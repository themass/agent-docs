"""MySQL 仓储实现（SQLAlchemy Core，异步）。

约定：
- 每个查询都带 owner_id（用户隔离）。查不到、或不属于该用户，统一返回 None / False。
- 状态转移用条件更新，用受影响行数判断成功（不做先读后写）。
- 删除一律软删除，注销时由后台任务物理删除（O §3）。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.adapters.store.mysql.schema import (
    action_confirmation,
    chat_message,
    chat_queue,
    chat_session,
    tool_call,
    user_role,
)
from companion.domain.turn.queue import QUEUE_TRANSITIONS
from companion.ports.store import (
    ConfirmationRecord,
    MessageRecord,
    QueueItem,
    RoleRecord,
    SessionRecord,
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class MysqlSessionStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def create(self, *, owner_id: int, role_id: str, name: str, locale: str) -> SessionRecord:
        now = _now()
        async with self._engine.begin() as conn:
            res = await conn.execute(insert(chat_session).values(
                owner_id=owner_id, role_id=role_id, name=name, locale=locale,
                created_at=now, updated_at=now, deleted=False))
            new_id = res.inserted_primary_key[0]
        return SessionRecord(new_id, owner_id, role_id, name, locale, now, now)

    async def get(self, *, owner_id: int, session_id: int) -> SessionRecord | None:
        async with self._engine.connect() as conn:
            row = (await conn.execute(select(chat_session).where(and_(
                chat_session.c.id == session_id, chat_session.c.owner_id == owner_id,
                chat_session.c.deleted == False)))).mappings().first()  # noqa: E712
        return _session(row) if row else None

    async def list_for_owner(self, *, owner_id: int, limit: int, offset: int) -> list[SessionRecord]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(chat_session).where(and_(
                chat_session.c.owner_id == owner_id, chat_session.c.deleted == False))  # noqa: E712
                .order_by(chat_session.c.updated_at.desc(), chat_session.c.id.desc())
                .limit(limit).offset(offset))).mappings().all()
        return [_session(r) for r in rows]

    async def rename(self, *, owner_id: int, session_id: int, name: str) -> bool:
        async with self._engine.begin() as conn:
            res = await conn.execute(update(chat_session).where(and_(
                chat_session.c.id == session_id, chat_session.c.owner_id == owner_id))
                .values(name=name))
        return res.rowcount == 1

    async def soft_delete(self, *, owner_id: int, session_id: int) -> bool:
        async with self._engine.begin() as conn:
            res = await conn.execute(update(chat_session).where(and_(
                chat_session.c.id == session_id, chat_session.c.owner_id == owner_id))
                .values(deleted=True))
        return res.rowcount == 1


class MysqlMessageStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def append(self, *, owner_id: int, session_id: int, role: str, content: str, kind: str,
                     client_message_id: str | None, turn_id: str | None, meta: dict[str, Any]) -> MessageRecord:
        now = _now()
        async with self._engine.begin() as conn:
            res = await conn.execute(insert(chat_message).values(
                session_id=session_id, owner_id=owner_id, role=role, content=content, kind=kind,
                client_message_id=client_message_id, turn_id=turn_id, interrupted=False,
                meta=meta or None, created_at=now, deleted=False))
            new_id = res.inserted_primary_key[0]
        return MessageRecord(new_id, session_id, owner_id, role, content, kind, client_message_id,
                             turn_id, False, now, dict(meta or {}))

    async def find_by_client_id(self, *, owner_id: int, session_id: int, client_message_id: str) -> MessageRecord | None:
        async with self._engine.connect() as conn:
            row = (await conn.execute(select(chat_message).where(and_(
                chat_message.c.session_id == session_id, chat_message.c.owner_id == owner_id,
                chat_message.c.client_message_id == client_message_id)))).mappings().first()
        return _message(row) if row else None

    async def list_before(self, *, owner_id: int, session_id: int, before_id: int | None, limit: int) -> list[MessageRecord]:
        cond = [chat_message.c.session_id == session_id, chat_message.c.owner_id == owner_id,
                chat_message.c.deleted == False]  # noqa: E712
        if before_id is not None:
            cond.append(chat_message.c.id < before_id)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(chat_message).where(and_(*cond))
                    .order_by(chat_message.c.id.desc()).limit(limit))).mappings().all()
        return [_message(r) for r in rows]

    async def mark_interrupted(self, *, owner_id: int, message_id: int) -> bool:
        async with self._engine.begin() as conn:
            res = await conn.execute(update(chat_message).where(and_(
                chat_message.c.id == message_id, chat_message.c.owner_id == owner_id))
                .values(interrupted=True))
        return res.rowcount == 1

    async def get(self, *, owner_id: int, message_id: int) -> MessageRecord | None:
        async with self._engine.connect() as conn:
            row = (await conn.execute(select(chat_message).where(and_(
                chat_message.c.id == message_id, chat_message.c.owner_id == owner_id,
                chat_message.c.deleted == False)))).mappings().first()  # noqa: E712
        return _message(row) if row else None

    async def attach_turn(self, *, owner_id: int, session_id: int, message_ids: list[int], turn_id: str) -> int:
        """把用户消息挂到回合上（D §3.3）。只挂还没有回合的消息，重复调用无副作用。"""
        if not message_ids:
            return 0
        async with self._engine.begin() as conn:
            res = await conn.execute(update(chat_message).where(and_(
                chat_message.c.id.in_(message_ids), chat_message.c.owner_id == owner_id,
                chat_message.c.session_id == session_id, chat_message.c.turn_id.is_(None)))
                .values(turn_id=turn_id))
        return res.rowcount

    async def edit(self, *, owner_id: int, message_id: int, content: str) -> bool:
        """只允许编辑用户消息（D §7.1）。"""
        async with self._engine.begin() as conn:
            res = await conn.execute(update(chat_message).where(and_(
                chat_message.c.id == message_id, chat_message.c.owner_id == owner_id,
                chat_message.c.role == "user", chat_message.c.deleted == False))  # noqa: E712
                .values(content=content))
        return res.rowcount == 1

    async def list_by_turn(self, *, owner_id: int, session_id: int, turn_id: str) -> list[MessageRecord]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(chat_message).where(and_(
                chat_message.c.turn_id == turn_id, chat_message.c.owner_id == owner_id,
                chat_message.c.session_id == session_id, chat_message.c.deleted == False))  # noqa: E712
                .order_by(chat_message.c.id))).mappings().all()
        return [_message(r) for r in rows]

    async def soft_delete(self, *, owner_id: int, message_id: int) -> bool:
        async with self._engine.begin() as conn:
            res = await conn.execute(update(chat_message).where(and_(
                chat_message.c.id == message_id, chat_message.c.owner_id == owner_id,
                chat_message.c.deleted == False))  # noqa: E712
                .values(deleted=True))
        return res.rowcount == 1


class MysqlQueueStore:
    """排队输入。状态转移只允许 D §3.3 列出的那几条，其余拒绝。"""

    ALLOWED = QUEUE_TRANSITIONS  # 单一来源：domain/turn/queue.py

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def enqueue(self, *, owner_id: int, session_id: int, message_id: int,
                      client_message_id: str | None, text: str) -> QueueItem:
        now = _now()
        async with self._engine.begin() as conn:
            res = await conn.execute(insert(chat_queue).values(
                session_id=session_id, owner_id=owner_id, message_id=message_id,
                client_message_id=client_message_id, text=text, status="queued",
                drain_attempts=0, created_at=now))
            new_id = res.inserted_primary_key[0]
        return QueueItem(new_id, session_id, owner_id, message_id, client_message_id, text, "queued", 0, now)

    async def list_queued(self, *, owner_id: int, session_id: int) -> list[QueueItem]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(chat_queue).where(and_(
                chat_queue.c.session_id == session_id, chat_queue.c.owner_id == owner_id,
                chat_queue.c.status == "queued")).order_by(chat_queue.c.id))).mappings().all()
        return [_queue(r) for r in rows]

    async def transition(self, *, item_id: int, from_status: str, to_status: str,
                         turn_id: str | None = None) -> bool:
        if (from_status, to_status) not in self.ALLOWED:
            raise ValueError(f"illegal queue transition {from_status} -> {to_status}")
        values: dict[str, Any] = {"status": to_status}
        if to_status == "draining":
            values["drain_attempts"] = chat_queue.c.drain_attempts + 1
        if turn_id is not None:
            values["turn_id"] = turn_id
        async with self._engine.begin() as conn:
            res = await conn.execute(update(chat_queue).where(and_(
                chat_queue.c.id == item_id, chat_queue.c.status == from_status)).values(**values))
        return res.rowcount == 1

    async def withdraw(self, *, owner_id: int, item_id: int) -> bool:
        async with self._engine.begin() as conn:
            res = await conn.execute(update(chat_queue).where(and_(
                chat_queue.c.id == item_id, chat_queue.c.owner_id == owner_id,
                chat_queue.c.status == "queued")).values(status="withdrawn"))
        return res.rowcount == 1

    async def list_status(self, *, owner_id: int, session_id: int, status: str) -> list[QueueItem]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(chat_queue).where(and_(
                chat_queue.c.session_id == session_id, chat_queue.c.owner_id == owner_id,
                chat_queue.c.status == status)).order_by(chat_queue.c.id))).mappings().all()
        return [_queue(r) for r in rows]


class MysqlRoleStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def create(self, *, owner_id: int, public_id: str, name: str, tagline: str, description: str,
                     prompt: str, locale: str) -> RoleRecord:
        now = _now()
        async with self._engine.begin() as conn:
            res = await conn.execute(insert(user_role).values(
                public_id=public_id, owner_id=owner_id, name=name, tagline=tagline, description=description,
                prompt=prompt, locale=locale, created_at=now, updated_at=now, deleted=False))
            new_id = res.inserted_primary_key[0]
        return RoleRecord(new_id, public_id, owner_id, name, tagline, description, prompt, locale, now, now)

    async def get_owned(self, *, owner_id: int, public_id: str) -> RoleRecord | None:
        async with self._engine.connect() as conn:
            row = (await conn.execute(select(user_role).where(and_(
                user_role.c.public_id == public_id, user_role.c.owner_id == owner_id,
                user_role.c.deleted == False)))).mappings().first()  # noqa: E712
        return _role(row) if row else None

    async def list_owned(self, *, owner_id: int, limit: int, offset: int) -> list[RoleRecord]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(user_role).where(and_(
                user_role.c.owner_id == owner_id, user_role.c.deleted == False))  # noqa: E712
                .order_by(user_role.c.id.desc()).limit(limit).offset(offset))).mappings().all()
        return [_role(r) for r in rows]

    async def update(self, *, owner_id: int, public_id: str, **fields: Any) -> bool:
        allowed = {"name", "tagline", "description", "prompt", "locale"}
        values = {k: v for k, v in fields.items() if k in allowed}
        if not values:
            return False
        async with self._engine.begin() as conn:
            res = await conn.execute(update(user_role).where(and_(
                user_role.c.public_id == public_id, user_role.c.owner_id == owner_id,
                user_role.c.deleted == False)).values(**values))  # noqa: E712
        return res.rowcount == 1

    async def soft_delete(self, *, owner_id: int, public_id: str) -> bool:
        async with self._engine.begin() as conn:
            res = await conn.execute(update(user_role).where(and_(
                user_role.c.public_id == public_id, user_role.c.owner_id == owner_id))
                .values(deleted=True))
        return res.rowcount == 1


class MysqlConfirmationStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def create(self, record: ConfirmationRecord) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(insert(action_confirmation).values(
                id=record.id, owner_id=record.owner_id, session_id=record.session_id, turn_id=record.turn_id,
                tool=record.tool, args=record.args, args_fingerprint=record.args_fingerprint,
                title=record.title, summary=record.summary, status=record.status,
                expires_at=record.expires_at, created_at=_now()))

    async def get_pending(self, *, owner_id: int, confirmation_id: str) -> ConfirmationRecord | None:
        async with self._engine.connect() as conn:
            row = (await conn.execute(select(action_confirmation).where(and_(
                action_confirmation.c.id == confirmation_id, action_confirmation.c.owner_id == owner_id,
                action_confirmation.c.status == "pending")))).mappings().first()
        return _confirmation(row) if row else None

    async def list_pending(self, *, owner_id: int) -> list[ConfirmationRecord]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(action_confirmation).where(and_(
                action_confirmation.c.owner_id == owner_id, action_confirmation.c.status == "pending"))
                .order_by(action_confirmation.c.created_at))).mappings().all()
        return [_confirmation(r) for r in rows]

    async def decide(self, *, owner_id: int, confirmation_id: str, status: str) -> bool:
        """只允许从 pending 转出（认领或拒绝/过期）。"""
        async with self._engine.begin() as conn:
            res = await conn.execute(update(action_confirmation).where(and_(
                action_confirmation.c.id == confirmation_id, action_confirmation.c.owner_id == owner_id,
                action_confirmation.c.status == "pending")).values(status=status, decided_at=_now()))
        return res.rowcount == 1

    async def finish(self, *, owner_id: int, confirmation_id: str, status: str) -> bool:
        """执行结束：只允许从 processing 转到 executed/failed。"""
        async with self._engine.begin() as conn:
            res = await conn.execute(update(action_confirmation).where(and_(
                action_confirmation.c.id == confirmation_id, action_confirmation.c.owner_id == owner_id,
                action_confirmation.c.status == "processing")).values(status=status))
        return res.rowcount == 1


class MysqlToolCallStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def append(self, record) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(insert(tool_call).values(
                turn_id=record.turn_id, owner_id=record.owner_id, tool=record.tool,
                permission=record.permission, args_fingerprint=record.args_fingerprint,
                status=record.status, latency_ms=record.latency_ms, result_chars=record.result_chars,
                created_at=_now()))


# ---- row mappers ----

def _session(r) -> SessionRecord:
    return SessionRecord(r["id"], r["owner_id"], r["role_id"], r["name"], r["locale"], r["created_at"], r["updated_at"])


def _message(r) -> MessageRecord:
    meta = r["meta"]
    if isinstance(meta, str):
        meta = json.loads(meta)
    return MessageRecord(r["id"], r["session_id"], r["owner_id"], r["role"], r["content"], r["kind"],
                         r["client_message_id"], r["turn_id"], bool(r["interrupted"]), r["created_at"], dict(meta or {}))


def _queue(r) -> QueueItem:
    return QueueItem(r["id"], r["session_id"], r["owner_id"], r["message_id"], r["client_message_id"],
                     r["text"], r["status"], r["drain_attempts"], r["created_at"])


def _role(r) -> RoleRecord:
    return RoleRecord(r["id"], r["public_id"], r["owner_id"], r["name"], r["tagline"], r["description"],
                      r["prompt"], r["locale"], r["created_at"], r["updated_at"])


def _confirmation(r) -> ConfirmationRecord:
    args = r["args"]
    if isinstance(args, str):
        args = json.loads(args)
    return ConfirmationRecord(r["id"], r["owner_id"], r["session_id"], r["turn_id"], r["tool"], dict(args or {}),
                              r["args_fingerprint"], r["title"], r["summary"], r["status"], r["expires_at"])
