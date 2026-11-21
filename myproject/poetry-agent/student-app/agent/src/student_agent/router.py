"""Free-text routing. Rules only: no model classifies a child's sentence.

Order matters and is part of the contract (the eval set pins it):
  1. empty                      -> decline
  2. out-of-scope entity        -> decline   (e.g. 宰相, 大官: names the lesson never covers)
  3. homework request           -> decline with a fixed line ("I'll think it through with you, not for you")
  4. prepared FAQ               -> faq       (answer is a bundle fact, verbatim)
  5. intent rules               -> rephrase / basis / open_layer / hint / recite_prompt
  6. anything else              -> decline
Safety screening happens before this module is reached.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .lesson import LessonContext

HOMEWORK_REPLY = "我可以陪你一句一句想，但不能替你写。先说说，这一句你看到了什么？"

_HOMEWORK = re.compile(r"(帮我|替我|给我|替).{0,8}(写|作业|赏析|作文|答案|默写)|赏析|作文|标准答案")
_REPHRASE = re.compile(r"没听懂|听不懂|不懂|不明白|再说一遍|再讲一遍|换个说法|换一种|说简单")
_BASIS = re.compile(r"有根据|真的吗|是真的|出处|史书|哪里写的|怎么知道|可信|靠谱|真的假的")
_HINT = re.compile(r"哪个字|这个字|字词|注释|词语|这个词|什么意思")
_RECITE = re.compile(r"怎么读|怎么念|停顿|节奏|读音|韵")
_WHY = re.compile(r"为什么|为何|怎么会|凭什么")
_SEQ = re.compile(r"第\s*([1-9]|[一二三四五六七八])\s*句")
_CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8}
_LAYERS = (
    ("SCENE", ("眼前", "看到什么", "看见什么")),   # 「城墙」「城门」已不在台词里，不再当关键词
    ("CITY", ("这座城", "长安", "都城", "城里")),
    ("WORLD", ("天下", "战", "叛", "乱")),
    ("PERSON", ("这个人", "他是", "家人", "他的")),
)


@dataclass(frozen=True)
class Route:
    action: str  # decline | faq | rephrase | basis | open_layer | hint | recite_prompt
    layer: str | None = None
    line_seq: int | None = None
    ref: str | None = None
    say: str | None = None  # a fixed reply that bypasses the handlers (decline wording)
    reason: str = ""


def _seq(text: str) -> int | None:
    m = _SEQ.search(text)
    if not m:
        return None
    g = m.group(1)
    return int(g) if g.isdigit() else _CN.get(g)


def _headword_seq(text: str, ctx: LessonContext) -> int | None:
    """The line whose annotation's headword the learner named, e.g. 「烽火是什么」 -> the line 烽火 is on.

    The headword is the part of an annotation before its first 「：」. Only annotations that exist in the
    bundle's pack are consulted, so the answer is always an already-sourced sentence, never something new.
    Annotations on several lines: the first one wins (they are ordered by line).
    """
    best: tuple[int, int] | None = None  # (line, headword length)
    for fact in ctx.facts.values():
        if fact.kind != "ANNOTATION" or not fact.line_seqs:
            continue
        head = fact.text.split("：", 1)[0].strip()
        if len(head) < 2 or head not in text:
            continue
        key = (fact.line_seqs[0], len(head))
        if best is None or key[1] > best[1]:
            best = key
    return best[0] if best else None


def route(text: str, ctx: LessonContext) -> Route:
    t = (text or "").strip()
    if not t:
        return Route("decline", reason="empty")
    for entity in ctx.forbidden:
        if entity and entity in t:
            return Route("decline", reason="out_of_scope")
    if _HOMEWORK.search(t):
        return Route("decline", say=HOMEWORK_REPLY, reason="homework")
    for item in ctx.sidecar.get("faq", []):
        if any(trig and trig in t for trig in item.get("triggers", [])):
            return Route("faq", ref=item["answer_ref"], reason=f"faq:{item.get('id')}")
    seq = _seq(t)
    if seq is None and not _BASIS.search(t) and not _REPHRASE.search(t):
        seq = _headword_seq(t, ctx)
    if _BASIS.search(t):
        return Route("basis", line_seq=seq, reason="basis")
    if _REPHRASE.search(t) and not _HINT.search(t):
        return Route("rephrase", line_seq=seq, reason="rephrase")
    if seq is not None or _HINT.search(t):
        return Route("hint", line_seq=seq, reason="hint")
    if _RECITE.search(t):
        return Route("recite_prompt", line_seq=seq, reason="recite")
    # 层级关键词只说明“你在问哪一块”，不说明那张层卡回答了你的问题。「他为什么被困在长安」带着「长安」，
    # 却会被送到“这是帝国都城”——事实没错，但那不是答案。原因类的问题走到这里还没有现成的回答（FAQ、词头、
    # 注释都没接住），就老实说这课没讲到，不拿一张只描述、不解释的层卡顶替。
    if _WHY.search(t):
        return Route("decline", reason="why_unanswered")
    for layer, words in _LAYERS:
        if any(w in t for w in words):
            return Route("open_layer", layer=layer, reason=f"layer:{layer}")
    return Route("decline", reason="no_match")
