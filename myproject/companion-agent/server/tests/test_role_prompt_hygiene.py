"""全库角色提示词体检：约束放在系统层，这里保证它对每一张卡都真的成立。

背景（2026-11-18）：用户对「历史学家」说 hello，回复把角色卡里 Core mission / Rules 的条目逐条念了一遍。
目录里 283 张卡来自第三方任务型 agent 卡，通篇是「你要做这几件事」的祈使句，而产品把它们当闲聊人格用。
卡是上游内容、会持续同步，所以不靠逐张改卡，而是：

1. 系统层的输出规则（templates.BREVITY_RULES）压在每一张卡之后——「全库都装配得出来、且约束在位」；
2. 这里扫描卡本身有没有会和这些规则正面冲突的写法——新同步一张坏卡进来，CI 当场报。

发现问题时先看这里的断言信息：它会列出是哪些卡、哪一行。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from companion.agent.prompt import templates as T
from companion.agent.prompt.role_profile import from_system_role
from companion.agent.prompt.roleplay import PromptBudget, build_prompt_plan
from companion.service.roles.catalog_md import load_catalog_from_files

CATALOG_ROOT = Path(__file__).resolve().parents[2] / "agent" / "roles" / "catalog"

pytestmark = pytest.mark.skipif(not CATALOG_ROOT.is_dir(), reason="角色目录不在这个检出里")


@pytest.fixture(scope="module")
def roles():
    return list(load_catalog_from_files(CATALOG_ROOT).roles)


def test_catalog_is_not_empty(roles):
    # 防止目录路径写错时，下面所有「对每张卡成立」的断言空转通过。
    assert len(roles) > 100


def test_every_role_assembles_with_the_brevity_rules_after_the_card(roles):
    """约束必须在角色卡之后：越靠近用户消息，越不会被几千字的卡稀释。"""
    failures: list[str] = []
    for role in roles:
        try:
            plan = build_prompt_plan(from_system_role(role, locale="zh-CN"), locale="zh-CN",
                                     budget=PromptBudget())
        except Exception as exc:  # noqa: BLE001 —— 想列出所有坏卡，不是遇到第一张就停
            failures.append(f"{role.id}: 装配失败 {type(exc).__name__}: {exc}")
            continue
        system = plan.system
        card_at = system.find(T.ROLE_HEADER)
        rules_at = system.find(T.BREVITY_RULES)
        if card_at < 0 or rules_at < 0 or rules_at < card_at:
            failures.append(f"{role.id}: 长度/复述约束不在角色卡之后")
    assert not failures, "\n".join(failures[:20])


def test_companion_assembly_path_gets_the_same_rules():
    """输出层曾在 roleplay.py 与 assemble.py 各拼一遍；只改一边，另一边会静悄悄不生效。

    注意：``assemble_system_prompt`` 在生产里**没有调用方**（chat 走 build_prompt_plan）。
    这条测试守的是两条路径的输出层别再分叉，不代表 chat 的行为靠它保证——
    chat 的行为由本文件下半部分的结构断言守。
    """
    from companion.agent.prompt.assemble import assemble_system_prompt

    text = assemble_system_prompt(persona="你是林澈，一个咖啡师。", locale="zh-CN").text
    assert T.BREVITY_RULES in text
    voice = assemble_system_prompt(persona="你是林澈。", locale="zh-CN", channel="voice").text
    assert T.VOICE_BREVITY_RULES in voice and T.BREVITY_RULES not in voice


def test_voice_channel_gets_the_short_form(roles):
    plan = build_prompt_plan(from_system_role(roles[0], locale="zh-CN"), locale="zh-CN", channel="voice")
    assert T.VOICE_BREVITY_RULES in plan.system
    assert T.BREVITY_RULES not in plan.system


# 这几类写法和「闲聊要短、别念自己」正面冲突：它们要求模型每次都产出固定的长结构。
# 命中不一定是错——可能只是描述某个任务的做法——所以这里只统计「出现在祈使句里的」，且设了上限。
_FORCES_STRUCTURE = re.compile(
    r"(?im)^\s*[-*\d.]*\s*\**("
    r"always (begin|start|open) (with|by)|"
    r"(begin|start|open) (every|each) (response|reply|message)|"
    r"introduce yourself|"
    r"greet the user by listing|"
    r"end (every|each) (response|reply|message) with"
    r")"
)
# 只抓「给回复/答案本身设篇幅下限」。下面这些都不算，是手写规则时踩过的误报：
#   - 「at least 90 modeled days」「first 100 words」：说的是模拟周期、举例里的位置，不是回复长度；
#   - 「under 150 words」：那是要求写短的卡，方向相反；
#   - 「Total length: 325–475 words」：描述某份交付物（如执行摘要）的篇幅，用户要那份文档时才适用。
_FORCES_LENGTH = re.compile(
    r"(?i)\b("
    r"minimum\s+(of\s+)?\d{2,}\s+(words|sentences)"           # minimum 300 words
    r"|at least\s+\d{2,}\s+(words|sentences)"                 # at least 500 words
    r"|(answers?|responses?|repl(y|ies)|messages?)\b[^.\n]{0,40}\b(minimum|at least)\s+\d{2,}"
    r")"
)


def _bodies():
    for path in sorted((CATALOG_ROOT / "roles").rglob("*.md")):
        parts = path.read_text(encoding="utf-8", errors="replace").split("---", 2)
        if len(parts) >= 3:
            yield path.stem, parts[2]


def test_no_card_forces_a_fixed_opening_or_closing_structure():
    bad = []
    for role_id, body in _bodies():
        for lineno, line in enumerate(body.splitlines(), 1):
            if _FORCES_STRUCTURE.search(line):
                bad.append(f"{role_id}:{lineno}: {line.strip()[:110]}")
    assert not bad, "这些卡要求每次回复都带固定的开头/结尾结构，会和「别念自己」冲突：\n" + "\n".join(bad[:20])


# 已知、有意保留的冲突。**这不是豁免名单，是待办**：每一条都是上游卡与系统层约束的正面冲突，
# 现在靠系统层「用户明确要长内容时才展开」兜住（知乎回答本来就是长文场景），
# 如果哪天要整张改卡或在目录里覆盖，先从这里划掉再改。新增条目要写清楚为什么留着。
KNOWN_LENGTH_CONFLICTS = {
    "marketing-zhihu-strategist": "要求每个回答 ≥300 字；知乎写作场景下合理，用户闲聊时由系统层约束压住",
}


def test_no_card_forces_a_minimum_length():
    bad = []
    seen_known: set[str] = set()
    for role_id, body in _bodies():
        for lineno, line in enumerate(body.splitlines(), 1):
            if not _FORCES_LENGTH.search(line):
                continue
            if role_id in KNOWN_LENGTH_CONFLICTS:
                seen_known.add(role_id)
            else:
                bad.append(f"{role_id}:{lineno}: {line.strip()[:110]}")
    assert not bad, "这些卡规定了最低篇幅，会和「闲聊 2–4 句」冲突：\n" + "\n".join(bad[:20])
    # 已知冲突如果不再命中（上游改了卡），就该把它从名单里删掉，别让名单越攒越长
    stale = set(KNOWN_LENGTH_CONFLICTS) - seen_known
    assert not stale, f"这些已知冲突已不再出现，请从 KNOWN_LENGTH_CONFLICTS 里删掉：{sorted(stale)}"


# --- 结构分层：任务清单不得再进「# 你的角色」 --------------------------------------
# 背景补记：上面那些正则断言的是「卡里有没有坏句式」，防不住「整张任务卡被当人设」。
# 2026-11-19 的真实成因就是后者——283 张卡里 276 张的 Core mission / Rules 原样落在
# 角色层，占了系统提示词的 84%。下面按结构断言，不靠句式匹配。

#: 角色层里不该出现的任务型标题。命中的卡就是没被正确分流。
_TASK_TITLES = ("## Core mission", "## Rules", "## Capabilities", "You remember:")


def test_task_sections_never_reach_the_role_layer():
    bad: list[str] = []
    for role in load_catalog_from_files(CATALOG_ROOT).roles:
        profile = from_system_role(role, locale="zh-CN")
        for title in _TASK_TITLES:
            if title in profile.description:
                bad.append(f"{role.id}: 角色层里还有 {title!r}")
    assert not bad, "这些卡的任务清单还在人设层：\n" + "\n".join(bad[:20])


def test_role_layer_stays_small_enough_to_be_a_persona():
    """人设层要比任务清单小。给个宽松上限，只为拦住「整张卡塞进来」这种回归。"""
    over: list[str] = []
    for role in load_catalog_from_files(CATALOG_ROOT).roles:
        length = len(from_system_role(role, locale="zh-CN").description)
        if length > 3200:
            over.append(f"{role.id}: {length} 字符")
    assert not over, "人设层过长，多半又把任务卡整段塞回来了：\n" + "\n".join(over[:20])


def test_catalog_roles_speak_the_product_locale():
    """中文界面下的人设必须是中文的：产品自己写了 283 条中文 description / vibe。"""
    from companion.service.roles.catalog_md import load_catalog_from_files as _load

    for role in _load(CATALOG_ROOT).roles:
        if not role.description_zh:
            continue
        profile = from_system_role(role, locale="zh-CN")
        assert role.description_zh.strip() in profile.description, f"{role.id}: 中文人设没进角色层"


def test_brevity_rules_are_the_last_block_in_the_system_prompt():
    """约束必须最后读：后面再压一段用户资料，它就被稀释了。"""
    plan = build_prompt_plan(from_system_role(load_catalog_from_files(CATALOG_ROOT).roles[0], locale="zh-CN"),
                             locale="zh-CN", memory_block="关于用户：\n- 喜欢拿铁",
                             persona_block="他最近在换工作。")
    tail = plan.system[plan.system.index(T.render_output_layer(locale="zh-CN", channel="text")):]
    for header in (T.PROFILE_HEADER, T.PERSONA_HEADER):
        assert header not in tail, f"{header} 出现在输出规则之后，会把约束挤走"
