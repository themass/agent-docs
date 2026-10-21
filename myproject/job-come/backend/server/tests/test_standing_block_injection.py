"""The session's standing instructions arrive once, as system content.

Background: every turn's `HumanMessage` used to carry the reply-language rule,
the conduct rules, a task header and (on the first turn) the whole role-family
methodology, ahead of the user's own words. Two of those were *also* injected as
system content by this middleware, so the model received them twice per turn in
two voices, and the live question sat several thousand characters down.

These tests pin the contract of the fix: the standing text is in the system
reminder, it is stated once, it is selected from this run's own
`authz_attributes` (never process-global state -- ADR-004), and a non-resume
skill is not handed resume rewriting methodology.
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage

from jc.deerflow_middleware import JCProductRulesMiddleware, _build_reminder

_LANGUAGE_RULE = "你必须全程使用简体中文回复"
_CONDUCT_RULE = "不要调用 ask_clarification"
_BULLET_METHOD = "动作 + 对象 + 结果"


class _Runtime:
    """A LangGraph runtime carrying one run's context, as the graph resolves it."""

    def __init__(self, **attributes: Any) -> None:
        self.context = {"authz_attributes": {k: v for k, v in attributes.items() if v}}


def test_the_reply_language_rule_is_sent_exactly_once() -> None:
    reminder = _build_reminder(
        _Runtime(jc_agent_skill="resume-coach", jc_reply_locale="zh-CN")
    )

    assert reminder.count(_LANGUAGE_RULE) == 1
    # And it is inside the standing block rather than its own former section.
    assert "<reply_language>" not in reminder
    assert "<session_instructions>" in reminder


def test_each_conduct_rule_is_sent_exactly_once() -> None:
    reminder = _build_reminder(
        _Runtime(jc_agent_skill="resume-coach", jc_profile_id="prof_1")
    )

    assert reminder.count(_CONDUCT_RULE) == 1
    # The bare `key=value` abbreviations of these rules are gone: a flag the
    # model has to interpret is strictly weaker than the sentence it replaced.
    assert "do_not_introduce" not in reminder
    assert "ask_clarification_when_facts_missing" not in reminder


def test_an_english_session_gets_the_english_rule_and_not_the_chinese_one() -> None:
    reminder = _build_reminder(
        _Runtime(jc_agent_skill="resume-coach", jc_reply_locale="en-US")
    )

    assert "You MUST reply in English only" in reminder
    assert _LANGUAGE_RULE not in reminder


def test_the_role_family_comes_from_this_runs_attributes() -> None:
    """The agent is cached per process and shared across users, so the
    methodology cannot be baked in at build time -- it is selected per run."""
    backend = _build_reminder(
        _Runtime(jc_agent_skill="resume-coach", jc_role_family="backend")
    )
    legal = _build_reminder(
        _Runtime(jc_agent_skill="resume-coach", jc_role_family="legal")
    )

    assert "后端 / 服务端研发" in backend
    assert "后端 / 服务端研发" not in legal
    assert "法务" in legal
    # A family whose outcomes are usually qualitative must not be told to chase
    # a metric, and the quantitative family must not get that licence.
    assert "这个岗位的成果常常没有数字" in legal
    assert "这个岗位的成果常常没有数字" not in backend


def test_an_unknown_family_falls_back_to_the_neutral_methodology() -> None:
    reminder = _build_reminder(_Runtime(jc_agent_skill="resume-coach"))

    assert _BULLET_METHOD in reminder
    assert "这个岗位族怎么写" not in reminder


def test_a_non_resume_skill_is_not_handed_resume_methodology() -> None:
    """A mock-interview turn has its own task shape. It still gets the conduct
    rules and the language, because those are true of every JC session."""
    reminder = _build_reminder(
        _Runtime(jc_agent_skill="coach-mock", jc_role_family="backend")
    )

    assert _BULLET_METHOD not in reminder
    assert "改写方法" not in reminder
    assert "本会话任务" not in reminder
    assert _CONDUCT_RULE in reminder
    assert reminder.count(_LANGUAGE_RULE) == 1


def test_the_interview_skill_is_framed_as_an_interview() -> None:
    reminder = _build_reminder(_Runtime(jc_agent_skill="profile-interview"))

    assert "建档访谈" in reminder
    assert "简历优化：" not in reminder


def test_the_standing_block_is_injected_as_system_content_once_per_thread() -> None:
    """It rides the system reminder, which is frozen on the first user turn."""
    mw = JCProductRulesMiddleware()
    runtime = _Runtime(jc_agent_skill="resume-coach", jc_role_family="backend")

    first = mw.before_agent({"messages": [HumanMessage(content="这段丰富一点")]}, runtime)
    injected = first["messages"]
    system_text = "".join(
        str(m.content) for m in injected if not isinstance(m, HumanMessage)
    )
    assert _BULLET_METHOD in system_text
    # The user's turn is copied through untouched: no policy is prepended to it.
    user = next(m for m in injected if isinstance(m, HumanMessage))
    assert user.content == "这段丰富一点"

    # A second pass over a thread that already carries the reminder adds nothing.
    assert mw.before_agent({"messages": injected}, runtime) == {}
