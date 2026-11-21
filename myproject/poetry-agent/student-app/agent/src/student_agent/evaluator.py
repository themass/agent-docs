"""The evaluator: which retell points are missing. It never scores, grades or says "wrong".

Matching is keyword based on purpose (``any_of`` per point, from the sidecar the content lead reviews).
It is a pointer for a gentle supplement, not a judgement; semantic matching could be added later only if it
passes the eval set. Supplements are bundle lines quoted verbatim, never text written by a model.
"""
from __future__ import annotations

import re
import unicodedata

from .lesson import Fact, LessonContext, badge_for
from .models import BasisItem, Evaluation, Supplement

_TRAD = str.maketrans("國長陷鄜書萬書煙戰亂鳥開淚歲來為憂愁頭髮", "国长陷鄜书万书烟战乱鸟开泪岁来为忧愁头发")
BANNED_WORDS = ("错", "不对", "分数", "得分", "扣", "失败", "不及格", "答错")

_SUM_MANY = "你把主要的几点都讲到了，很清楚。"
_SUM_SOME = "你已经讲到了{labels}。还可以再想想另外几点。"
_SUM_NONE = "谢谢你愿意说出来。我们一起再看看这几点。"
_SUM_EMPTY = "先试着用自己的话说一说，说得不全也没关系。"


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "").lower().translate(_TRAD)
    return re.sub(r"[^\w一-鿿]", "", t)


NEGATORS = ("没有", "没", "无", "不", "未", "别", "非")


def _hit(norm: str, word: str) -> bool:
    """A keyword counts only when it is at least two characters and not negated just before it ("没有战争" is not "战争")."""
    if len(word) < 2:
        return False
    start = 0
    while True:
        i = norm.find(word, start)
        if i < 0:
            return False
        if not norm[max(0, i - 3):i].endswith(NEGATORS):   # "没有战争" / "不是战乱" are negated; "和平，战争" is not
            return True
        start = i + 1


def evaluate(text: str, ctx: LessonContext, supplement_cap: int = 2) -> tuple[Evaluation, list[Fact]]:
    points = [p for p in ctx.sidecar.get("points", []) if p.get("id")]
    norm = normalize(text)
    if not norm or not points:
        return Evaluation(summary=_SUM_EMPTY), []
    covered, missing = [], []
    for p in points:
        words = [normalize(w) for w in p.get("any_of", [])]
        (covered if any(_hit(norm, w) for w in words) else missing).append(p)
    labels = [str(p.get("label", "")) for p in covered if p.get("label")]
    if len(covered) >= 3:
        summary = _SUM_MANY
    elif covered:
        summary = _SUM_SOME.format(labels="、".join(labels))
    else:
        summary = _SUM_NONE
    used: list[Fact] = []
    supplement: list[Supplement] = []
    for p in missing[:supplement_cap]:
        ref = p.get("supplement_ref")
        fact = ctx.facts.get(ref) if ref else None
        if fact is None:
            continue
        used.append(fact)
        supplement.append(Supplement(
            point_id=str(p["id"]), ask=str(p.get("ask", "")), say=fact.text,
            badge=badge_for(fact.owner, [fact]),  # type: ignore[arg-type]
            basis=[BasisItem(kind="script", id=fact.id, claim_id=fact.claim_id)],
        ))
    return Evaluation(
        covered=[str(p["id"]) for p in covered], missing=[str(p["id"]) for p in missing],
        covered_labels=labels, summary=summary, supplement=supplement,
    ), used
