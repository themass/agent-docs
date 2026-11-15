"""The audit list must not load the payload columns.

Measured on production before this test existed: 113 calls held 1.35 MB in
`prompt_text`/`response_text`/`reasoning_text` (1.19 MB of it prompt text),
against ~9 KB for every other column of those rows combined. `select(LlmCall)`
fetched all of it for a table that renders none of it, so the endpoint took
2.8 s instead of ~0.4 s and shipped 68 KB to the browser.

A duration test would need a real remote database to fail, so this pins the
mechanism instead: the emitted SQL must not name those columns. That is what
breaks if someone drops the `defer` options later.
"""

from __future__ import annotations

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.db.base import Base
from jc.models.llm_call import LlmCall
from jc.stores.llm_call_store import LlmCallStore

PAYLOAD_COLUMNS = ("prompt_text", "response_text", "reasoning_text")


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/llm.sqlite")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        session.add(
            LlmCall(
                id="call_1",
                scenario="coach",
                caller="agent",
                channel="harness",
                status="success",
                prompt_text="x" * 50_000,
                response_text="y" * 10_000,
                reasoning_text="z" * 5_000,
            )
        )
        await session.commit()
    yield sessions, engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_list_calls_does_not_select_payload_columns(db):
    sessions, engine = db
    seen: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def capture(conn, cursor, statement, parameters, context, executemany):
        seen.append(statement)

    async with sessions() as session:
        rows, total, _, _ = await LlmCallStore(session).list_calls(limit=10)

    assert total == 1
    assert len(rows) == 1
    selects = [s for s in seen if s.lstrip().upper().startswith("SELECT")]
    assert selects, "no SELECT was issued"
    for column in PAYLOAD_COLUMNS:
        for statement in selects:
            assert column not in statement, (
                f"list query selects {column}, which is what made the endpoint "
                f"transfer 1.35 MB of payload for a table that shows none of it:\n{statement}"
            )


@pytest.mark.asyncio
async def test_detail_still_reads_payload(db):
    """Deferring is a list-only decision; the detail view must keep the text."""
    sessions, _ = db
    async with sessions() as session:
        row = await LlmCallStore(session).get_call("call_1")
    assert row is not None
    assert row.prompt_text == "x" * 50_000
