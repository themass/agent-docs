"""角色卡来源端口：读取角色卡，不关心来自库、文件还是服务。

``load`` 是异步的：链上第一环现在就是数据库（packs.py），同步端口会把事件循环堵在
回合关键路径上。未命中的口径是 ``FileNotFoundError``——resolver 的存在性判据钉的是
这个异常，换实现不能换语义。
"""

from __future__ import annotations

from typing import Any, Protocol


class CharacterSourcePort(Protocol):
    async def load(self, character_id: str) -> Any: ...
