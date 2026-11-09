"""A stop request is stored on the session row, so a run in another worker can see it."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.adapters import deerflow_harness_client as harness
from jc.db.base import Base
from jc.models.agent import AgentSession
from jc.models.user import User


@pytest.fixture
async def sessions(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/cancel.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        db.add(AgentSession(
            id="ags_1", user_id="u1", status="active", deerflow_thread_id="thr_1",
        ))
        await db.commit()
    import jc.db.session as db_session

    monkeypatch.setattr(db_session, "AsyncSessionLocal", maker)
    yield maker
    await engine.dispose()


async def _set_requested(maker, value: datetime | None) -> None:
    async with maker() as db:
        row = await db.get(AgentSession, "ags_1")
        row.cancel_requested_at = value
        await db.commit()


async def test_no_request_means_keep_running(sessions):
    since = datetime.now(UTC)
    assert await harness._stop_requested_since("ags_1", since) is False


async def test_request_after_run_start_stops_the_run(sessions):
    since = datetime.now(UTC)
    await _set_requested(sessions, since + timedelta(seconds=5))
    assert await harness._stop_requested_since("ags_1", since) is True


async def test_request_before_run_start_does_not_stop_a_later_run(sessions):
    """A stop given to an earlier run must not cancel the next one."""
    since = datetime.now(UTC)
    await _set_requested(sessions, since - timedelta(minutes=5))
    assert await harness._stop_requested_since("ags_1", since) is False


async def test_unknown_session_is_not_a_stop(sessions):
    assert await harness._stop_requested_since("ags_missing", datetime.now(UTC)) is False


async def test_failed_read_does_not_stop_the_run(monkeypatch):
    import jc.db.session as db_session

    class _Broken:
        async def __aenter__(self):
            raise RuntimeError("database unavailable")

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(db_session, "AsyncSessionLocal", lambda: _Broken())
    assert await harness._stop_requested_since("ags_1", datetime.now(UTC)) is False


def test_migration_025_follows_024():
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1] / "alembic" / "versions" / "025_agent_cancel_request.py"
    )
    spec = importlib.util.spec_from_file_location("m025", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == "024_mock_report_queue"
    assert module.revision == "025_agent_cancel_request"
