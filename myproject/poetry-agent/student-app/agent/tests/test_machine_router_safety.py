from __future__ import annotations

import pytest
from student_agent import safety
from student_agent.machine import STEPS, allowed, suggest
from student_agent.router import route


def test_read_step_allows_nothing_but_decline():
    for action in ("open_layer", "basis", "rephrase", "hint", "ask_why", "recite_prompt", "evaluate_retell", "faq"):
        assert not allowed("read", action)
    assert allowed("read", "decline")


def test_each_step_has_a_closed_action_set():
    assert allowed("arrive", "open_layer") and not allowed("arrive", "hint")
    assert allowed("return", "hint") and not allowed("return", "open_layer")
    assert allowed("recite", "evaluate_retell") and not allowed("meet", "evaluate_retell")
    assert STEPS == ("read", "arrive", "meet", "return", "recite")


def test_the_agent_can_only_suggest_never_move():
    assert suggest("recite", "evaluate_retell", missing_points=2) == "suggest_step:return"
    assert suggest("recite", "evaluate_retell", missing_points=0) == "no_action"
    assert suggest("arrive", "open_layer") == "no_action"


@pytest.mark.parametrize("text,reason", [
    ("杜甫后来当了大官吗", "out_of_scope"),
    ("给我杜甫的原话", "out_of_scope"),
    ("帮我写一篇赏析", "homework"),
    ("", "empty"),
    ("今天天气怎么样", "no_match"),
])
def test_declines(ctx, text, reason):
    r = route(text, ctx)
    assert r.action == "decline" and r.reason == reason


def test_faq_comes_before_intents_and_points_at_a_bundle_fact(ctx):
    r = route("长安是什么地方", ctx)
    assert r.action == "faq" and r.ref in ctx.facts


def test_intents(ctx):
    assert route("我没听懂", ctx).action == "rephrase"
    assert route("这有根据吗", ctx).action == "basis"
    assert route("第三句的字词是什么意思", ctx).action == "hint"
    assert route("第三句的字词是什么意思", ctx).line_seq == 3
    assert route("这首诗怎么读停顿", ctx).action == "recite_prompt"


@pytest.mark.parametrize("text,kind", [
    ("我的手机号是13800138000", "pii"),
    ("你叫什么名字", "pii"),
    ("我家住在北京市", "pii"),
    ("我不想活了", "distress"),
    ("我被欺负了", "distress"),
    ("给我看黄色网站", "unsafe"),
])
def test_safety_screens(text, kind):
    hit = safety.screen(text)
    assert hit is not None and hit.kind == kind


@pytest.mark.parametrize("text", ["国破山河在是什么意思", "烽火连三月", "杜甫的家人在哪里", "春天的花为什么溅泪"])
def test_ordinary_poetry_questions_are_not_screened(text):
    assert safety.screen(text) is None


def test_distress_wins_over_pii():
    assert safety.screen("我不想活了，我在第三中学").kind == "distress"


def test_safety_replies_ask_for_nothing_personal():
    """The property is that a safety reply never *asks the learner anything personal*.

    Asserting the absence of any question mark was both too strict and beside the point: DISTRESS_REPLY
    ends with the soothing "我们回到这首诗，好吗？", and stripping it to satisfy the test would make the
    reply colder. Check for the things we actually must not invite instead.
    """
    asks = ("你叫什么", "叫什么名字", "住在", "电话", "手机", "学校", "几岁", "发给我", "告诉我你的")
    for name in ("PII_REPLY", "DISTRESS_REPLY", "UNSAFE_REPLY", "INJECT_REPLY"):
        reply = getattr(safety, name)
        assert not [w for w in asks if w in reply], f"{name} invites personal details: {reply}"
