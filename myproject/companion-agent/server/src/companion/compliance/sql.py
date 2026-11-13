"""合规底座的 SQL 实现。语义见 ports/compliance.py。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.adapters.store.sql.schema import usage_span, user_consent
from companion.compliance.port import REMIND_AFTER_MINUTES, SPAN_GAP_MINUTES, Consent, UsageState


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


def _naive(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


class SqlComplianceStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def consent(self, *, owner_id: int) -> Consent:
        async with self._engine.connect() as conn:
            row = (await conn.execute(select(user_consent).where(user_consent.c.owner_id == owner_id))).first()
        if row is None:
            return Consent()          # 没有记录 = 默认值（训练用途不同意、主动联系开启）
        return Consent(training_consent=bool(row.training_consent),
                       proactive_enabled=bool(row.proactive_enabled),
                       age_verified_adult=bool(row.age_verified_adult),
                       qa_retention=bool(row.qa_retention))

    async def update_consent(self, *, owner_id: int, training_consent: bool | None = None,
                             proactive_enabled: bool | None = None,
                             age_verified_adult: bool | None = None,
                             qa_retention: bool | None = None) -> Consent:
        now = _now()
        async with self._engine.begin() as conn:
            current = (await conn.execute(select(user_consent).where(
                user_consent.c.owner_id == owner_id).with_for_update())).first()
            if current is None:
                await conn.execute(insert(user_consent).values(
                    owner_id=owner_id,
                    training_consent=bool(training_consent) if training_consent is not None else False,
                    proactive_enabled=bool(proactive_enabled) if proactive_enabled is not None else True,
                    age_verified_adult=bool(age_verified_adult) if age_verified_adult is not None else False,
                    qa_retention=bool(qa_retention) if qa_retention is not None else False,
                    updated_at=now))
            else:
                values = {"updated_at": now}
                if training_consent is not None:
                    values["training_consent"] = training_consent
                if proactive_enabled is not None:
                    values["proactive_enabled"] = proactive_enabled
                if age_verified_adult is not None:
                    values["age_verified_adult"] = age_verified_adult
                if qa_retention is not None:
                    values["qa_retention"] = qa_retention
                await conn.execute(update(user_consent).where(user_consent.c.owner_id == owner_id).values(**values))
        return await self.consent(owner_id=owner_id)

    async def touch_usage(self, *, owner_id: int, now: datetime) -> UsageState:
        current = _naive(now)
        gap = timedelta(minutes=SPAN_GAP_MINUTES)
        remind_at = timedelta(minutes=REMIND_AFTER_MINUTES)
        async with self._engine.begin() as conn:
            row = (await conn.execute(select(usage_span).where(
                usage_span.c.owner_id == owner_id).with_for_update())).first()
            if row is None or row.last_seen_at is None or current - row.last_seen_at > gap:
                if row is None:
                    await conn.execute(insert(usage_span).values(
                        owner_id=owner_id, started_at=current, last_seen_at=current, reminded_at=None,
                        updated_at=current))
                else:
                    await conn.execute(update(usage_span).where(usage_span.c.owner_id == owner_id).values(
                        started_at=current, last_seen_at=current, reminded_at=None, updated_at=current))
                return UsageState(span_minutes=0, should_remind=False)
            started = row.started_at
            elapsed = current - started
            should = elapsed >= remind_at and row.reminded_at is None
            await conn.execute(update(usage_span).where(usage_span.c.owner_id == owner_id).values(
                last_seen_at=current, reminded_at=current if should else row.reminded_at, updated_at=current))
        return UsageState(span_minutes=int(elapsed.total_seconds() // 60), should_remind=should)

    async def delete_user(self, *, owner_id: int) -> int:
        async with self._engine.begin() as conn:
            total = (await conn.execute(delete(user_consent).where(user_consent.c.owner_id == owner_id))).rowcount
            total += (await conn.execute(delete(usage_span).where(usage_span.c.owner_id == owner_id))).rowcount
        return total
