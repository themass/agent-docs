#!/usr/bin/env python3
"""Walk a profile from nothing to generatable, through both intake paths.

What this covers that the unit tests do not
-------------------------------------------
`test_profile_intake.py` and `test_intake_tools.py` assert individual transitions: this
question appears, that answer lands, a closed question is refused. None of them answer
the plan repeatedly until it runs out, which is the only way to observe the two failure
modes that actually broke this feature in use:

- **It does not terminate.** Highlight question ids were once derived from the remaining
  shortfall, so every answer renumbered the next question, the plan re-issued an id it
  had just dropped, and the interview stalled one bullet short of generating. Nothing
  failed; the user simply could never finish.
- **The two paths diverge.** The panel (`POST /intake-answers`) and the agent
  (`jc_intake_record`) are separate entry points onto one plan. The plan is mostly
  self-healing here, because questions are derived from the *shape of the profile* -- a
  filled-in name stops producing the name question whether or not anything remembered
  answering it. What is not self-healing is the writing: an answer that is stored as
  evidence but never lands in a structured field leaves the question open forever, and
  that is invisible from either path alone.

So this script runs the same interview twice over identical profiles -- once entirely
through `IntakeService`, once entirely through the agent tools -- and requires that both
reach `can_generate` with the lead role actually filled in. The two walks answer at
different granularity on purpose: the panel submits a stage at a time, the agent one
question at a time, which is how each is really driven.

Why it is offline, and why that matters
---------------------------------------
Intake is the one path in JC with no model between the user and their profile
(`schemas/intake.py` states that trust class). That makes the whole walk deterministic,
so this runs against an in-memory SQLite database with no model, no browser and no MySQL
-- which is why it belongs in `test-local.sh` rather than behind a real-run flag like
`verify_resume_steps.py`. A convergence check that only runs when someone remembers to
run it is not a gate.

Usage:
    python scripts/verify_intake_flow.py [--output docs/evidence/intake-flow.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lib.bootstrap import ensure_project_env

PROJECT_ROOT = ensure_project_env()
SERVER_ROOT = PROJECT_ROOT / "backend" / "server"

from agentkit.web.auth import UserActor  # noqa: E402
from jc.authz import RunScope  # noqa: E402
from jc.db.base import Base  # noqa: E402
from jc.mcp.handlers import intake_plan as tool_intake_plan  # noqa: E402
from jc.mcp.handlers import intake_record as tool_intake_record  # noqa: E402
from jc.models import *  # noqa: E402, F403
from jc.models.profile import Profile  # noqa: E402
from jc.models.user import User  # noqa: E402
from jc.schemas.intake import (  # noqa: E402
    IntakeAnswerInput,
    IntakeAnswerRequest,
    IntakeSplitRequest,
)
from jc.services.intake_service import IntakeService  # noqa: E402
from jc.services.profile_intake import NEW_EXPERIENCE_PATH  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

#: Ceiling on how many answer rounds an interview may need. Not a performance budget:
#: a walk that needs more rounds than there are questions is re-issuing ids, which is
#: the non-termination bug stated above. Deliberately loose -- it should fail only when
#: the plan is genuinely looping, not when a stage gains a question.
_MAX_ROUNDS = 30

#: Highlights the most recent role must end up with. Mirrors
#: `profile_intake._MIN_HIGHLIGHTS_LEAD_ROLE` rather than importing it: this script is
#: asserting the product promise ("the role that decides the hire is not thin"), so it
#: has to fail if that constant is quietly lowered.
_MIN_LEAD_HIGHLIGHTS = 3

_EXPERIENCE_PATH_RE = re.compile(r"^experiences\[(\d+)\]$")
_HIGHLIGHT_PATH_RE = re.compile(r"^experiences\[(\d+)\]\.highlights\[(\d+)\]$")

#: A dictated answer holding four separate achievements, the way people actually talk
#: about their own work. Used once per walk so the split path is exercised inside the
#: convergence run rather than only in isolation.
_DICTATED = (
    "我带了 4 个人把订单中心从单体拆成 6 个服务。"
    "发布耗时从 40 分钟降到 6 分钟。"
    "顺手把配置中心推到了 120 多个服务。"
    "大促期间支撑了日均 1200 万单。"
)


def answer_for(target_path: str, *, round_no: int) -> str | None:
    """A plausible user answer for one profile path, or None if the path is unknown.

    Routed on `target_path` rather than on question id on purpose. A question id is a
    label; the path is the contract with `apply_answer`. If someone adds a question
    whose path nothing writes, this returns None and the walk fails loudly -- which is
    the point, because such a question is answerable forever: the answer is stored as
    evidence, `count_written_evidence` never counts it, and the interview cannot end.
    """
    if target_path == "contact.name":
        return "李雷"
    if target_path in ("contact.email", "contact.phone"):
        return "lilei@example.test"
    if target_path == "contact.location":
        return "上海"
    if target_path == "summary":
        return "十年后端，做过交易和结算两条主链路。"
    if target_path == "preferences.target_roles":
        return "后端技术专家 / 架构师"
    if target_path == NEW_EXPERIENCE_PATH:
        return "新新科技 · 后端技术专家 · 2024-02 至今"
    exp = _EXPERIENCE_PATH_RE.match(target_path)
    if exp:
        idx = int(exp.group(1))
        return f"第{idx + 1}家科技 · 后端技术专家 · 20{20 - idx}-03 至今"
    if _HIGHLIGHT_PATH_RE.match(target_path):
        return f"主导第 {round_no} 项改造，把一条主链路的超时率从 3% 降到 0.4%。"
    if target_path.endswith(".scope"):
        return "带 8 人后端团队，负责订单与结算两条主链路"
    return None


def _in_plan_order(plan: dict[str, Any], chosen: set[str]) -> list[str]:
    """`chosen` in the order the plan listed them, so the walk follows the interview."""
    return [q["id"] for q in plan["questions"] if q["id"] in chosen]


def _next_batch(
    questions: list[tuple[str, str, bool]],
) -> set[str]:
    """Which of the pending questions this round answers: required first, then optional.

    Required-only would make the `stale` case vacuous. A stale profile already holds
    three highlights, so it can generate before the interview starts and its one
    question (「现在这份工作是什么」) is deliberately optional -- a user may genuinely be
    between roles. A walk that stops at `can_generate` therefore never answers it, and
    the branch that exists to stop us interviewing someone about the job they left
    would be covered by nothing.

    Answering the optional ones also reaches the second-role questions, which only
    appear once `experiences[1]` exists. Each id drops out as it is answered, so the
    walk still terminates.
    """
    answerable = [(qid, path) for qid, path, _ in questions if answer_for(path, round_no=1)]
    required = {qid for qid, path, req in questions if req and answer_for(path, round_no=1)}
    if required:
        return required
    return {qid for qid, _ in answerable}


@dataclass
class Walk:
    """One interview run, recorded well enough to explain a failure."""

    path: str
    mode_at_start: str
    rounds: int = 0
    asked: list[str] = field(default_factory=list)
    answers: dict[str, str] = field(default_factory=dict)
    repeated: list[str] = field(default_factory=list)
    unwritten_required: list[str] = field(default_factory=list)
    can_generate: bool = False
    blocking: list[str] = field(default_factory=list)
    split_segments: int = 0

    def note_asked(self, question_id: str) -> None:
        if question_id in self.asked:
            self.repeated.append(question_id)
        self.asked.append(question_id)

    def report(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "mode_at_start": self.mode_at_start,
            "rounds": self.rounds,
            "questions_asked": len(self.asked),
            "repeated_question_ids": self.repeated,
            "required_questions_that_wrote_nothing": self.unwritten_required,
            "can_generate": self.can_generate,
            "blocking": self.blocking,
            "dictated_split_segments": self.split_segments,
        }


async def _fresh_db(payload: dict[str, Any]):
    """An isolated in-memory database holding one owned profile."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = async_sessionmaker(engine, expire_on_commit=False)()
    session.add(User(id="usr_walk", email="walk@example.test", password_hash="x"))
    session.add(
        Profile(
            id="prof_walk",
            user_id="usr_walk",
            owner_kind="user",
            payload=payload,
            version=1,
        )
    )
    await session.commit()
    return engine, session


