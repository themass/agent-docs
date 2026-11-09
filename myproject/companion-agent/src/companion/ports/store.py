"""持久化端口：会话、消息、回合、队列、角色、确认、后台任务。

领域与应用层只依赖这些协议与记录类型；MySQL 实现在 adapters/store/mysql/。
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
    async def rename(self, *, owner_id: int, session_id: int, name: str) -> bool: ...
    async def soft_delete(self, *, owner_id: int, session_id: int) -> bool: ...


class MessageStore(Protocol):
    async def append(self, *, owner_id: int, session_id: int, role: str, content: str, kind: str,
                     client_message_id: str | None, turn_id: str | None, meta: dict[str, Any]) -> MessageRecord: ...
    async def find_by_client_id(self, *, owner_id: int, session_id: int, client_message_id: str) -> MessageRecord | None: ...
    async def list_before(self, *, owner_id: int, session_id: int, before_id: int | None, limit: int) -> list[MessageRecord]: ...
    async def mark_interrupted(self, *, owner_id: int, message_id: int) -> bool: ...
    async def get(self, *, owner_id: int, message_id: int) -> MessageRecord | None: ...
    async def attach_turn(self, *, owner_id: int, session_id: int, message_ids: list[int], turn_id: str) -> int: ...
    async def edit(self, *, owner_id: int, message_id: int, content: str) -> bool: ...
    async def list_by_turn(self, *, owner_id: int, session_id: int, turn_id: str) -> list[MessageRecord]: ...
    async def soft_delete(self, *, owner_id: int, message_id: int) -> bool: ...


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


class UploadStore(Protocol):
    async def create(self, record: Any) -> None: ...
    async def get_owned(self, *, owner_id: int, upload_id: str) -> Any | None: ...


class ConfirmationStore(Protocol):
    async def create(self, record: ConfirmationRecord) -> None: ...
    async def get_pending(self, *, owner_id: int, confirmation_id: str) -> ConfirmationRecord | None: ...
    async def list_pending(self, *, owner_id: int) -> list[ConfirmationRecord]: ...
    async def decide(self, *, owner_id: int, confirmation_id: str, status: str) -> bool: ...
    async def finish(self, *, owner_id: int, confirmation_id: str, status: str) -> bool: ...
    async def expire_due(self, *, now: datetime) -> int: ...
