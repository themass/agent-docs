"""持久化端口：会话、消息、回合、队列、角色、确认、后台任务。

领域与应用层只依赖这些协议与记录类型；MySQL 实现在 adapters/store/sql/。
所有查询必须带 owner_id（用户隔离，D §5.3），不带则视为实现错误。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class SessionRecord:
    id: int
    owner_id: int
    role_id: str
    name: str
    locale: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class MessageRecord:
    id: int
    session_id: int
    owner_id: int
    role: str
    content: str
    kind: str
    client_message_id: str | None
    turn_id: str | None
    interrupted: bool
    created_at: datetime
    meta: dict[str, Any] = field(default_factory=dict)
    alt_group: int | None = None     # 候选回复组；None = 不是候选
    alt_selected: bool = True        # 组内当前被选中的那一条（普通消息恒为 True）


@dataclass(frozen=True)
class QueueItem:
    id: int
    session_id: int
    owner_id: int
    message_id: int
    client_message_id: str | None
    text: str
    status: str
    drain_attempts: int
    created_at: datetime


@dataclass(frozen=True)
class RoleRecord:
    id: int
    public_id: str
    owner_id: int
    name: str
    tagline: str
    description: str
    prompt: str
    locale: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ConfirmationRecord:
    id: str
    owner_id: int
    session_id: int
    turn_id: str | None
    tool: str
    args: dict[str, Any]
    args_fingerprint: str
    title: str
    summary: str
    status: str
    expires_at: datetime


class SessionStore(Protocol):
    async def create(self, *, owner_id: int, role_id: str, name: str, locale: str) -> SessionRecord: ...
    async def get(self, *, owner_id: int, session_id: int) -> SessionRecord | None: ...
    async def list_for_owner(self, *, owner_id: int, limit: int, offset: int) -> list[SessionRecord]: ...
    async def latest_for_role(self, *, owner_id: int, role_id: str) -> SessionRecord | None:
        """这个用户和这个角色最近一次活跃的会话（未删除）。没有则 None。"""
        ...
    async def rename(self, *, owner_id: int, session_id: int, name: str) -> bool: ...
    async def soft_delete(self, *, owner_id: int, session_id: int) -> bool: ...
    async def advance_fence(self, *, session_id: int, fence: int) -> bool: ...


class MessageStore(Protocol):
    async def append(self, *, owner_id: int, session_id: int, role: str, content: str, kind: str,
                     client_message_id: str | None, turn_id: str | None, meta: dict[str, Any],
                     fence: int | None = None, alt_of: int | None = None) -> MessageRecord | None:
        """``alt_of``：作为这条消息的另一个候选写入（重新生成）。新消息成为组内被选中的一条。"""
        ...
    async def list_after(self, *, owner_id: int, session_id: int, after_id: int, limit: int) -> list[MessageRecord]: ...
    async def get_any(self, *, owner_id: int, message_id: int) -> MessageRecord | None: ...
    async def find_by_client_id(self, *, owner_id: int, session_id: int, client_message_id: str) -> MessageRecord | None: ...
    async def list_before(self, *, owner_id: int, session_id: int, before_id: int | None, limit: int) -> list[MessageRecord]: ...
    async def mark_interrupted(self, *, owner_id: int, message_id: int) -> bool: ...
    async def get(self, *, owner_id: int, message_id: int) -> MessageRecord | None: ...
    async def attach_turn(self, *, owner_id: int, session_id: int, message_ids: list[int], turn_id: str) -> int: ...
    async def edit(self, *, owner_id: int, message_id: int, content: str) -> bool: ...
    async def list_by_turn(self, *, owner_id: int, session_id: int, turn_id: str) -> list[MessageRecord]: ...
    async def soft_delete(self, *, owner_id: int, message_id: int) -> bool: ...
    async def clear(self, *, owner_id: int, session_id: int) -> int: ...
    async def alternatives(self, *, owner_id: int, session_id: int, alt_group: int) -> list[MessageRecord]:
        """同组的候选（含未选中的），按 id 升序，不含已删除。"""
        ...
    async def alt_ids_for(self, *, owner_id: int, session_id: int, groups: list[int]) -> dict[int, list[int]]:
        """批量取各组的候选 id（按 id 升序，不含已删除），历史列表用。"""
        ...
    async def select_alternative(self, *, owner_id: int, session_id: int, alt_group: int, message_id: int) -> bool:
        """把组内被选中的候选换成 ``message_id``；不在组内返回 False。"""
        ...


class QueueStore(Protocol):
    async def enqueue(self, *, owner_id: int, session_id: int, message_id: int,
                      client_message_id: str | None, text: str) -> QueueItem: ...
    async def list_queued(self, *, owner_id: int, session_id: int) -> list[QueueItem]: ...
    async def transition(self, *, item_id: int, from_status: str, to_status: str,
                         turn_id: str | None = None) -> bool: ...
    async def list_status(self, *, owner_id: int, session_id: int, status: str) -> list[QueueItem]: ...
    async def withdraw(self, *, owner_id: int, item_id: int) -> bool: ...


class RoleStore(Protocol):
    async def create(self, *, owner_id: int, public_id: str, name: str, tagline: str, description: str,
                     prompt: str, locale: str) -> RoleRecord: ...
    async def get_owned(self, *, owner_id: int, public_id: str) -> RoleRecord | None: ...
    async def list_owned(self, *, owner_id: int, limit: int, offset: int) -> list[RoleRecord]: ...
    async def update(self, *, owner_id: int, public_id: str, **fields: Any) -> bool: ...
    async def soft_delete(self, *, owner_id: int, public_id: str) -> bool: ...


@dataclass(frozen=True)
class UploadRecord:
    """一次上传的记录。定义在这里而不是 uploads 模块：持久化层要按它还原行，
    反过来让它 import 业务模块会把底座变成依赖于调用方。"""

    id: str
    owner_id: int
    object_key: str
    mime: str
    size: int
    width: int
    height: int
    referenced: bool
    created_at: datetime


class UploadStore(Protocol):
    async def create(self, record: UploadRecord) -> None: ...
    async def get_owned(self, *, owner_id: int, upload_id: str) -> UploadRecord | None: ...


class ConfirmationStore(Protocol):
    async def create(self, record: ConfirmationRecord) -> None: ...
    async def get_pending(self, *, owner_id: int, confirmation_id: str) -> ConfirmationRecord | None: ...
    async def list_pending(self, *, owner_id: int) -> list[ConfirmationRecord]: ...
    async def decide(self, *, owner_id: int, confirmation_id: str, status: str) -> bool: ...
    async def finish(self, *, owner_id: int, confirmation_id: str, status: str) -> bool: ...
    async def expire_due(self, *, now: datetime) -> int: ...
