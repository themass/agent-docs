from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from companion.domain.roles.card import CharacterCard, from_v2_json, render_persona
from companion.domain.prompt.instructions import build_instructions
from companion.adapters.skills.library import SkillLibrary


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