async def walk_panel(payload: dict[str, Any]) -> tuple[Walk, dict[str, Any]]:
    """Answer the plan through `IntakeService`, the way the panel does."""
    engine, db = await _fresh_db(payload)
    actor = UserActor(user_id="usr_walk", session_id="login")
    service = IntakeService(db)
    walk = Walk(path="panel", mode_at_start="")
    try:
        plan = await service.get_plan("prof_walk", actor=actor)
        walk.mode_at_start = plan.mode
        dictated_used = False

        for _ in range(_MAX_ROUNDS):
            if plan.can_generate and not plan.questions:
                break
            pending = _next_batch([(q.id, q.target_path, q.required) for q in plan.questions])
            if not pending:
                break
            pending = [q for q in plan.questions if q.id in pending]
            walk.rounds += 1
            batch: list[IntakeAnswerInput] = []
            for question in pending:
                walk.note_asked(question.id)
                is_highlight = bool(_HIGHLIGHT_PATH_RE.match(question.target_path))
                if is_highlight and not dictated_used:
                    # One answer per walk goes through the dictation split, so the
                    # multi-point paragraph is covered inside the convergence run.
                    dictated_used = True
                    split = await service.split_answer(
                        "prof_walk",
                        actor=actor,
                        body=IntakeSplitRequest(
                            question_id=question.id,
                            target_path=question.target_path,
                            answer=_DICTATED,
                        ),
                    )
                    walk.split_segments = len(split.segments)
                    for segment in split.segments:
                        batch.append(
                            IntakeAnswerInput(
                                question_id=segment.question_id,
                                target_path=segment.target_path,
                                question=question.question,
                                answer=segment.text,
                            )
                        )
                        walk.answers[segment.question_id] = segment.text
                    continue
                text = answer_for(question.target_path, round_no=walk.rounds)
                if text is None:
                    raise SystemExit(
                        "FAIL: plan asked for a path nothing can answer: "
                        f"{question.id} -> {question.target_path}"
                    )
                batch.append(
                    IntakeAnswerInput(
                        question_id=question.id,
                        target_path=question.target_path,
                        question=question.question,
                        answer=text,
                    )
                )
                walk.answers[question.id] = text

            result = await service.submit_answers(
                "prof_walk", actor=actor, body=IntakeAnswerRequest(answers=batch)
            )
            if not result.applied:
                walk.unwritten_required.extend(a.question_id for a in batch)
            plan = result.plan

        walk.can_generate = plan.can_generate
        walk.blocking = list(plan.blocking)
        final = await service.get_plan("prof_walk", actor=actor)
        row = await db.get(Profile, "prof_walk")
        snapshot = dict(row.payload or {})
    finally:
        await db.close()
        await engine.dispose()
    # Re-read rather than trusting the submit response: the plan the user sees next is
    # the one computed from the stored profile, and that is what must agree.
    walk.can_generate = final.can_generate
    walk.blocking = list(final.blocking)
    return walk, snapshot


