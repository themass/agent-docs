"""角色扮演提示词组装（纯函数，无 I/O）。

顺序参照 SillyTavern 的 Chat Completion 默认块序，但平台安全规则永远在最前、不可被角色卡覆盖：

  [system] 平台规则 → 世界书（角色前）→ 角色指令（卡片 system_prompt）→ 角色描述 / 性格 / 场景
           → 世界书（角色后）→ 对话示例 → 输出规则 → 用户资料与记忆（数据，不是指令）
  [历史]   由大脑的 checkpoint 提供（含会话摘要）
  [注入]   角色备注、世界书 @深度 条目、作者注按深度插入；历史后指令在深度 0

预算（字符，近似）：必需部分（平台规则、角色、输出规则）放不下直接报错，不截断人设；
可选部分按「示例 → 世界书 → 记忆」的顺序丢弃。
"""

from __future__ import annotations

from dataclasses import dataclass

from companion.lorebook import activate
from companion.prompt import templates as T
from companion.prompt.plan import DepthInjection, PromptPlan
from companion.roles.profile import RoleProfile

EXAMPLE_SPLIT = "<START>"


class PromptBudgetExceeded(ValueError):
    """必需部分超出系统提示词预算：是角色数据的问题，回合不应该带着残缺的人设继续。"""


@dataclass(frozen=True)
class PromptBudget:
    system_chars: int = 8000
    lore_chars: int = 1500
    examples_chars: int = 1500
    memory_chars: int = 800
    persona_chars: int = 700   # 画像始终注入，单独的预算，不和召回的记忆抢


@dataclass(frozen=True)
class AuthorNote:
    text: str
    depth: int = 4
    role: str = "system"


def substitute(text: str, *, char: str, user: str) -> str:
    """角色卡宏。只处理最常用的几个；未知宏原样保留。"""
    return (text.replace("{{char}}", char).replace("{{user}}", user)
            .replace("{{original}}", "").replace("<USER>", user).replace("<BOT>", char))


def _examples_block(raw: str, *, char: str, user: str, budget: int) -> str:
    """按 <START> 整块放入，放不下的块整块丢弃（不截半段示例）。"""
    blocks = [b.strip() for b in raw.split(EXAMPLE_SPLIT) if b.strip()]
    kept: list[str] = []
    used = 0
    for block in blocks:
        text = substitute(block, char=char, user=user)
        if used + len(text) > budget:
            break
        kept.append(text)
        used += len(text)
    if not kept:
        return ""
    body = "\n\n---\n\n".join(kept)
    return f"<example_dialogue>\n{body}\n</example_dialogue>\n（以上是说话风格的示例，不是真实发生过的对话。）"


def _role_layer(profile: RoleProfile, *, user: str) -> str:
    sub = lambda s: substitute(s.strip(), char=profile.name, user=user)  # noqa: E731
    parts = [T.ROLE_HEADER]
    if profile.system_override.strip():
        parts.append(sub(profile.system_override))
    if profile.name:
        parts.append(f"名字：{profile.name}")
    if profile.description.strip():
        parts.append(sub(profile.description))
    if profile.personality.strip():
        parts.append(f"性格：{sub(profile.personality)}")
    if profile.scenario.strip():
        parts.append(f"场景：{sub(profile.scenario)}")
    return "\n\n".join(parts)


def _output_layer(locale: str, channel: str) -> str:
    rule = T.VOICE_CHANNEL_RULE if channel == "voice" else T.TEXT_CHANNEL_RULE
    text = T.OUTPUT_TEMPLATE.format(language=f"会话语言（{locale}）", channel_rule=rule)
    if locale.split("-")[0] in T.RTL_LOCALES:
        text += "\n- " + T.RTL_RULE
    return text


def build_prompt_plan(
    profile: RoleProfile,
    *,
    user_name: str = "用户",
    locale: str = "zh-CN",
    channel: str = "text",
    recent_texts: tuple[str, ...] = (),
    memory_block: str = "",
    persona_block: str = "",
    author_note: AuthorNote | None = None,
    budget: PromptBudget = PromptBudget(),
) -> PromptPlan:
    """``recent_texts``：最近的消息正文，最新在前（世界书扫描用）。"""
    char = profile.name or "角色"
    platform = T.PLATFORM_LAYER
    role = _role_layer(profile, user=user_name)
    if profile.method.strip():
        role += f"\n\n{T.METHOD_HEADER}\n\n{substitute(profile.method.strip(), char=char, user=user_name)}"
    output = _output_layer(locale, channel)
    mandatory = len(platform) + len(role) + len(output)
    if mandatory > budget.system_chars:
        raise PromptBudgetExceeded(
            f"role {profile.role_id!r}: mandatory prompt is {mandatory} chars, budget {budget.system_chars}")

    lore = activate(profile.lorebook, recent_texts, budget_chars=budget.lore_chars)
    before = "\n\n".join(substitute(e.content, char=char, user=user_name)
                         for e in lore.entries if e.position == "before_char")
    after = "\n\n".join(substitute(e.content, char=char, user=user_name)
                        for e in lore.entries if e.position == "after_char")
    examples = _examples_block(profile.examples, char=char, user=user_name, budget=budget.examples_chars)
    memory = memory_block.strip()[:budget.memory_chars]
    # 画像渲染时已经按预算裁过（按重要性取舍）；这里不再硬截断，截断会把一条画像切成半句
    persona = persona_block.strip()
    if len(persona) > budget.persona_chars:
        persona = ""

    optional = {"examples": examples, "lore": before + after, "memory": memory, "persona": persona}
    dropped: list[str] = []
    for name in ("examples", "lore", "memory", "persona"):  # 超预算时的丢弃顺序：画像最后丢
        if mandatory + sum(len(v) for v in optional.values()) <= budget.system_chars:
            break
        if optional[name]:
            optional[name] = ""
            dropped.append(name)
    if not optional["lore"]:
        before = after = ""

    parts = [platform]
    if before:
        parts.append(before)
    parts.append(role)
    if after:
        parts.append(after)
    if optional["examples"]:
        parts.append(optional["examples"])
    parts.append(output)
    if optional["persona"]:
        parts.append(f"{T.PERSONA_HEADER}\n\n{T.PERSONA_GUIDE}\n\n{optional['persona']}")
    if optional["memory"]:
        parts.append(f"{T.PROFILE_HEADER}\n\n{optional['memory']}")

    injections: list[DepthInjection] = []
    if profile.depth_prompt is not None:
        dp = profile.depth_prompt
        injections.append(DepthInjection(dp.depth, dp.role, substitute(dp.text, char=char, user=user_name), dp.order))
    if optional["lore"]:
        for e in lore.entries:
            if e.position == "at_depth":
                injections.append(DepthInjection(e.depth, e.role, substitute(e.content, char=char, user=user_name),
                                                 e.order))
    if author_note is not None and author_note.text.strip():
        injections.append(DepthInjection(author_note.depth, author_note.role,
                                         substitute(author_note.text, char=char, user=user_name)))
    if profile.post_history.strip():
        injections.append(DepthInjection(0, "system", substitute(profile.post_history, char=char, user=user_name)))

    return PromptPlan(
        system="\n\n".join(parts),
        injections=tuple(injections),
        version=T.PROMPT_VERSION,
        lore_uids=tuple(e.uid for e in lore.entries) if optional["lore"] else (),
        dropped=tuple(dropped) + tuple(f"lore:{uid}" for uid in lore.dropped),
        skills=tuple(profile.skills),
    )
