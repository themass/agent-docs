"""角色有自己的说话方式，而不是服务端在判断用户说了什么。

2026-11-20 用户否决了「按招呼词表压 ``max_tokens``」那套设计：那是在替模型理解对话，
而且它让每个角色的回复都长成一个样。长度不该由服务端判断，而该由**这个人是谁**决定。

所以「怎么说话」要真的进提示词：
1. 目录卡的 ``## Communication style`` 摘出来挂在角色层末尾——它写的是语气与句式（带引号例句），
   本来就是性格，比任何「回复要简短」的元指令更能定住一个人说话的样子；
2. 输出层说清「设定不是台词」，但不再对用户输入下判断。

这里断言第 1 条真的到得了模型面前，第 2 条不再出现旧写法。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from companion.agent.prompt import templates as T
from companion.agent.prompt.role_profile import from_system_role, split_card_prompt
from companion.agent.prompt.roleplay import PromptBudget, build_prompt_plan
from companion.service.roles.catalog_md import load_catalog_from_files

CATALOG_ROOT = Path(__file__).resolve().parents[2] / "agent" / "roles" / "catalog"

pytestmark = pytest.mark.skipif(not CATALOG_ROOT.is_dir(), reason="角色目录不在这个检出里")


# --- 拆分：说话方式单独摘出来，不混进方法层 ---------------------------------------

_CARD = """\
我是做用户研究的，习惯先问再下结论。

## Identity
- **Role**: UX researcher
- **Personality**: Patient and curious.

## Core mission
Run studies.

## Rules
1. Ask before assuming.

## Communication style
- Says "我先问一句，你说的『卡住』具体是哪一步？" instead of proposing a fix.
- Admits uncertainty out loud: "这个我还没有证据。"
"""


def test_the_style_section_is_its_own_output():
    persona, method, style = split_card_prompt(_CARD)
    assert "UX researcher" in persona
    assert "Run studies" in method
    # 说话方式既不在人设里（会被任务清单淹掉），也不在方法层（那是工作流程）。
    assert "我先问一句" not in persona and "我先问一句" not in method
    assert "我先问一句" in style and "这个我还没有证据" in style


def test_the_style_section_does_not_keep_its_heading():
    """调用方会加自己的标题；重复两层标题只会让模型去复述标题。"""
    _, _, style = split_card_prompt(_CARD)
    assert "Communication style" not in style


def test_a_card_without_a_style_section_still_works():
    persona, method, style = split_card_prompt("## Identity\n- Role: x\n\n## Rules\n1. y")
    assert persona and method
    assert style == ""


def test_style_and_task_sections_are_not_confused():
    """两个标题都以 C 开头，别用前缀匹配把它们搞混。"""
    _, method, style = split_card_prompt(
        "## Capabilities\n- does things\n\n## Communication style\n- talks like this")
    assert "does things" in method and "talks like this" not in method
    assert "talks like this" in style and "does things" not in style


# --- 装配：说话方式必须到得了模型面前 ---------------------------------------------

def _first_role_with_style(roles):
    for role in roles:
        if "## Communication style" in role.prompt:
            return role
    pytest.skip("目录里没有带 Communication style 的卡")


def test_the_style_block_lands_in_the_system_prompt():
    roles = load_catalog_from_files(CATALOG_ROOT).roles
    role = _first_role_with_style(roles)
    plan = build_prompt_plan(from_system_role(role, locale="zh-CN"), locale="zh-CN")
    assert T.VOICE_SAMPLE_HEADER in plan.system


def test_the_style_block_survives_a_tight_budget():
    """它是角色层的一部分，不是可选层——预算紧张时也不该被丢掉。

    丢掉它，模型剩下的就只有 Core mission / Rules，那正是「对着 hello 念任务清单」的起点。
    """
    roles = load_catalog_from_files(CATALOG_ROOT).roles
    role = _first_role_with_style(roles)
    tight = PromptBudget(system_chars=20000, examples_chars=1, lore_chars=1, memory_chars=1, persona_chars=1)
    plan = build_prompt_plan(from_system_role(role, locale="zh-CN"), locale="zh-CN",
                             memory_block="记忆" * 500, budget=tight)
    assert T.VOICE_SAMPLE_HEADER in plan.system


def test_the_style_block_sits_after_the_persona():
    """顺序：先知道这是谁，再知道这个人怎么说话。"""
    roles = load_catalog_from_files(CATALOG_ROOT).roles
    role = _first_role_with_style(roles)
    plan = build_prompt_plan(from_system_role(role, locale="zh-CN"), locale="zh-CN")
    assert plan.system.find(T.ROLE_HEADER) < plan.system.find(T.VOICE_SAMPLE_HEADER)


def test_companion_cards_without_a_style_section_are_unaffected():
    """陪伴角色卡没有这个段落，行为与以前一致：不凭空多出一段。"""
    from companion.agent.prompt.role_profile import RoleProfile

    plan = build_prompt_plan(RoleProfile(role_id="x", name="林澈", description="一个教练。"),
                             locale="zh-CN")
    assert T.VOICE_SAMPLE_HEADER not in plan.system


# --- 输出层不再替模型判断用户输入 -------------------------------------------------

def test_the_output_layer_does_not_judge_whether_the_user_is_greeting():
    """旧写法按消息种类给指令（「一句招呼就回一两句」），那是在替模型理解对话。"""
    for channel in ("text", "voice"):
        text = T.render_output_layer(locale="zh-CN", channel=channel)
        for forbidden in ("招呼", "寒暄", "hello", "问「你能做什么」"):
            assert forbidden not in text, f"{channel} 输出层还在判断用户输入：{forbidden!r}"


def test_the_output_layer_says_the_persona_is_not_a_script():
    text = T.render_output_layer(locale="zh-CN", channel="text")
    assert "不是「你要说的话」" in text


def test_the_voice_layer_stays_short_and_spoken():
    text = T.render_output_layer(locale="zh-CN", channel="voice")
    assert "口语" in text


def test_prompt_version_moved_with_the_change():
    """提示词内容变了就得换版本号：chat_turn 记着它是事后归因的唯一依据。"""
    assert T.PROMPT_VERSION >= "2026-11-20"
