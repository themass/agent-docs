"""用户画像存储协议（domain/persona/model.py 说明了数据的形状）。所有方法按「用户 + 角色」隔离。"""

from __future__ import annotations

from typing import Protocol

from companion.domain.persona.model import MergeAction, ProfileEntry


class PersonaStore(Protocol):
    async def list_entries(self, *, owner_id: int, role_id: str, include_history: bool = False) -> list[ProfileEntry]:
        """当前有效的条目（不含被取代和被压住的）；``include_history`` 时包括全部，供「为什么记得」和回滚用。"""
        ...

    async def apply(self, *, owner_id: int, role_id: str, actions: list[MergeAction]) -> int:
        """在一个事务里应用合并动作，返回实际写入的条数。update 先写新条目再把旧条目标为被取代。"""
        ...

    async def suppress(self, *, owner_id: int, entry_id: int) -> bool:
        """用户说「别再提」：条目不再注入，同话题不再被重新生成。不属于该用户返回 False。"""
        ...

    async def delete(self, *, owner_id: int, entry_id: int) -> bool: ...

    async def drop_for_facts(self, *, owner_id: int, fact_ids: list[str]) -> int:
        """联动删除：来源事实被用户删掉后，只靠这些事实归纳出来的条目一并删除。"""
        ...

    async def delete_user(self, *, owner_id: int) -> int: ...

    async def advance(self, *, owner_id: int, role_id: str, last_message_id: int, add_chars: int) -> int:
        """记录又处理了多少内容，返回累计待处理字数（超过阈值时调用方触发抽取）。"""
        ...

    async def cursor(self, *, owner_id: int, role_id: str) -> tuple[int, int]:
        """(上次处理到的用户消息 id, 累计待处理字数)；没有记录是 (0, 0)。"""
        ...

    async def reset_pending(self, *, owner_id: int, role_id: str, last_message_id: int) -> None: ...
