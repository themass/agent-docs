"""`UTCDateTime` round-trips timestamps as UTC-aware, regardless of what the
driver hands back.

This matters beyond SQLite correctness: MySQL's `DATETIME` has no timezone
concept, so `aiomysql` always returns a *naive* datetime, no matter what
SQLAlchemy column type requested it. A naive `created_at` then serializes via
Pydantic's `.isoformat()` with no `Z`/offset suffix, and the frontend's
`new Date(iso)` treats an offset-less ISO string as local time — so a UTC
instant was displayed as if it already were wall-clock browser time (8 hours
fast in Asia/Shanghai). `UTCDateTime` is the single point that prevents this:
`process_bind_param` always stores a naive-but-UTC value, and
`process_result_value` always re-attaches `tzinfo=UTC` on the way out.

These tests use real SQLAlchemy against SQLite (no remote resources), same
pattern as `test_agent_message_store.py`. SQLite is actually the *opposite*
failure mode from MySQL: it stores whatever Python object it's given,
including tzinfo, so a round-trip test here also pins that bind-side
normalization (convert-to-UTC-then-strip) does not silently corrupt a
non-UTC-aware input.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import Column, MetaData, String, Table
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.db.types import UTCDateTime


@pytest.fixture
async def engine_and_table():
    metadata = MetaData()
    table = Table(
        "utc_datetime_probe",
        metadata,
        Column("id", String(10), primary_key=True),
        Column("ts", UTCDateTime, nullable=True),
    )
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield engine, table
    await engine.dispose()


@pytest.mark.asyncio
async def test_aware_utc_value_round_trips_with_tzinfo_intact(engine_and_table) -> None:
    engine, table = engine_and_table
    written = datetime(2026, 10, 19, 8, 30, 0, tzinfo=UTC)
    async with engine.begin() as conn:
        await conn.execute(table.insert().values(id="row_1", ts=written))
    async with engine.connect() as conn:
        row = (await conn.execute(table.select().where(table.c.id == "row_1"))).one()
    assert row.ts.tzinfo is not None
    assert row.ts.astimezone(UTC) == written


@pytest.mark.asyncio
async def test_naive_datetime_in_db_is_read_back_as_utc_not_silently_wrong(engine_and_table) -> None:
    """Simulates the MySQL `aiomysql` behavior directly: a bare `DateTime` column

    (no `UTCDateTime` on the write side, as if a migration or manual SQL wrote a
    naive value straight into the column) must still come back from
    `UTCDateTime.process_result_value` labeled as UTC, not left ambiguous.
    """
    engine, table = engine_and_table
    naive = datetime(2026, 10, 19, 8, 30, 0)
    async with engine.begin() as conn:
        # Bypass the type's bind processing to simulate a raw driver value,
        # matching how aiomysql would hand back a MySQL DATETIME column.
        await conn.exec_driver_sql(
            "INSERT INTO utc_datetime_probe (id, ts) VALUES (?, ?)",
            ("row_2", naive.isoformat(sep=" ")),
        )
    async with engine.connect() as conn:
        row = (await conn.execute(table.select().where(table.c.id == "row_2"))).one()
    assert row.ts.tzinfo is not None
    assert row.ts.replace(tzinfo=None) == naive


@pytest.mark.asyncio
async def test_non_utc_aware_input_is_normalized_to_utc_before_storage(engine_and_table) -> None:
    """A caller that accidentally passes e.g. +08:00 must not have that offset

    silently treated as if it were already UTC — the bind side converts first.
    """
    engine, table = engine_and_table
    shanghai = timezone(timedelta(hours=8))
    written = datetime(2026, 10, 19, 16, 30, 0, tzinfo=shanghai)  # == 08:30 UTC
    async with engine.begin() as conn:
        await conn.execute(table.insert().values(id="row_3", ts=written))
    async with engine.connect() as conn:
        row = (await conn.execute(table.select().where(table.c.id == "row_3"))).one()
    assert row.ts.astimezone(UTC) == datetime(2026, 10, 19, 8, 30, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_null_round_trips_as_none(engine_and_table) -> None:
    engine, table = engine_and_table
    async with engine.begin() as conn:
        await conn.execute(table.insert().values(id="row_4", ts=None))
    async with engine.connect() as conn:
        row = (await conn.execute(table.select().where(table.c.id == "row_4"))).one()
    assert row.ts is None
