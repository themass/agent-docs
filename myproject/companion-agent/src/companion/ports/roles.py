"""角色卡来源端口：读取角色卡，不关心来自文件还是服务。"""

from __future__ import annotations

from typing import Any, Protocol


class CharacterSourcePort(Protocol):
    root: Any

    def load(self, character_id: str) -> Any: ...
