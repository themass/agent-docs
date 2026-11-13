"""主动消息的三块持久化：用户偏好、应用内收件箱、投递账本。

这三样原来都在进程内（``InMemoryPreferencesStore`` / ``InAppDelivery`` / ``InMemorySendLedger``），
带来的都是同一个问题：重启即丢，而且多 worker 时各记各的。具体后果：

- 偏好：用户关掉主动消息，重启后又开始收到；
- 收件箱：她主动发了一句，用户还没打开应用，消息就没了；
- 账本：频控是「每天 2 次」，两个 worker 各自计数，用户一天收到 4 次。

接口与原来的内存实现一致，装配处只换实例，调用方不用改。
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.adapters.store.sql.schema import (
    delivery_receipt,
    proactive_preferences,
    send_record,
)
from companion.domain.proactive.models import InitiativePreferences, InitiativeState, SendRecord
from companion.ports.delivery import DeliveryReceipt, Channel


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _apply_patch(current: InitiativePreferences, patch: dict[str, Any]) -> InitiativePreferences:
    """只接受 dataclass 上真实存在的字段；时间字段接受 "HH:MM" 字符串或 time。"""
    from dataclasses import replace

    allowed = {f.name for f in current.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    changes: dict[str, Any] = {}
    for key, value in patch.items():
        if key not in allowed:
            continue
        if key in ("quiet_start", "quiet_end") and isinstance(value, str):
            hour, _, minute = value.partition(":")
            changes[key] = time(int(hour), int(minute or 0))
        elif key == "paused_until" and isinstance(value, str):
            # 空串 = 恢复（旧接口的约定：传 "" 表示不再暂停）。
            # 直接 fromisoformat("") 会抛 ValueError，把「恢复」变成 500。
            changes[key] = (datetime.fromisoformat(value.replace("Z", "+00:00"))
                            if value.strip() else None)
        else:
            changes[key] = value
    return replace(current, **changes)


class SqlPreferencesStore:
    """用户对「她主动找你」的偏好。没有记录时返回默认值，不写空行。"""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def load(self, user_id: str) -> InitiativePreferences:
        async with self._engine.connect() as conn:
            row = (await conn.execute(
                select(proactive_preferences).where(proactive_preferences.c.owner_id == int(user_id))
            )).mappings().first()
        if row is None:
            return InitiativePreferences()
        return InitiativePreferences(
            events_enabled=bool(row["events_enabled"]),
            greetings_enabled=bool(row["greetings_enabled"]),
            call_enabled=bool(row["call_enabled"]),
            quiet_start=time.fromisoformat(str(row["quiet_start"])),
            quiet_end=time.fromisoformat(str(row["quiet_end"])),
            max_per_day=int(row["max_per_day"]),
            max_per_week=int(row["max_per_week"]),
            paused_until=_as_utc(row["paused_until"]) if row["paused_until"] else None,
        )

    async def save(self, user_id: str, patch: dict[str, Any]) -> InitiativePreferences:
        current = _apply_patch(await self.load(user_id), patch)
        values = dict(
            owner_id=int(user_id),
            events_enabled=current.events_enabled,
            greetings_enabled=current.greetings_enabled,
            call_enabled=current.call_enabled,
            quiet_start=current.quiet_start.strftime("%H:%M"),
            quiet_end=current.quiet_end.strftime("%H:%M"),
            max_per_day=current.max_per_day,
            max_per_week=current.max_per_week,
            paused_until=current.paused_until.replace(tzinfo=None) if current.paused_until else None,
            updated_at=_now(),
        )
        async with self._engine.begin() as conn:
            exists = (await conn.execute(
                select(proactive_preferences.c.owner_id)
                .where(proactive_preferences.c.owner_id == int(user_id))
            )).first()
            if exists:
                await conn.execute(update(proactive_preferences)
                                   .where(proactive_preferences.c.owner_id == int(user_id)).values(**values))
            else:
                await conn.execute(insert(proactive_preferences).values(**values))
        return current


class SqlDelivery:
    """应用内收件箱。写入即可见，取走（drain）后标记已读而不是删除，便于事后对账。"""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def deliver(self, *, user_id: str, character_id: str, text: str, channel: Channel,
                      at: datetime, meta: dict[str, Any] | None = None) -> DeliveryReceipt:
        import secrets

        receipt = DeliveryReceipt(
            id=f"inapp-{secrets.token_urlsafe(12)}",
            user_id=user_id,
            character_id=character_id,
            text=text,
            channel=channel,
            at=at,
            meta=dict(meta or {}),
        )
        async with self._engine.begin() as conn:
            await conn.execute(insert(delivery_receipt).values(
                id=receipt.id[:_ID_MAX], owner_id=int(user_id), role_id=character_id or "",
                text=text, channel=channel.value if hasattr(channel, "value") else str(channel),
                meta=receipt.meta, at=_as_utc(at).replace(tzinfo=None), created_at=_now()))
        return receipt

    async def inbox(self, user_id: str) -> list[DeliveryReceipt]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(
                select(delivery_receipt)
                .where(delivery_receipt.c.owner_id == int(user_id), delivery_receipt.c.drained_at.is_(None))
                .order_by(delivery_receipt.c.at))).mappings().all()
        return [_receipt(r) for r in rows]

    async def drain(self, user_id: str, *, limit: int = 50) -> list[DeliveryReceipt]:
        async with self._engine.begin() as conn:
            rows = (await conn.execute(
                select(delivery_receipt)
                .where(delivery_receipt.c.owner_id == int(user_id), delivery_receipt.c.drained_at.is_(None))
                .order_by(delivery_receipt.c.at).limit(limit))).mappings().all()
            if rows:
                await conn.execute(update(delivery_receipt)
                                   .where(delivery_receipt.c.id.in_([r["id"] for r in rows]))
                                   .values(drained_at=_now()))
        return [_receipt(r) for r in rows]


_ID_MAX = 48


def _receipt(row: Any) -> DeliveryReceipt:
    raw = row["channel"]
    try:
        channel = Channel(raw)
    except ValueError:
        channel = Channel.IN_APP
    return DeliveryReceipt(
        id=row["id"], user_id=str(row["owner_id"]), character_id=row["role_id"], text=row["text"],
        channel=channel, at=_as_utc(row["at"]), meta=dict(row["meta"] or {}))


class SqlSendLedger:
    """投递账本：频控按它算「今天/本周已经发过几次」。跨重启、跨进程都对。"""

    def __init__(self, engine: AsyncEngine, *, keep_days: int = 60) -> None:
        self._engine = engine
        self._keep_days = keep_days

    async def record(self, user_id: str, record: SendRecord) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(insert(send_record).values(
                owner_id=int(user_id), at=_as_utc(record.at).replace(tzinfo=None),
                channel=record.channel.value if hasattr(record.channel, "value") else str(record.channel),
                trigger=(record.trigger or "")[:64]))

    async def state_for(self, user_id: str) -> InitiativeState:
        from datetime import timedelta

        since = _now() - timedelta(days=self._keep_days)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(
                select(send_record.c.at, send_record.c.channel, send_record.c.trigger)
                .where(send_record.c.owner_id == int(user_id), send_record.c.at >= since)
                .order_by(send_record.c.at))).all()
        sent = []
        for at, channel, trigger in rows:
            try:
                ch = Channel(channel)
            except ValueError:
                ch = Channel.IN_APP
            sent.append(SendRecord(at=_as_utc(at), channel=ch, trigger=trigger or ""))
        return InitiativeState(sent=sent)

    async def records_for(self, user_id: str) -> list[SendRecord]:
        return (await self.state_for(user_id)).sent

    async def prune(self, *, before: datetime) -> int:
        async with self._engine.begin() as conn:
            result = await conn.execute(delete(send_record).where(send_record.c.at < before))
        return result.rowcount or 0
