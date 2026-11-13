"""SQL 仓储实现（SQLAlchemy Core，异步；目标库 Postgres，兼容 MySQL）。

约定：
- 每个查询都带 owner_id（用户隔离）。查不到、或不属于该用户，统一返回 None / False。
- 状态转移用条件更新，用受影响行数判断成功（不做先读后写）。
- 删除一律软删除，注销时由后台任务物理删除（O §3）。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, delete, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.db.schema import (
    action_confirmation,
    chat_message,
    chat_queue,
    chat_session,
    tool_call,
    upload,
    user_role,
)
from companion.db.port import (
    QUEUE_TRANSITIONS,
    ConfirmationRecord,
    MessageRecord,
    QueueItem,
    RoleRecord,
    SessionRecord,
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SqlSessionStore:
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

    async def latest_for_role(self, *, owner_id: int, role_id: str) -> SessionRecord | None:
        async with self._engine.connect() as conn:
            row = (await conn.execute(select(chat_session).where(and_(
                chat_session.c.owner_id == owner_id, chat_session.c.role_id == role_id,
                chat_session.c.deleted == False))  # noqa: E712
                .order_by(chat_session.c.updated_at.desc(), chat_session.c.id.desc()).limit(1))).mappings().first()
        return _session(row) if row else None

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

    async def advance_fence(self, *, session_id: int, fence: int) -> bool:
        """把会话围栏推进到 ``fence``。只增不减：拿到更新的锁的进程总能推进，旧的推进不了。"""
        async with self._engine.begin() as conn:
            res = await conn.execute(update(chat_session).where(and_(
                chat_session.c.id == session_id, chat_session.c.fence < fence))
                .values(fence=fence))
        return res.rowcount == 1


class SqlMessageStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def append(self, *, owner_id: int, session_id: int, role: str, content: str, kind: str,
                     client_message_id: str | None, turn_id: str | None, meta: dict[str, Any],
                     fence: int | None = None, alt_of: int | None = None) -> MessageRecord | None:
        """写入一条消息。给了 ``fence`` 时，只有会话围栏仍等于它才写入（否则返回 None）：
        锁丢失后被别的进程接手的旧回合，回复写不进来。

        给了 ``alt_of``（重新生成）：新消息作为那条回复的另一个候选写入，成为组内被选中的一条；
        组还不存在就以被重生成的那条的 id 建组。``alt_of`` 找不到或不是同会话的助手消息时当作普通消息写入。"""
        now = _now()
        async with self._engine.begin() as conn:
            if fence is not None:
                current = (await conn.execute(
                    select(chat_session.c.fence).where(chat_session.c.id == session_id).with_for_update()
                )).scalar()
                if current != fence:
                    return None
            group: int | None = None
            if alt_of is not None and role == "assistant":
                origin = (await conn.execute(select(chat_message.c.id, chat_message.c.alt_group).where(and_(
                    chat_message.c.id == alt_of, chat_message.c.session_id == session_id,
                    chat_message.c.owner_id == owner_id, chat_message.c.role == "assistant")))).first()
                if origin is not None:
                    group = origin.alt_group or origin.id
                    await conn.execute(update(chat_message).where(
                        or_(chat_message.c.id == group, chat_message.c.alt_group == group))
                        .values(alt_group=group, alt_selected=False))
            res = await conn.execute(insert(chat_message).values(
                session_id=session_id, owner_id=owner_id, role=role, content=content, kind=kind,
                client_message_id=client_message_id, turn_id=turn_id, interrupted=False,
                meta=meta or None, created_at=now, deleted=False, alt_group=group, alt_selected=True))
            new_id = res.inserted_primary_key[0]
        return MessageRecord(new_id, session_id, owner_id, role, content, kind, client_message_id,
                             turn_id, False, now, dict(meta or {}), alt_group=group, alt_selected=True)

    async def find_by_client_id(self, *, owner_id: int, session_id: int, client_message_id: str) -> MessageRecord | None:
        async with self._engine.connect() as conn:
            row = (await conn.execute(select(chat_message).where(and_(
                chat_message.c.session_id == session_id, chat_message.c.owner_id == owner_id,
                chat_message.c.client_message_id == client_message_id)))).mappings().first()
        return _message(row) if row else None

    async def list_before(self, *, owner_id: int, session_id: int, before_id: int | None, limit: int) -> list[MessageRecord]:
        cond = [chat_message.c.session_id == session_id, chat_message.c.owner_id == owner_id,
                chat_message.c.deleted == False,  # noqa: E712
                chat_message.c.alt_selected == True]  # noqa: E712 —— 未选中的候选不进历史
        if before_id is not None:
            cond.append(chat_message.c.id < before_id)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(chat_message).where(and_(*cond))
                    .order_by(chat_message.c.id.desc()).limit(limit))).mappings().all()
        return [_message(r) for r in rows]

    async def list_after(self, *, owner_id: int, session_id: int, after_id: int, limit: int) -> list[MessageRecord]:
        """``after_id`` 之后的消息，按 id 升序（不含已删除）。"""
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(chat_message).where(and_(
                chat_message.c.session_id == session_id, chat_message.c.owner_id == owner_id,
                chat_message.c.deleted == False, chat_message.c.alt_selected == True,  # noqa: E712
                chat_message.c.id > after_id))
                .order_by(chat_message.c.id).limit(limit))).mappings().all()
        return [_message(r) for r in rows]

    async def get_any(self, *, owner_id: int, message_id: int) -> MessageRecord | None:
        """包括已删除的消息（重建摘要时需要知道哪些被删）。"""
        async with self._engine.connect() as conn:
            row = (await conn.execute(select(chat_message).where(and_(
                chat_message.c.id == message_id, chat_message.c.owner_id == owner_id)))).mappings().first()
        return _message(row) if row else None

    async def alternatives(self, *, owner_id: int, session_id: int, alt_group: int) -> list[MessageRecord]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(chat_message).where(and_(
                chat_message.c.session_id == session_id, chat_message.c.owner_id == owner_id,
                chat_message.c.alt_group == alt_group, chat_message.c.deleted == False))  # noqa: E712
                .order_by(chat_message.c.id))).mappings().all()
        return [_message(r) for r in rows]

    async def alt_ids_for(self, *, owner_id: int, session_id: int, groups: list[int]) -> dict[int, list[int]]:
        if not groups:
            return {}
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(chat_message.c.id, chat_message.c.alt_group).where(and_(
                chat_message.c.session_id == session_id, chat_message.c.owner_id == owner_id,
                chat_message.c.alt_group.in_(groups), chat_message.c.deleted == False))  # noqa: E712
                .order_by(chat_message.c.id))).all()
        out: dict[int, list[int]] = {g: [] for g in groups}
        for mid, group in rows:
            out[group].append(mid)
        return out

    async def select_alternative(self, *, owner_id: int, session_id: int, alt_group: int, message_id: int) -> bool:
        async with self._engine.begin() as conn:
            member = (await conn.execute(select(chat_message.c.id).where(and_(
                chat_message.c.id == message_id, chat_message.c.session_id == session_id,
                chat_message.c.owner_id == owner_id, chat_message.c.alt_group == alt_group,
                chat_message.c.deleted == False)))).first()  # noqa: E712
            if member is None:
                return False
            await conn.execute(update(chat_message).where(and_(
                chat_message.c.session_id == session_id, chat_message.c.owner_id == owner_id,
                chat_message.c.alt_group == alt_group)).values(alt_selected=(chat_message.c.id == message_id)))
        return True

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

    async def clear(self, *, owner_id: int, session_id: int) -> int:
        """清空一个会话的全部消息（软删）。只影响这一个会话，别的会话不受影响。

        为什么软删而不物理删除：编辑、删除消息的既有语义都是软删，
        画像/记忆抽取按 message_id 回溯来源，物理删会让来源指向不存在的行。
        """
        async with self._engine.begin() as conn:
            res = await conn.execute(update(chat_message).where(and_(
                chat_message.c.session_id == session_id,
                chat_message.c.owner_id == owner_id,
                chat_message.c.deleted == False))  # noqa: E712
                .values(deleted=True))
        return res.rowcount or 0


class SqlQueueStore:
    """排队输入。状态转移只允许 D §3.3 列出的那几条，其余拒绝。"""

    ALLOWED = QUEUE_TRANSITIONS  # 单一来源：store/port.py

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


class SqlRoleStore:
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


class SqlUploadStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def create(self, record) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(insert(upload).values(
                id=record.id, owner_id=record.owner_id, object_key=record.object_key, mime=record.mime,
                size=record.size, width=record.width, height=record.height, referenced=False,
                created_at=record.created_at))

    async def get_owned(self, *, owner_id: int, upload_id: str):
        async with self._engine.connect() as conn:
            row = (await conn.execute(select(upload).where(and_(
                upload.c.id == upload_id, upload.c.owner_id == owner_id)))).mappings().first()
        if row is None:
            return None
        return UploadRecord(row["id"], row["owner_id"], row["object_key"], row["mime"], row["size"],
                            row["width"] or 0, row["height"] or 0, bool(row["referenced"]), row["created_at"])


class SqlConfirmationStore:
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

    async def expire_due(self, *, now) -> int:
        """把已过期的待确认置 expired。条件更新：重复执行结果相同。"""
        async with self._engine.begin() as conn:
            res = await conn.execute(update(action_confirmation).where(and_(
                action_confirmation.c.status == "pending", action_confirmation.c.expires_at <= now))
                .values(status="expired", decided_at=now))
        return res.rowcount

    async def finish(self, *, owner_id: int, confirmation_id: str, status: str) -> bool:
        """执行结束：只允许从 processing 转到 executed/failed。"""
        async with self._engine.begin() as conn:
            res = await conn.execute(update(action_confirmation).where(and_(
                action_confirmation.c.id == confirmation_id, action_confirmation.c.owner_id == owner_id,
                action_confirmation.c.status == "processing")).values(status=status))
        return res.rowcount == 1


class SqlToolCallStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def trim_before(self, *, cutoff) -> int:
        from sqlalchemy import delete as sa_delete

        async with self._engine.begin() as conn:
            res = await conn.execute(sa_delete(tool_call).where(tool_call.c.created_at < cutoff))
        return res.rowcount

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
                         r["client_message_id"], r["turn_id"], bool(r["interrupted"]), r["created_at"], dict(meta or {}),
                         alt_group=r["alt_group"], alt_selected=bool(r["alt_selected"]))


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
    expires = r["expires_at"]
    # 数据库存的是不带时区的时间（UTC）；读回来若直接与 datetime.now(UTC) 比较会抛
    # TypeError: can't compare offset-naive and offset-aware。库里统一按 UTC 解释。
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return ConfirmationRecord(r["id"], r["owner_id"], r["session_id"], r["turn_id"], r["tool"], dict(args or {}),
                              r["args_fingerprint"], r["title"], r["summary"], r["status"], expires)
