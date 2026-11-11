from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from companion.ports.roles import CharacterSourcePort
from companion.domain.roles.card import CharacterCard, from_v2_json, render_persona
from companion.domain.prompt.instructions import build_instructions
from companion.ports.skills import SkillCatalog


def skill_id_of(card: CharacterCard) -> str | None:
    """角色卡在 extensions.vvv.skill 里声明它用哪个 skill 包。"""
    vvv = card.extensions.get("vvv")
    if not isinstance(vvv, dict):
        return None
    skill = vvv.get("skill")
    return skill if isinstance(skill, str) and skill else None


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
        skill_id = skill_id_of(card)
        if skill_id:
            # skill 缺失不该让对话开不起来：角色人设本身已经能支撑一轮对话。
            try:
                skill_text = self._skills.compose([skill_id])
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
