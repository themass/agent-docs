"""用户画像的 SQL 实现。语义见 ports/persona.py 与 domain/persona/model.py。

来源事实 id 存成 JSON 列；联动删除在 Python 里判断而不用数据库的 JSON 函数，
这样 Postgres（JSONB）和 MySQL 5.6（文本）行为一致。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.adapters.store.sql.schema import persona_cursor, persona_entry
from companion.domain.persona.model import APPEND, UPDATE, MergeAction, ProfileEntry


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


def _naive(value: datetime | None) -> datetime | None:
    return value.astimezone(UTC).replace(tzinfo=None) if value is not None and value.tzinfo else value


def _entry(r) -> ProfileEntry:
    return ProfileEntry(
        id=r["id"], topic=r["topic"], memo=r["memo"], section=r["section"], is_inference=bool(r["is_inference"]),
        confidence=float(r["confidence"]), source_fact_ids=tuple(r["source_fact_ids"] or ()),
        mentioned_at=r["mentioned_at"], happened_at=r["happened_at"], superseded_by=r["superseded_by"],
        suppressed=bool(r["suppressed"]))


class SqlPersonaStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def list_entries(self, *, owner_id: int, role_id: str, include_history: bool = False) -> list[ProfileEntry]:
        cond = [persona_entry.c.owner_id == owner_id, persona_entry.c.role_id == role_id]
        if not include_history:
            cond += [persona_entry.c.superseded_by.is_(None), persona_entry.c.suppressed == False]  # noqa: E712
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(persona_entry).where(and_(*cond))
                                       .order_by(persona_entry.c.id))).mappings().all()
        return [_entry(r) for r in rows]

    async def apply(self, *, owner_id: int, role_id: str, actions: list[MergeAction]) -> int:
        now = _now()
        written = 0
        async with self._engine.begin() as conn:
            for action in actions:
                if action.kind not in (APPEND, UPDATE):
                    continue
                d = action.draft
                res = await conn.execute(insert(persona_entry).values(
                    owner_id=owner_id, role_id=role_id, topic=d.topic, memo=d.memo, section=d.section,
                    is_inference=d.is_inference, confidence=d.confidence, source_fact_ids=list(d.source_fact_ids),
                    mentioned_at=_naive(d.mentioned_at), happened_at=_naive(d.happened_at),
                    suppressed=False, created_at=now, updated_at=now))
                if action.kind == UPDATE and action.replaces is not None:
                    # 只增不改：旧条目保留，标为被新条目取代（条件更新，别人已取代过的不再动）
                    await conn.execute(update(persona_entry).where(and_(
                        persona_entry.c.id == action.replaces, persona_entry.c.owner_id == owner_id,
                        persona_entry.c.superseded_by.is_(None)))
                        .values(superseded_by=res.inserted_primary_key[0], updated_at=now))
                written += 1
        return written

    async def suppress(self, *, owner_id: int, entry_id: int) -> bool:
        async with self._engine.begin() as conn:
            res = await conn.execute(update(persona_entry).where(and_(
                persona_entry.c.id == entry_id, persona_entry.c.owner_id == owner_id))
                .values(suppressed=True, updated_at=_now()))
        return res.rowcount == 1

    async def delete(self, *, owner_id: int, entry_id: int) -> bool:
        async with self._engine.begin() as conn:
            res = await conn.execute(delete(persona_entry).where(and_(
                persona_entry.c.id == entry_id, persona_entry.c.owner_id == owner_id)))
        return res.rowcount == 1

    async def drop_for_facts(self, *, owner_id: int, fact_ids: list[str]) -> int:
        wanted = set(fact_ids)
        if not wanted:
            return 0
        async with self._engine.begin() as conn:
            rows = (await conn.execute(select(persona_entry.c.id, persona_entry.c.source_fact_ids).where(
                persona_entry.c.owner_id == owner_id))).all()
            doomed = [rid for rid, sources in rows if sources and set(sources) <= wanted]
            if doomed:
                await conn.execute(delete(persona_entry).where(persona_entry.c.id.in_(doomed)))
        return len(doomed)

    async def delete_user(self, *, owner_id: int) -> int:
        async with self._engine.begin() as conn:
            total = (await conn.execute(delete(persona_entry).where(persona_entry.c.owner_id == owner_id))).rowcount
            await conn.execute(delete(persona_cursor).where(persona_cursor.c.owner_id == owner_id))
        return total

    async def advance(self, *, owner_id: int, role_id: str, last_message_id: int, add_chars: int) -> int:
        now = _now()
        async with self._engine.begin() as conn:
            row = (await conn.execute(select(persona_cursor.c.pending_chars, persona_cursor.c.last_message_id).where(
                and_(persona_cursor.c.owner_id == owner_id, persona_cursor.c.role_id == role_id)
            ).with_for_update())).first()
            if row is None:
                await conn.execute(insert(persona_cursor).values(
                    owner_id=owner_id, role_id=role_id, last_message_id=0, pending_chars=add_chars, updated_at=now))
                return add_chars
            pending = row.pending_chars + add_chars
            await conn.execute(update(persona_cursor).where(and_(
                persona_cursor.c.owner_id == owner_id, persona_cursor.c.role_id == role_id))
                .values(pending_chars=pending, updated_at=now))
        return pending

    async def cursor(self, *, owner_id: int, role_id: str) -> tuple[int, int]:
        async with self._engine.connect() as conn:
            row = (await conn.execute(select(persona_cursor.c.last_message_id, persona_cursor.c.pending_chars).where(
                and_(persona_cursor.c.owner_id == owner_id, persona_cursor.c.role_id == role_id)))).first()
        return (int(row.last_message_id), int(row.pending_chars)) if row else (0, 0)

    async def reset_pending(self, *, owner_id: int, role_id: str, last_message_id: int) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(update(persona_cursor).where(and_(
                persona_cursor.c.owner_id == owner_id, persona_cursor.c.role_id == role_id))
                .values(pending_chars=0, last_message_id=last_message_id, updated_at=_now()))
