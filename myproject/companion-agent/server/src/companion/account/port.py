"""账号注销的跨存储删除所需的端口（chat-agent-ops-design.md §3）。

每个方法都必须可以重复执行：注销任务失败会整体重试，已经删过的部分再删一次没有副作用。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class AccountFootprint:
    """一个用户在关系库里留下的、需要到别的存储里一起删除的东西。"""

    session_ids: tuple[int, ...] = ()
    role_ids: tuple[str, ...] = ()        # 聊过的角色：记忆按角色分空间，要逐个删除
    object_keys: tuple[str, ...] = ()     # 上传到对象存储的文件


class AccountDataStore(Protocol):
    async def footprint(self, *, owner_id: int) -> AccountFootprint:
        """包括已软删除的会话：它们的线程、事件流与记忆同样要删。"""
        ...

    async def close_sessions(self, *, owner_id: int) -> int:
        """把会话全部标记为删除并推进围栏：新消息被拒，进行中的回合写不进回复。"""
        ...

    async def purge(self, *, owner_id: int) -> int:
        """物理删除该用户在关系库里的全部行（消息、回合、队列、会话、角色、上传、确认、
        审计、提醒、画像，以及还没执行的、带该用户数据的后台任务）。返回删除的行数。"""
        ...

    async def log_purge(self, *, user_hash: str, requested_at: datetime, finished_at: datetime) -> None:
        """记一笔注销完成，只存用户 id 的哈希。"""
        ...


class ThreadEraser(Protocol):
    """模型上下文（对话线程 checkpoint）的删除。"""

    async def delete_threads(self, *, session_ids: Sequence[int]) -> None: ...


class SessionEventsEraser(Protocol):
    """控制面（Redis）里会话的锁、回合状态与事件流；进行中的回合先被取消。"""

    async def purge_session(self, *, session_id: int) -> None: ...
