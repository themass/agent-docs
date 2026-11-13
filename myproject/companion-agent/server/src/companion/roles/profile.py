"""提示词用的统一角色视图。

角色有三个来源（P §4）：目录角色（SystemRole）、陪伴角色卡（CharacterCard，SillyTavern V2/V3）、
用户自建角色（只有一段提示词）。提示词引擎只认 RoleProfile，来源之间的差异在这里抹平。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from companion.lorebook import Lorebook, from_character_book
from companion.prompt.plan import ROLES, DepthInjection
from companion.roles.card import CharacterCard
from companion.roles.catalog import SystemRole


@dataclass(frozen=True)
class RoleProfile:
    role_id: str
    name: str
    description: str
    personality: str = ""
    scenario: str = ""
    system_override: str = ""      # 卡片 system_prompt；只补充角色指令，不覆盖平台安全规则
    post_history: str = ""         # 卡片 post_history_instructions；放在历史之后
    examples: str = ""             # 卡片 mes_example 原文（<START> 分块）
    lorebook: Lorebook | None = None
    depth_prompt: DepthInjection | None = None
    method: str = ""               # skill 的方法层常驻段（P §5），由解析方填入
    skills: tuple[str, ...] = ()   # method 实际由哪些 skill 合成（含常驻的），质检用
    source: str = "catalog"        # catalog | companion | user


def _depth_prompt(extensions: dict[str, Any]) -> DepthInjection | None:
    raw = extensions.get("depth_prompt")
    if not isinstance(raw, dict):
        return None
    text = str(raw.get("prompt") or "").strip()
    if not text:
        return None
    try:
        depth = max(0, int(raw.get("depth", 4)))
    except (TypeError, ValueError):
        depth = 4
    role = str(raw.get("role") or "system")
    return DepthInjection(depth=depth, role=role if role in ROLES else "system", text=text)


def from_card(card: CharacterCard) -> RoleProfile:
    return RoleProfile(
        role_id=card.id,
        name=card.name,
        description=card.description,
        personality=card.personality,
        scenario=card.scenario,
        system_override=card.system_prompt,
        post_history=card.post_history_instructions,
        examples=card.mes_example,
        lorebook=from_character_book(card.character_book),
        depth_prompt=_depth_prompt(card.extensions),
        source="companion",
    )


def from_system_role(role: SystemRole, *, locale: str = "zh-CN") -> RoleProfile:
    name = role.name_zh if locale.startswith("zh") and role.name_zh else role.name
    return RoleProfile(role_id=role.id, name=name, description=role.prompt, source="catalog")


def from_user_prompt(*, role_id: str, name: str, prompt: str) -> RoleProfile:
    return RoleProfile(role_id=role_id, name=name, description=prompt, source="user")
