"""把角色、skill 与记忆装配成一个回合的提示词与请求。

``ConversationService`` 在 conversation.py 里定义了流程骨架（召回 → 拼装 → 交主脑），
这里补上"拼装"这一步的具体实现：从角色卡读人设，从 skill 库读方法论，
交给 instructions.build_instructions 分层。

单独放在一起是因为这一段最容易在扩展时写歪：新增一个角色或 skill 不该改动
对话流程。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from companion.prompt.character import CharacterCard, from_v2_json, render_persona
from companion.prompt.instructions import build_instructions
from companion.prompt.skills import SkillLibrary


@dataclass
class CharacterSource:
    """角色卡从哪来。现在只支持本地 JSON 文件，将来接服务端 API 时换这个实现。"""

    root: Path

    def load(self, character_id: str) -> CharacterCard:
        path = self.root / f"{character_id}.v2.json"
        if not path.is_file():
            raise FileNotFoundError(f"character not found: {character_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        card = from_v2_json(payload)
        if not card.id:
            card.id = character_id
        return card


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

    def __init__(self, *, characters: CharacterSource, skills: SkillLibrary) -> None:
        self._characters = characters
        self._skills = skills

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
