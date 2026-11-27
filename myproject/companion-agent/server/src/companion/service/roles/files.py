from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from companion.agent.roles.card import CharacterCard, CharacterFormatError, from_v2_json


@dataclass
class CharacterSource:
    """角色卡从磁盘来（随包发布）。现在它是读取链的兜底环：库优先，见 packs.py。"""

    root: Path

    async def load(self, character_id: str) -> CharacterCard:
        path = self.root / f"{character_id}.v2.json"
        if not path.is_file():
            raise FileNotFoundError(f"character not found: {character_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        card = from_v2_json(payload)
        if not card.id:
            card.id = character_id
        return card

    async def cards(self) -> dict[str, CharacterCard]:
        """整目录的卡。一张坏卡跳过——列表页不该因为一个文件坏了而空白（同 CharacterCatalog）。"""
        loaded: dict[str, CharacterCard] = {}
        for path in sorted(self.root.glob("*.v2.json")):
            character_id = path.name[: -len(".v2.json")]
            try:
                loaded[character_id] = await self.load(character_id)
            except (CharacterFormatError, json.JSONDecodeError, OSError):
                continue
        return loaded
