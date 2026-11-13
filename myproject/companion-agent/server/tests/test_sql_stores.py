"""MySQL 仓储与迁移的集成测试（T2、T13）。

需要 COMPANION_TEST_MYSQL_URL。库可以与 Java 共用（vpn），但测试只碰 ca_ 前缀的表：
守卫发现任何无前缀的表会直接失败。测试开始时删除并重建 ca_ 表。
"""

import asyncio
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

URL = (os.environ.get("COMPANION_TEST_DATABASE_URL") or os.environ.get("COMPANION_TEST_MYSQL_URL", ""))
pytestmark = pytest.mark.skipif(not URL, reason="COMPANION_TEST_DATABASE_URL not set")
ROOT = Path(__file__).resolve().parents[1]


def _guard_database_name() -> None:
    """测试会删除并重建表。vpn 库与 Java 后端共用，所以只允许碰带 ca_ 前缀的表。"""
    from companion.adapters.store.sql.schema import TABLE_PREFIX, metadata

    foreign = [t for t in metadata.tables if not t.startswith(TABLE_PREFIX)]
    if foreign:
        raise AssertionError(f"refusing to run: tables without {TABLE_PREFIX!r} prefix: {foreign}")


@pytest.fixture(scope="module")
def migrated():
    _guard_database_name()
    env = {**os.environ, "COMPANION_MYSQL_URL": URL, "COMPANION_DATABASE_URL": URL, "PYTHONPATH": str(ROOT / "src")}
    py = sys.executable
    subprocess.run([py, "-m", "alembic", "downgrade", "base"], cwd=ROOT, env=env, check=True, capture_output=True)
    subprocess.run([py, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True, capture_output=True)
    yield URL
    subprocess.run([py, "-m", "alembic", "downgrade", "base"], cwd=ROOT, env=env, check=True, capture_output=True)


def test_migration_is_reversible_and_creates_all_tables(migrated):
    from sqlalchemy import create_engine, inspect

    from companion.adapters.store.sql.schema import metadata

    sync_url = migrated.replace("+aiomysql", "+pymysql")
    engine = create_engine(sync_url)
    try:
        names = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    expected = set(metadata.tables) - {"alembic_version"}
    assert expected <= names


async def _engine(url):
    from sqlalchemy.ext.asyncio import create_async_engine

    return create_async_engine(url, pool_pre_ping=True)


def run(coro):
    return asyncio.run(coro)


def test_message_store_attach_edit_and_soft_delete(migrated):
    from companion.adapters.store.sql.repositories import SqlMessageStore, SqlSessionStore

    async def go():
        engine = await _engine(migrated)
        try:
            sessions = SqlSessionStore(engine)
            messages = SqlMessageStore(engine)
            s = await sessions.create(owner_id=9001, role_id="linche", name="t", locale="zh-CN")
            m = await messages.append(owner_id=9001, session_id=s.id, role="user", content="你好", kind="chat",
                                      client_message_id="c-1", turn_id=None, meta={})
            assert (await messages.find_by_client_id(owner_id=9001, session_id=s.id,
                                                     client_message_id="c-1")).id == m.id
            assert await messages.attach_turn(owner_id=9001, session_id=s.id, message_ids=[m.id],
                                              turn_id="01AAAAAAAAAAAAAAAAAAAAAAAA") == 1
            assert await messages.attach_turn(owner_id=9001, session_id=s.id, message_ids=[m.id],
                                              turn_id="01BBBBBBBBBBBBBBBBBBBBBBBB") == 0  # 只挂一次
            assert await messages.edit(owner_id=9001, message_id=m.id, content="改过的")
            assert await messages.get(owner_id=9002, message_id=m.id) is None  # 他人不可见
            assert await messages.soft_delete(owner_id=9001, message_id=m.id)
            assert await messages.get(owner_id=9001, message_id=m.id) is None
        finally:
            await engine.dispose()

    run(go())


def test_queue_transitions_follow_the_table_and_refuse_illegal_ones(migrated):
    from companion.adapters.store.sql.repositories import SqlMessageStore, SqlQueueStore, SqlSessionStore

    async def go():
        engine = await _engine(migrated)
        try:
            s = await SqlSessionStore(engine).create(owner_id=9003, role_id="linche", name="q", locale="zh-CN")
            m = await SqlMessageStore(engine).append(owner_id=9003, session_id=s.id, role="user", content="排队",
                                                       kind="chat", client_message_id=None, turn_id=None, meta={})
            queue = SqlQueueStore(engine)
            item = await queue.enqueue(owner_id=9003, session_id=s.id, message_id=m.id,
                                       client_message_id=None, text="排队")
            assert await queue.transition(item_id=item.id, from_status="queued", to_status="draining")
            with pytest.raises(ValueError):
                await queue.transition(item_id=item.id, from_status="drained", to_status="queued")
            assert await queue.transition(item_id=item.id, from_status="draining", to_status="drained",
                                          turn_id="01CCCCCCCCCCCCCCCCCCCCCCCC")
            assert await queue.list_status(owner_id=9003, session_id=s.id, status="drained")
        finally:
            await engine.dispose()

    run(go())


def test_confirmation_claim_finish_and_expiry(migrated):
    from companion.adapters.store.sql.repositories import SqlConfirmationStore
    from companion.ports.store import ConfirmationRecord

    async def go():
        engine = await _engine(migrated)
        try:
            store = SqlConfirmationStore(engine)
            now = datetime.now(UTC).replace(tzinfo=None)
            rec = ConfirmationRecord(id="cfm_test_1", owner_id=9004, session_id=1, turn_id=None, tool="create_reminder",
                                     args={"title": "吃药"}, args_fingerprint="0123456789abcdef", title="提醒",
                                     summary="s", status="pending", expires_at=now + timedelta(hours=1))
            await store.create(rec)
            assert await store.decide(owner_id=9004, confirmation_id="cfm_test_1", status="processing")
            assert not await store.decide(owner_id=9004, confirmation_id="cfm_test_1", status="processing")
            assert await store.finish(owner_id=9004, confirmation_id="cfm_test_1", status="executed")
            expired = ConfirmationRecord(**{**rec.__dict__, "id": "cfm_test_2", "expires_at": now - timedelta(minutes=1)})
            await store.create(expired)
            assert await store.expire_due(now=now) >= 1
        finally:
            await engine.dispose()

    run(go())


def test_job_claim_is_exclusive_and_dedupe_holds(migrated):
    from companion.jobs.sql import SqlJobStore

    async def go():
        engine = await _engine(migrated)
        try:
            jobs = SqlJobStore(engine)
            now = datetime.now(UTC).replace(tzinfo=None)
            import uuid
            key = "t-dedupe-" + uuid.uuid4().hex
            assert await jobs.enqueue(kind="audit.trim", payload={}, run_after=now, dedupe_key=key)
            assert not await jobs.enqueue(kind="audit.trim", payload={}, run_after=now, dedupe_key=key)
            first = await jobs.claim(owner="w1", now=now, lease_until=now + timedelta(minutes=5), limit=50)
            second = await jobs.claim(owner="w2", now=now, lease_until=now + timedelta(minutes=5), limit=50)
            claimed_ids = {j.id for j in first}
            assert not claimed_ids & {j.id for j in second}
            mine = next(j for j in first if j.dedupe_key == key)
            assert await jobs.complete(job_id=mine.id, owner="w1")
            assert not await jobs.complete(job_id=mine.id, owner="w2")
        finally:
            await engine.dispose()

    run(go())


def test_tool_call_audit_trim_removes_only_old_rows(migrated):
    from companion.adapters.store.sql.repositories import SqlToolCallStore
    from companion.ports.tools import ToolCallRecord

    async def go():
        engine = await _engine(migrated)
        try:
            store = SqlToolCallStore(engine)
            await store.append(ToolCallRecord(turn_id="01DDDDDDDDDDDDDDDDDDDDDDDD", owner_id=9005, tool="recall_facts",
                                              permission="read", args_fingerprint="0123456789abcdef",
                                              status="executed", latency_ms=5, result_chars=10))
            removed = await store.trim_before(cutoff=datetime(2000, 1, 1))
            assert removed == 0
            assert await store.trim_before(cutoff=datetime(2100, 1, 1)) >= 1
        finally:
            await engine.dispose()

    run(go())