async def walk_agent(payload: dict[str, Any]) -> tuple[Walk, dict[str, Any]]:
    """Answer the same plan through the agent tools, the way 舟卡 does in chat."""
    engine, db = await _fresh_db(payload)
    scope = RunScope(
        db=db, user_id="usr_walk", profile_id="prof_walk", session_id="agsn_walk"
    )
    walk = Walk(path="agent", mode_at_start="")
    try:
        plan = await tool_intake_plan(scope, limit=12)
        walk.mode_at_start = plan["mode"]

        for _ in range(_MAX_ROUNDS):
            chosen = _next_batch(
                [(q["id"], q["target_path"], q["required"]) for q in plan["questions"]]
            )
            if not chosen:
                break
            # One question per round, unlike the panel. This is how the chat path
            # actually behaves -- the agent records an answer as the user gives it --
            # and it is the only way to observe question-id renumbering: a walk that
            # answers a whole stage at once fills every slot before the plan is
            # recomputed, so an id derived from the remaining shortfall never gets the
            # chance to shift.
            pending = [
                q for q in plan["questions"] if q["id"] == next(iter(_in_plan_order(plan, chosen)))
            ]
            walk.rounds += 1
            batch: list[dict[str, str]] = []
            for question in pending:
                walk.note_asked(question["id"])
                text = answer_for(question["target_path"], round_no=walk.rounds)
                if text is None:
                    raise SystemExit(
                        "FAIL: plan asked for a path nothing can answer: "
                        f"{question['id']} -> {question['target_path']}"
                    )
                # Declared deliberately: the tool must accept the plan's own path and
                # reject any other, so passing it is the honest client behaviour.
                batch.append(
                    {
                        "question_id": question["id"],
                        "target_path": question["target_path"],
                        "answer": text,
                    }
                )
                walk.answers[question["id"]] = text

            result = await tool_intake_record(scope, answers=batch)
            if not result["applied"]:
                walk.unwritten_required.extend(a["question_id"] for a in batch)
            plan = await tool_intake_plan(scope, limit=12)

        walk.can_generate = plan["can_generate"]
        walk.blocking = list(plan["blocking"])
        row = await db.get(Profile, "prof_walk")
        snapshot = dict(row.payload or {})
        contact_name = row.contact_name
    finally:
        await db.close()
        await engine.dispose()
    # The tool maintains the denormalised column the profile list renders from. A walk
    # that fills in a name and leaves the sidebar showing an unnamed profile is a bug
    # the plan itself cannot see.
    if walk.answers and not contact_name:
        raise SystemExit("FAIL: agent walk left profile.contact_name empty")
    return walk, snapshot


