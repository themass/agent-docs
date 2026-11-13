from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from companion.roles.port import CharacterSourcePort
from companion.roles.card import CharacterCard, from_v2_json, render_persona
from companion.prompt.instructions import build_instructions
from companion.skills.port import SkillCatalog


def skill_ids_of(card: CharacterCard) -> list[str]:
    """角色卡在 extensions.vvv.skill 里声明用哪些 skill 包。

    既接受单个字符串（老卡），也接受字符串列表（一张卡可以叠多个 skill）。
    非字符串、空串、重复项直接丢掉，保持声明顺序。
    """
    vvv = card.extensions.get("vvv")
    if not isinstance(vvv, dict):
        return []
    skill = vvv.get("skill")
    raw = [skill] if isinstance(skill, str) else skill if isinstance(skill, list) else []
    ids: list[str] = []
    for item in raw:
        if isinstance(item, str) and item and item not in ids:
            ids.append(item)
    return ids


def skill_id_of(card: CharacterCard) -> str | None:
    """第一个 skill id；保留给只认单个 skill 的老调用方。"""
    ids = skill_ids_of(card)
    return ids[0] if ids else None


class PromptAssembler:
    """按角色组装系统提示词。

    组装只在建会话或换角色时发生，所以不做缓存——角色卡和 skill 都可能被改动，
    缓存会让改动在线上表现成"改了没生效"。
    """

    def __init__(self, *, characters: CharacterSourcePort, skills: SkillCatalog) -> None:
        self._characters = characters
        self._skills = skills

    @property
    def characters(self) -> CharacterSourcePort:
        return self._characters

    @property
    def skills(self) -> SkillCatalog:
        return self._skills

    def build(self, character_id: str, memory_block: str = "") -> str:
        card = self._characters.load(character_id)
        skill_text = ""
        # 没声明 skill 也要 compose：常驻 skill（陪伴底线）对每个角色卡都生效。
        # skill 缺失不该让对话开不起来：角色人设本身已经能支撑一轮对话。
        try:
            skill_text = self._skills.compose(skill_ids_of(card))
        except Exception:
            skill_text = ""
        return build_instructions(
            persona=render_persona(card),
            skill_text=skill_text,
            memory_block=memory_block,
        )

    def __call__(self, ctx: Any, memory_block: str) -> str:
        """符合 ConversationService 对 prompt_builder 的调用约定。"""
        return self.build(ctx.character_id, memory_block)
