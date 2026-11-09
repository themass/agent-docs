"""系统提示词组装（纯函数，无 I/O）。层序与预算见 P §6.1。

预算以字符计，近似：中文约 1 字符 ≈ 0.7 token。超出预算的层截断并标记，而不是整体失败。
"""

from __future__ import annotations

from dataclasses import dataclass

from companion.domain.prompt import templates as T

LAYER_BUDGET_CHARS = {
    "role": 1500,      # 角色层 ≤ 1500 token（P §6.1，修订后）
    "method": 900,
    "task": 900,
    "profile": 1200,
}


@dataclass(frozen=True)
class SystemPrompt:
    text: str
    version: str
    truncated_layers: tuple[str, ...]


def _clip(name: str, text: str, truncated: list[str]) -> str:
    budget = LAYER_BUDGET_CHARS[name]
    if len(text) <= budget:
        return text
    truncated.append(name)
    return text[:budget].rstrip() + "…"


def assemble_system_prompt(
    *,
    persona: str,
    role_constraints: list[str] | None = None,
    method: str = "",
    task: str = "",
    locale: str = "zh-CN",
    channel: str = "text",
    profile: str = "",
    memory_lines: list[str] | None = None,
) -> SystemPrompt:
    truncated: list[str] = []
    parts: list[str] = [T.PLATFORM_LAYER]

    role_text = persona.strip()
    if role_constraints:
        role_text += "\n\n" + "\n".join(f"- {c}" for c in role_constraints)
    parts.append(f"{T.ROLE_HEADER}\n\n{_clip('role', role_text, truncated)}")

    if method.strip():
        parts.append(f"{T.METHOD_HEADER}\n\n{_clip('method', method.strip(), truncated)}")
    if task.strip():
        parts.append(f"{T.TASK_HEADER}\n\n{_clip('task', task.strip(), truncated)}")

    language = "会话语言（" + locale + "）"
    channel_rule = T.VOICE_CHANNEL_RULE if channel == "voice" else T.TEXT_CHANNEL_RULE
    output = T.OUTPUT_TEMPLATE.format(language=language, channel_rule=channel_rule)
    if locale.split("-")[0] in T.RTL_LOCALES:
        output += "\n- " + T.RTL_RULE
    parts.append(output)

    user_bits = []
    if profile.strip():
        user_bits.append(_clip("profile", profile.strip(), truncated))
    if memory_lines:
        user_bits.append("<user_memories>\n" + "\n".join(f"- {m}" for m in memory_lines) + "\n</user_memories>")
    if user_bits:
        parts.append(f"{T.PROFILE_HEADER}\n\n" + "\n".join(user_bits))

    return SystemPrompt(text="\n\n".join(parts), version=T.PROMPT_VERSION, truncated_layers=tuple(truncated))