def _highlights(snapshot: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for exp in snapshot.get("experiences") or []:
        out.extend(exp.get("highlights") or [])
    return out


def _check(walk: Walk, snapshot: dict[str, Any], *, failures: list[str]) -> None:
    where = f"{walk.mode_at_start}/{walk.path}"
    if not walk.can_generate:
        failures.append(f"{where}: never reached can_generate; blocking={walk.blocking}")
    if walk.repeated:
        failures.append(f"{where}: plan re-issued {sorted(set(walk.repeated))}")
    if walk.rounds >= _MAX_ROUNDS:
        failures.append(f"{where}: hit the {_MAX_ROUNDS}-round ceiling")
    if walk.unwritten_required:
        failures.append(
            f"{where}: required answers wrote no structured field: "
            f"{walk.unwritten_required}"
        )
    # Verbatim is the promise intake makes. Checked on the stored profile, not on the
    # response, because the response is produced by the same call that did the write.
    stored = json.dumps(snapshot, ensure_ascii=False)
    for question_id, text in walk.answers.items():
        if text not in stored:
            failures.append(f"{where}: answer to {question_id} is not in the profile")
            break
    if not (snapshot.get("contact") or {}).get("name"):
        failures.append(f"{where}: finished without a name")
    if len(_highlights(snapshot)) < 3:
        failures.append(f"{where}: finished with {len(_highlights(snapshot))} highlights")

    # The lead role specifically, not the total. The original bug stalled the interview
    # one bullet short of the floor on `experiences[0]`, and a total can hide that: an
    # optional second role contributes highlights too, so the profile reaches
    # `can_generate` while the role that carries the hiring decision stays thin.
    lead = (snapshot.get("experiences") or [{}])[0]
    lead_count = len(lead.get("highlights") or [])
    if lead_count < _MIN_LEAD_HIGHLIGHTS:
        failures.append(
            f"{where}: lead role ended with {lead_count} highlights "
            f"(needs {_MIN_LEAD_HIGHLIGHTS})"
        )
    # An empty bullet is a bullet-shaped hole in the rendered resume, and it is what a
    # slot the interview skipped looks like once something lands after it.
    for idx, role in enumerate(snapshot.get("experiences") or []):
        if any(not (h or "").strip() for h in role.get("highlights") or []):
            failures.append(f"{where}: experiences[{idx}] holds an empty highlight")


async def run() -> dict[str, Any]:
    """Every starting mode, through both paths, compared."""
    # One fixture per `classify_mode` branch. `complete` is excluded: it can generate
    # before the interview starts, so it proves nothing about convergence.
    starts: dict[str, dict[str, Any]] = {
        "empty": {},
        "skeleton": {
            "contact": {"name": "李雷"},
            "experiences": [
                {
                    "id": "exp_1",
                    "company": "某某科技",
                    "title": "后端技术专家",
                    "start_date": "2021-03",
                    "highlights": ["把订单链路超时率从 3% 降到 0.4%"],
                }
            ],
        },
        "stale": {
            "contact": {"name": "李雷", "email": "lilei@example.test"},
            "experiences": [
                {
                    "id": "exp_1",
                    "company": "某某科技",
                    "title": "后端技术专家",
                    "start_date": "2019-03",
                    "end_date": "2022-08",
                    "scope": "带 8 人后端团队",
                    "highlights": [
                        "主导订单服务拆分为 6 个微服务",
                        "搭建配置中心覆盖 120 多个服务",
                        "大促支撑日均 1200 万单",
                    ],
                }
            ],
        },
    }

    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    for name, payload in starts.items():
        panel, panel_snapshot = await walk_panel(json.loads(json.dumps(payload)))
        agent, agent_snapshot = await walk_agent(json.loads(json.dumps(payload)))

        if panel.mode_at_start != name:
            failures.append(
                f"{name}: classified as {panel.mode_at_start}, so this case tests "
                "the wrong branch"
            )
        _check(panel, panel_snapshot, failures=failures)
        _check(agent, agent_snapshot, failures=failures)

        if name == "stale":
            # The one property this branch exists for: the current job is an insertion,
            # not an edit. Writing it to `experiences[0]` would delete a real role to
            # make room, and the resume reads most-recent-first off this order.
            for who, snapshot in (("panel", panel_snapshot), ("agent", agent_snapshot)):
                roles = snapshot.get("experiences") or []
                companies = [r.get("company") for r in roles]
                if "某某科技" not in companies:
                    failures.append(f"stale/{who}: the old role was overwritten")
                elif companies[0] == "某某科技":
                    failures.append(
                        f"stale/{who}: the new current role did not move to the front "
                        f"({companies})"
                    )
                if len(roles) < 2:
                    failures.append(f"stale/{who}: ended with {len(roles)} role(s)")

        # The convergence claim: two entry points onto one plan must not leave the
        # user in different places. Compared on the questions asked rather than on
        # the payload, because the panel walk deliberately routes one answer through
        # the dictation split and so stores more highlights.
        if panel.asked != agent.asked[: len(panel.asked)] and set(agent.asked) - set(
            panel.asked
        ):
            failures.append(
                f"{name}: panel and agent were asked different questions "
                f"({sorted(set(panel.asked) ^ set(agent.asked))})"
            )
        cases.append(
            {
                "start": name,
                "panel": panel.report(),
                "agent": agent.report(),
                "highlights_after": {
                    "panel": len(_highlights(panel_snapshot)),
                    "agent": len(_highlights(agent_snapshot)),
                },
            }
        )

    # The split has to actually have fanned out, or the walk silently stopped covering
    # it and the 300-character-bullet failure would come back unnoticed.
    if not any(case["panel"]["dictated_split_segments"] > 1 for case in cases):
        failures.append("dictation split never produced more than one segment")

    return {
        "scope": (
            "offline intake convergence: no model, no browser, no MySQL. "
            "Proves the interview terminates and that the panel and the agent "
            "tools agree about one plan."
        ),
        "max_rounds_allowed": _MAX_ROUNDS,
        "cases": cases,
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "docs" / "evidence" / "intake-flow.json",
    )
    args = parser.parse_args()
    report = asyncio.run(run())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    if report["failures"]:
        for line in report["failures"]:
            print(f"FAIL: {line}")
        raise SystemExit(f"FAIL: {len(report['failures'])} intake flow findings")
    rounds = ", ".join(
        f"{case['start']}={case['panel']['rounds']}/{case['agent']['rounds']}"
        for case in report["cases"]
    )
    print(f"PASS: intake reaches can_generate on both paths (rounds panel/agent: {rounds})")


if __name__ == "__main__":
    main()
