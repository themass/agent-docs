"""提示词计划：按深度注入、角色扮演组装顺序、预算与宏。"""

import pytest

from companion.agent.lorebook import LoreEntry, Lorebook
from companion.agent.prompt import templates as T
from companion.agent.prompt.plan import DepthInjection, splice_injections
from companion.agent.prompt.roleplay import (
    AuthorNote,
    PromptBudget,
    PromptBudgetExceeded,
    build_prompt_plan,
)
from companion.agent.prompt.role_profile import RoleProfile


def _make(role, text):
    return (role, text)


def test_depth_zero_goes_after_the_last_message_and_depth_n_before_the_nth_newest():
    msgs = ["u1", "a1", "u2", "a2"]
    out = splice_injections(msgs, [DepthInjection(0, "system", "PHI"), DepthInjection(2, "system", "D2")], _make)
    assert out == ["u1", "a1", ("system", "D2"), "u2", "a2", ("system", "PHI")]


def test_same_depth_groups_by_order_then_merges_by_role():
    out = splice_injections(["m"], [
        DepthInjection(1, "user", "low-user", order=10),
        DepthInjection(1, "system", "high-sys", order=90),
        DepthInjection(1, "system", "low-sys-1", order=10),
        DepthInjection(1, "system", "low-sys-2", order=10),
    ], _make)
    assert out == [("system", "high-sys"), ("system", "low-sys-1\n\nlow-sys-2"), ("user", "low-user"), "m"]


def test_depth_beyond_history_lands_at_the_start():
    assert splice_injections(["m"], [DepthInjection(9, "system", "far")], _make) == [("system", "far"), "m"]


def _profile(**kw) -> RoleProfile:
    base = dict(role_id="r1", name="林澈", description="{{char}}是一名咖啡师，叫{{user}}「朋友」。",
                personality="温和", scenario="雨天的咖啡馆")
    base.update(kw)
    return RoleProfile(**base)


def test_roleplay_plan_orders_blocks_and_keeps_platform_rules_first():
    lore = Lorebook(entries=(
        LoreEntry(uid="b", keys=("咖啡",), content="店里只卖手冲。", position="before_char"),
        LoreEntry(uid="a", keys=("咖啡",), content="老板姓周。", position="after_char"),
        LoreEntry(uid="d", keys=("咖啡",), content="她刚刚擦完杯子。", position="at_depth", depth=1),
    ))
    plan = build_prompt_plan(
        _profile(lorebook=lore, system_override="说话简短。", post_history="保持角色。",
                 examples="<START>\n{{user}}: 你好\n{{char}}: 欢迎。"),
        user_name="小明", recent_texts=("来杯咖啡",), memory_block="关于用户：\n- 喜欢拿铁")
    s = plan.system
    assert s.startswith(T.PLATFORM_LAYER)
    order = [s.index(x) for x in ("店里只卖手冲", T.ROLE_HEADER, "说话简短", "林澈是一名咖啡师，叫小明", "老板姓周",
                                  "<example_dialogue>", "# 输出", T.PROFILE_HEADER)]
    assert order == sorted(order)
    assert "{{char}}" not in s and "{{user}}" not in s
    assert [(i.depth, i.text) for i in plan.injections] == [(1, "她刚刚擦完杯子。"), (0, "保持角色。")]
    assert set(plan.lore_uids) == {"a", "b", "d"}


def test_mandatory_overflow_is_an_error_not_a_silent_truncation():
    with pytest.raises(PromptBudgetExceeded):
        build_prompt_plan(_profile(description="长" * 5000), budget=PromptBudget(system_chars=2000))


def test_optional_blocks_are_dropped_examples_first():
    examples = "<START>\n" + "例" * 900
    profile = _profile(examples=examples)
    base = len(build_prompt_plan(profile, budget=PromptBudget(system_chars=100_000)).system) - len(examples)
    plan = build_prompt_plan(profile, memory_block="记忆" * 50,
                             budget=PromptBudget(system_chars=base + 150, examples_chars=2000))
    assert "examples" in plan.dropped and "<example_dialogue>" not in plan.system
    assert "记忆" in plan.system


def test_author_note_and_depth_prompt_become_injections():
    plan = build_prompt_plan(_profile(depth_prompt=DepthInjection(4, "system", "{{char}}在想心事")),
                             author_note=AuthorNote("描写要细腻", depth=3))
    assert [(i.depth, i.text) for i in plan.injections] == [(4, "林澈在想心事"), (3, "描写要细腻")]


def test_method_layer_is_part_of_the_role_section():
    plan = build_prompt_plan(_profile(method="先倾听再回应。"))
    assert T.METHOD_HEADER in plan.system and plan.system.index(T.METHOD_HEADER) < plan.system.index("# 输出")


def test_rtl_locale_adds_the_rtl_rule():
    assert T.RTL_RULE in build_prompt_plan(_profile(), locale="ar-SA").system
