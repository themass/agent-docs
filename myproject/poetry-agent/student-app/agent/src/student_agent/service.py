"""One turn. Order is fixed and is the design (agent-design.md section 4):

  validate -> safety (free text) -> route -> step gate -> role-pruned facts -> SCRIPT ANSWER (always exists)
  -> optional wording by a model (<= 1 call + 1 retry) -> rule review -> else the script answer.

The response is always a valid TurnResponse. A model failing, timing out, being absent, being over budget or
being rejected by the reviewer is a ``degraded_reason`` on a scripted answer, never an error.
Logging records metadata only (action, role, source, model tier, latency, tokens), never what anyone wrote.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import safety
from .budget import AnswerCache, Ledger
from .config import Settings
from .evaluator import evaluate
from .lesson import Fact, LessonContext, badge_for, build_context, load_sidecar
from .llm import LLMClient, LLMError
from .machine import allowed, suggest
from .models import SAY_LIMIT, BasisItem, Evaluation, TurnRequest, TurnResponse
from .reviewer import review
from .router import route
from .sources import FixtureSource, JavaSource, Source, SourceError

log = logging.getLogger("student_agent.turn")
SOULS = Path(__file__).parent / "souls"
BREAKER_FAILURES = 3
BREAKER_SECONDS = 60
SOURCE_NEGATIVE_SECONDS = 30
LLM_ROLES = {"narrator": "narrator.md", "poet": "poet.md", "guide": "guide.md"}

_NO_CONTEXT = "这一课的讲解暂时没取到，先看页面上的文字吧，文字不受影响。"
_RATE = "你问得有点快，歇一会儿再问吧。先看看页面上的文字。"
_READ_FIRST = "先把诗读一读，读完告诉我，你最想弄清楚哪一句。"
_DECLINE = "这一点我们这一课没有讲到，我也不乱说。要不要回头看看已经讲过的部分？"
_POET_EXIT = "这个我说不好。你去看看“这座城”和“这个天下”吧，那里有说得清楚的。"
_PICK_LINE = "你想问哪一句？点一下那一句，我再告诉你。"


@dataclass
class Answer:
    role: str
    say: str
    basis: list[BasisItem]
    badge: str = "NONE"
    next: str = "no_action"
    facts: list[Fact] | None = None  # the facts this answer was built from (for review and the badge)
    evaluation: Evaluation | None = None
    reword: bool = False  # eligible to be reworded by a model
    declined: bool = False


@dataclass
class Meta:
    outcome: str  # answer | decline | safety | unavailable | rate
    model_tier: str | None = None
    ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


def _item(f: Fact) -> BasisItem:
    return BasisItem(kind="annotation" if f.kind == "ANNOTATION" else "script", id=f.id, claim_id=f.claim_id)


class TurnService:
    def __init__(self, settings: Settings, source: Source | None = None, llm: Any | None = None) -> None:
        self.s = settings
        self.source: Source = source or (
            JavaSource(settings.java_base) if settings.source == "java" and settings.java_base
            else FixtureSource(settings.fixtures_dir, settings.bundles_dir))
        self.llm = llm if llm is not None else (LLMClient(settings) if settings.llm_configured else None)
        self.ledger = Ledger(settings.calls_per_lesson, settings.tokens_per_lesson, settings.turns_per_minute)
        self.cache = AnswerCache()
        self.souls = {role: self._soul(name) for role, name in LLM_ROLES.items()}
        self._contexts: dict[tuple[str, str], LessonContext] = {}
        # Circuit breaker: after BREAKER_FAILURES gateway failures in a row, stop calling it for BREAKER_SECONDS.
        self._fail_streak = 0
        self._open_until = 0.0
        self._source_down_until: dict[tuple[str, str], float] = {}

    @staticmethod
    def _soul(name: str) -> str:
        try:
            return (SOULS / name).read_text(encoding="utf-8")
        except OSError:
            return ""

    # ---------------------------------------------------------------- public

    def handle(self, req: TurnRequest, bucket: str = "anon") -> TurnResponse:
        return self.handle_detailed(req, bucket)[0]

    def handle_detailed(self, req: TurnRequest, bucket: str = "anon") -> tuple[TurnResponse, Meta]:
        started = time.monotonic()
        resp, meta = self._turn(req, bucket)
        meta.ms = meta.ms or int((time.monotonic() - started) * 1000)
        log.info("turn action=%s step=%s role=%s outcome=%s source=%s degraded=%s tier=%s ms=%d pt=%d ct=%d",
                 req.action, req.step, resp.role, meta.outcome, resp.source, resp.degraded_reason,
                 meta.model_tier, meta.ms, meta.prompt_tokens, meta.completion_tokens)
        return resp, meta

    # ---------------------------------------------------------------- internals

    def _turn(self, req: TurnRequest, bucket: str) -> tuple[TurnResponse, Meta]:
        if not self.ledger.allow_turn(bucket):
            return self._plain("guide", _RATE), Meta("rate")
        text = (req.args.text or "").strip()
        action, args = req.action, req.args

        if action == "free_text":
            text = text[:SAY_LIMIT]
            hit = safety.screen(text)
            if hit:
                return self._plain("guide", hit.say), Meta("safety")
        elif action == "evaluate_retell":
            hit = safety.screen(text)
            if hit:
                return self._plain("guide", hit.say), Meta("safety")

        ctx = self._context(req)
        if ctx is None:
            return self._plain("guide", _NO_CONTEXT, degraded="unavailable"), Meta("unavailable")

        say_override: str | None = None
        if action == "free_text":
            r = route(text, ctx)
            action, say_override = r.action, r.say
            updates = {k: v for k, v in (("layer", r.layer), ("line_seq", r.line_seq), ("ref", r.ref)) if v}
            args = args.model_copy(update=updates)

        if req.step == "read":
            return self._plain("guide", ctx.sidecar.get("guide", {}).get("read", _READ_FIRST)), Meta("decline")
        if not allowed(req.step, action):
            action = "decline"

        ans = self._script(action, req, args, ctx, text, say_override)
        return self._finish(ans, req, ctx, bucket, Meta("decline" if ans.declined else "answer"))

    def _context(self, req: TurnRequest) -> LessonContext | None:
        key = (req.bundle_hash, req.work_id)
        if key in self._contexts:
            return self._contexts[key]
        now = time.monotonic()
        if self._source_down_until.get(key, 0.0) > now:
            return None                       # negative cache: the source failed a moment ago, do not wait on it again
        try:
            bundle = self.source.bundle(req.bundle_hash)
            pack = self.source.pack(req.work_id)
        except SourceError:
            self._source_down_until[key] = now + SOURCE_NEGATIVE_SECONDS
            return None
        self._source_down_until.pop(key, None)
        ctx = build_context(bundle, pack, load_sidecar(self.s.lessons_dir, req.work_id), req.work_id, req.bundle_hash)
        for w in ctx.warnings:
            log.warning("lesson warning: %s", w[:120])
        if len(self._contexts) > 64:
            self._contexts.clear()
        self._contexts[key] = ctx
        return ctx

    # ---------------------------------------------------------------- scripted answers

    def _decline(self, req: TurnRequest, ctx: LessonContext, say_override: str | None = None) -> Answer:
        guide = ctx.sidecar.get("guide", {})
        if req.step == "meet" and say_override is None:
            # In the poet's scene the poet leaves gracefully ("主动退场是设计的一部分"); it is still a role-play line.
            return Answer("poet", guide.get("poet_exit", _POET_EXIT), [], "DRAMATIZATION", declined=True)
        return Answer("guide", say_override or guide.get("decline", _DECLINE), [], declined=True,
                      next="suggest_step:return" if req.step == "recite" else "no_action")

    def _script(self, action: str, req: TurnRequest, args, ctx: LessonContext, text: str,
                say_override: str | None) -> Answer:
        guide = ctx.sidecar.get("guide", {})

        if action == "decline":
            return self._decline(req, ctx, say_override)

        if action == "faq":
            f = ctx.facts.get(args.ref or "")
            owner_ok = f is not None and ((f.owner == "poet") == (req.step == "meet")) and f.kind != "ANNOTATION"
            if not f or not owner_ok:
                return self._decline(req, ctx)
            return Answer(f.owner, f.text, [_item(f)], badge_for(f.owner, [f]), facts=[f], reword=True)

        if action == "open_layer":
            layer = args.layer
            facts = ctx.layer_facts(layer, "arrive") if layer else []
            if not facts:
                return self._decline(req, ctx)
            used = facts[:2]
            return Answer("narrator", "".join(f.text for f in used), [_item(f) for f in used],
                          badge_for("narrator", used), facts=used, reword=True)

        if action == "basis":
            f = ctx.pick(req.step, args.ref, args.layer)
            if f is None:
                return Answer("guide", _PICK_LINE, [])
            if f.kind == "DRAMATIZATION":
                say = "这是教学演绎，不是史料里的原话。想看有出处的内容，去看“这座城”和“这个天下”。"
                return Answer("narrator", say, [_item(f)], "DRAMATIZATION", facts=[f])
            label = "史实" if f.kind == "FACT" else "对这件事的理解"
            return Answer("narrator", f"这一条属于{label}，出处在诗词页的“出处与说法”里，可以点开看。",
                          [_item(f)], badge_for("narrator", [f]), facts=[f])

        if action == "rephrase":
            f = ctx.pick(req.step, args.ref, args.layer)
            if f is None and args.line_seq:
                anns = ctx.annotations_for(args.line_seq)[:1]
                if anns:
                    return Answer("narrator", anns[0].text, [_item(anns[0])], facts=anns, reword=True)
            if f is None:
                return Answer("guide", guide.get("rephrase", _PICK_LINE), [])
            return Answer(f.owner, f.text, [_item(f)], badge_for(f.owner, [f]), facts=[f], reword=True)

        if action == "hint":
            if not args.line_seq:
                return Answer("guide", _PICK_LINE, [])
            anns = ctx.annotations_for(args.line_seq, {"WORD", "PHRASE", "IMAGE", "ALLUSION"})[:2]
            if not anns:
                return Answer("guide", guide.get("no_annotation", "这一句的字词说明还在整理，先读读上下句。"), [])
            return Answer("narrator", "".join(a.text for a in anns), [_item(a) for a in anns],
                          facts=anns, reword=True)

        if action == "ask_why":
            line = ctx.lines.get(args.line_seq or 0, "")
            tpl = guide.get("ask_why", "读到“{line}”，你想到了什么？")
            return Answer("guide", tpl.replace("{line}", line) if line else tpl.replace("“{line}”", "这一句"), [])

        if action == "recite_prompt":
            seq = args.line_seq or 0
            rhyme = ctx.annotations_for(seq, {"RHYME"})[:1] if seq else []
            base = guide.get("recite", "放慢一点，一句一句读。")
            if rhyme:
                return Answer("guide", base + rhyme[0].text, [_item(rhyme[0])], facts=rhyme)
            return Answer("guide", base, [])

        if action == "evaluate_retell":
            ev, used = evaluate(text, ctx)
            return Answer("guide", ev.summary, [BasisItem(kind="script", id=f.id, claim_id=f.claim_id) for f in used],
                          next=suggest(req.step, action, len(ev.missing)), evaluation=ev, facts=used or None)

        return self._decline(req, ctx)

    # ---------------------------------------------------------------- wording + review

    def _finish(self, ans: Answer, req: TurnRequest, ctx: LessonContext, bucket: str,
                meta: Meta) -> tuple[TurnResponse, Meta]:
        degraded: str | None = None
        source = "script"
        say = ans.say
        if ans.reword and ans.facts:
            eligible = req.action in self.s.llm_actions or req.action == "free_text"
            if ans.role == "poet" and not self.s.llm_poet:
                eligible = False
            if eligible:
                if self.s.mode != "llm" or self.llm is None:
                    degraded = "disabled"
                elif not self.ledger.can_call_llm(bucket):
                    degraded = "budget"
                else:
                    say, source, degraded = self._reword(ans, req, ctx, bucket, meta)
        resp = TurnResponse(role=ans.role, say=say, basis=ans.basis, badge=ans.badge, next=ans.next,  # type: ignore[arg-type]
                            source=source, degraded_reason=degraded, evaluation=ans.evaluation)  # type: ignore[arg-type]
        return resp, meta

    def _reword(self, ans: Answer, req: TurnRequest, ctx: LessonContext, bucket: str,
                meta: Meta) -> tuple[str, str, str | None]:
        facts = ans.facts or []
        key = (ctx.bundle_hash, ans.role, req.action, tuple(f.id for f in facts))
        hit = self.cache.get(key)
        if isinstance(hit, str):
            return hit, "llm", None
        if time.monotonic() < self._open_until:
            return ans.say, "script", "unavailable"
        reason = "rejected"
        for tier in ("primary", "fallback"):
            try:
                out = self.llm.rephrase(role=ans.role, soul=self.souls.get(ans.role, ""), script_say=ans.say,
                                        facts=facts, tier=tier)
            except LLMError as exc:
                reason = exc.reason
                self.ledger.record_call(bucket, 0)
                if reason in ("timeout", "unavailable"):
                    self._fail_streak += 1
                    if self._fail_streak >= BREAKER_FAILURES:
                        self._open_until = time.monotonic() + BREAKER_SECONDS
                        self._fail_streak = 0
                        log.warning("gateway breaker open for %ds", BREAKER_SECONDS)
                if reason == "timeout" or tier == "fallback":
                    break
                continue
            self.ledger.record_call(bucket, out.prompt_tokens + out.completion_tokens)
            meta.model_tier, meta.prompt_tokens, meta.completion_tokens = tier, out.prompt_tokens, out.completion_tokens
            verdict = review(out.say, role=ans.role, allowed_facts=facts, uses=out.uses,
                             forbidden=ctx.forbidden)
            self._fail_streak = 0
            if verdict.ok:
                self.cache.put(key, out.say)
                return out.say, "llm", None
            log.info("review rejected rule=%s tier=%s", verdict.rule, tier)
            reason = "rejected"
            if not self.ledger.can_call_llm(bucket):
                reason = "budget"
                break
        return ans.say, "script", reason

    def _plain(self, role: str, say: str, degraded: str | None = None) -> TurnResponse:
        return TurnResponse(role=role, say=say, source="script", degraded_reason=degraded)  # type: ignore[arg-type]
