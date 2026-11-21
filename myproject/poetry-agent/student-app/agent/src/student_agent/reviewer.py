"""The reviewer: rules first, and a pure function so the eval set can hit it directly.

It judges model-reworded text before a child sees it. It records WHICH rule failed (an id), never the text.
Script answers are human-approved content and do not pass through here; instead ``test_sidecar_lint`` runs
every sidecar string through these same rules so the wording written for this service obeys them too.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .lesson import Fact

# One limit for every reader: the product is not split by grade (2026-11-12). The prompt states the same number.
SAY_LIMIT = 100
GROUNDING_MIN = 0.45  # share of the output's character bigrams that must occur in the allowed text

_DIGITS = re.compile(r"\d+")
_CN_NUM = re.compile(r"[一二三四五六七八九十百千万两零〇]{1,6}(?=岁|年|载|万|个月|月|日|天|里|步|人|口|次)")
_URL = re.compile(r"https?://|www\.|\.com|\.cn|@")
_PERSONAL_ASK = re.compile(r"你叫什么|你的名字|你住|你家在|哪个学校|手机号|微信|电话")
_ABSOLUTE = ("肯定", "一定", "毫无疑问", "绝对", "千真万确")
_NARRATOR_BANNED = ("我觉得", "我认为", "我以为", "在我看来", "我们家", "我的家")
_POET_BANNED = ("据记载", "史书", "史载", "据说", "学界", "研究表明", "后人")
_NAMES = ("杜甫", "李白", "安禄山", "史思明", "唐玄宗", "唐肃宗", "玄宗", "肃宗", "杨贵妃", "长安", "洛阳", "鄜州",
          "潼关", "凤翔", "灵武", "安史之乱", "唐朝", "宰相")


@dataclass(frozen=True)
class Verdict:
    ok: bool
    rule: str | None = None  # the id of the first rule that failed


def _bigrams(text: str) -> set[str]:
    t = re.sub(r"[\s，。！？、；：“”‘’（）,.!?;:'\"()—…-]", "", text)
    return {t[i:i + 2] for i in range(len(t) - 1)}


def _numbers(text: str) -> set[str]:
    return set(_DIGITS.findall(text)) | set(_CN_NUM.findall(text))


def review(say: str, *, role: str, allowed_facts: list[Fact], uses: list[str],
           user_text: str = "", forbidden: list[str] | None = None, extra_allowed: str = "") -> Verdict:
    allowed_ids = {f.id for f in allowed_facts}
    allowed_text = "".join(f.text for f in allowed_facts) + extra_allowed + (user_text or "")
    if not say or not say.strip():
        return Verdict(False, "R-empty")
    if role != "guide" and (not uses or any(u not in allowed_ids for u in uses)):
        return Verdict(False, "R-basis")
    if _numbers(say) - _numbers(allowed_text):
        return Verdict(False, "R-fact")
    for name in list(_NAMES) + list(forbidden or []):
        if name and name in say and name not in allowed_text:
            return Verdict(False, "R-uncovered" if name in (forbidden or []) else "R-fact")
    if role == "narrator" and any(p in say for p in _NARRATOR_BANNED):
        return Verdict(False, "R-mode")
    if role == "poet" and any(p in say for p in _POET_BANNED):
        return Verdict(False, "R-mode")
    if role == "guide" and re.search(r"我站|我认不出|我当时|我被困", say):
        return Verdict(False, "R-mode")
    soft = {f.kind for f in allowed_facts if f.id in set(uses)} & {"INTERPRETATION", "DRAMATIZATION"}
    if soft and any(w in say for w in _ABSOLUTE):
        return Verdict(False, "R-hedge")
    if len(say) > SAY_LIMIT or say.count("\n") > 1:
        return Verdict(False, "R-len")
    if _URL.search(say) or re.search(r"\d{6,}", say) or _PERSONAL_ASK.search(say):
        return Verdict(False, "R-safe")
    grams = _bigrams(say)
    if role != "guide" and grams:
        overlap = len(grams & _bigrams(allowed_text)) / len(grams)
        if overlap < GROUNDING_MIN:
            return Verdict(False, "R-grounding")
    return Verdict(True)
