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
                                  "<example_dialogue>", T.PROFILE_HEADER, "# 输出")]
    assert order == sorted(order), "# 输出 必须是最后一段：约束紧挨着用户消息才压得住角色卡的体量"
    assert "{{char}}" not in s and "{{user}}" not in s
    assert (1, "她刚刚擦完杯子。") in [(i.depth, i.text) for i in plan.injections]
    assert (0, "保持角色。") in [(i.depth, i.text) for i in plan.injections]
    assert set(plan.lore_uids) == {"a", "b", "d"}


def test_cue_snippet_is_injected_on_the_voice_channel_only():
    """cue JSON 是语音通道的协议：文字聊天不该被要求输出它。

    生产里文字气泡出现过整行 `{"say":…}`：约束挂了所有通道，而文字通道的
    token 流不经过断句器与 cue 解析，原样进了气泡。语音侧仍需要它——
    字幕与 presentation.* 都从 say/cues 来。
    """
    voice = build_prompt_plan(_profile(), channel="voice")
    assert any(i.depth == 0 and i.text == T.CUE_OUTPUT_SNIPPET for i in voice.injections)

    text = build_prompt_plan(_profile(), channel="text")
    assert not any(i.text == T.CUE_OUTPUT_SNIPPET for i in text.injections)
    assert T.CUE_OUTPUT_SNIPPET not in text.system


def test_text_channel_bans_writing_the_protocol_shape_itself():
    """清洗器兜住已经冒出来的协议行，提示词这层还要把它按名禁掉。

    2026-11-20 的实际泄漏路径：协议片段进了 checkpointer 线程历史，下一轮
    文字回合的模型看见自己「写过」`{"say":…}` 就照抄。历史删不掉，
    所以文字通道要明说那种形状不是给用户写的。
    """
    text = build_prompt_plan(_profile(), channel="text")
    # 文字通道里 CUE_OUTPUT_SNIPPET 已确认不在；此时系统层里唯一能出现
    # `"say"` 的合法位置就是这条禁令本身。
    assert '"say"' in text.system
    assert "协议" in T.TEXT_CHANNEL_RULE or "语音通道" in T.TEXT_CHANNEL_RULE


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
    texts = [(i.depth, i.text) for i in plan.injections]
    assert (4, "林澈在想心事") in texts
    assert (3, "描写要细腻") in texts


def test_method_layer_is_part_of_the_role_section():
    plan = build_prompt_plan(_profile(method="先倾听再回应。"))
    assert T.METHOD_HEADER in plan.system and plan.system.index(T.METHOD_HEADER) < plan.system.index("# 输出")


def test_rtl_locale_adds_the_rtl_rule():
    assert T.RTL_RULE in build_prompt_plan(_profile(), locale="ar-SA").system


def test_cue_snippet_teaches_the_intensity_limit():
    """§18.6：intensity 给了模型就容易滥用（"强度 1.0 的狂喜"）。

    编译期钳制（B7）兜住越界值，但 prompt 也要写明区间与「默认省略」——
    少让模型写它，比每次帮它擦掉更好。这条锁住那段话还在。
    """
    assert "intensity" in T.CUE_OUTPUT_SNIPPET
    assert "0..1" in T.CUE_OUTPUT_SNIPPET
