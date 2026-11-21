"""The wording written for this service must obey the same rules the reviewer applies to model output."""
from __future__ import annotations

import json
import re

from student_agent import evaluator, safety
from student_agent.config import AGENT_ROOT
from student_agent.reviewer import _NARRATOR_BANNED
from student_agent.router import HOMEWORK_REPLY

SIDECAR = AGENT_ROOT / "data" / "lessons" / "lesson.chun-wang.json"


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k in {"note", "status"}:
                continue
            yield from strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings(v)


def test_every_reference_resolves_into_the_bundle(ctx):
    side = json.loads(SIDECAR.read_text(encoding="utf-8"))
    for p in side["points"]:
        assert p["supplement_ref"] in ctx.facts, p["id"]
    for q in side["faq"]:
        assert q["answer_ref"] in ctx.facts, q["id"]
    assert ctx.warnings == []


def test_guide_wording_has_no_verdict_words_and_asks_for_nothing_personal():
    side = json.loads(SIDECAR.read_text(encoding="utf-8"))
    texts = list(strings(side["guide"])) + [HOMEWORK_REPLY, safety.PII_REPLY, safety.DISTRESS_REPLY, safety.UNSAFE_REPLY]
    for t in texts:
        for w in evaluator.BANNED_WORDS:
            assert w not in t, (t, w)
        assert not re.search(r"你叫什么|哪个学校|手机号|微信|住在哪", t), t
        assert not any(p in t for p in _NARRATOR_BANNED), t


def test_guide_wording_contains_no_dates_or_numbers():
    side = json.loads(SIDECAR.read_text(encoding="utf-8"))
    for t in strings(side["guide"]):
        assert not re.search(r"\d", t), t


def test_forbidden_entities_are_not_in_any_scripted_fact(ctx):
    for e in ctx.forbidden:
        for f in ctx.facts.values():
            assert e not in f.text, (e, f.id)


def test_evaluator_summaries_have_no_banned_words():
    for s in (evaluator._SUM_MANY, evaluator._SUM_SOME, evaluator._SUM_NONE, evaluator._SUM_EMPTY):
        for w in evaluator.BANNED_WORDS:
            assert w not in s
