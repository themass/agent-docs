"""A finished session queues its report; a background worker claims it and runs the reviewer.

The report used to be generated when its page was first opened, which held the page for the whole
review and left a failure with nothing to say. The session row is now the queue: ending it marks the
report `queued`, a worker claims it with a conditional update (one winner, a lease for a worker that
died, a cap on runs) and the page only reads the status."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.agent import subtask
from jc.authz.scope import RunScope
from jc.db.base import Base
from jc.models.interview import AnswerAttempt, InterviewQuestion, MockSession
from jc.models.profile import Profile
from jc.models.user import User
from jc.services import mock_report_queue
from jc.services.mock_guard_service import end, plan
from jc.services.mock_report_queue import (
    CLAIM_LEASE,
    MAX_REPORT_RUNS,
    _claim_one,
    claim_next_report,
    generate_report,
    requeue_failed,
    run_mock_report_dispatcher,
)
from reviewer_agent_fake import FakeClientFactory, FakeReviewerAgent

ANSWER = "我负责把结算接口从单表拆成两张表，耗时三周。"
GOOD_REPORT = {"questions": [{"question_id": "q1", "scores": {"depth": 6},
                              "evidence": {"depth": "拆成两张表"}}]}
MAIN = {"question_id": "q1", "kind": "main", "parent_question_id": None}
NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/queue.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    makers = async_sessionmaker(engine, expire_on_commit=False)
    async with makers() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(Profile(id="p1", user_id="u1", owner_kind="user",
                       payload={"experience": "结算接口拆表"}, version=1))
        db.add(InterviewQuestion(id="q1", profile_id="p1", stem="讲一个你拆分数据的经历",
                                 question_type="behavioral"))
        db.add(AnswerAttempt(id="a1", question_id="q1", profile_id="p1", mock_session_id="ms1",
                             user_answer=ANSWER, coach_feedback={}, reference_answer=None))
        await db.commit()
    yield makers
    await engine.dispose()


async def _seed(maker, *, session_id="ms1", status="completed", report_status=None, attempts=0,
                claimed_at=None, asked=None, completed_at=NOW, last_activity=None) -> None:
    coverage = {"asked": [MAIN] if asked is None else asked}
    if last_activity:
        coverage["last_activity"] = last_activity
    async with maker() as db:
        db.add(MockSession(
            id=session_id, profile_id="p1", user_id="u1", mode="full", question_ids=["q1"],
            bank_draw_count=0, generated_count=0, status=status,
            started_at=NOW - timedelta(days=3 if last_activity else 0, minutes=30),
            completed_at=completed_at if status == "completed" else None,
            coverage=coverage, report_status=report_status, report_attempts=attempts,
            report_claimed_at=claimed_at,
        ))
        await db.commit()


async def _row(maker, session_id="ms1") -> MockSession:
    async with maker() as db:
        return (await db.execute(select(MockSession).where(MockSession.id == session_id))
                ).scalar_one()


def _use_reviewer(monkeypatch, maker, agent: FakeReviewerAgent) -> None:
    monkeypatch.setattr(subtask, "get_deerflow_client", FakeClientFactory(agent))
    monkeypatch.setattr(mock_report_queue, "AsyncSessionLocal", maker)


# --- ending a session queues its report -------------------------------------------------------


@pytest.mark.asyncio
async def test_ending_a_session_queues_its_report(maker):
    # The session was just active: the guard closes one idle for a day, judged by the wall clock.
    await _seed(maker, status="active", completed_at=None,
                last_activity=datetime.now(UTC).replace(tzinfo=None).isoformat())
    async with maker() as db:
        scope = RunScope(db=db, user_id="u1", profile_id="p1", mock_session_id="ms1")
        assert (await end(scope, mock_session_id="ms1", reason="user_ended"))["accepted"] is True
    row = await _row(maker)
    assert (row.status, row.report_status, row.report_attempts) == ("completed", "queued", 0)


@pytest.mark.asyncio
async def test_the_timeout_close_queues_the_report_too(maker):
    stale = (datetime.now(UTC) - timedelta(days=3)).replace(tzinfo=None).isoformat()
    await _seed(maker, status="active", completed_at=None, last_activity=stale)
    async with maker() as db:
        scope = RunScope(db=db, user_id="u1", profile_id="p1", mock_session_id="ms1")
        await plan(scope, mock_session_id="ms1")
    row = await _row(maker)
    assert (row.status, row.report_status) == ("completed", "queued")


@pytest.mark.asyncio
async def test_a_session_that_asked_nothing_has_nothing_to_review(maker):
    # Ending right after the greeting. A review of nothing can only fail, so it is not queued.
    await _seed(maker, status="active", completed_at=None, asked=[])
    async with maker() as db:
        scope = RunScope(db=db, user_id="u1", profile_id="p1", mock_session_id="ms1")
        await end(scope, mock_session_id="ms1", reason="user_ended")
    row = await _row(maker)
    assert (row.report_status, row.report_attempts) == ("failed", MAX_REPORT_RUNS)
    assert "没有提问" in row.report_error
    async with maker() as db:
        assert await requeue_failed(db, "ms1") is False


# --- claiming ---------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_queued_report_is_claimed_once(maker):
    await _seed(maker, report_status="queued")
    async with maker() as db:
        assert await claim_next_report(db, now=NOW) == "ms1"
    async with maker() as db:
        assert await claim_next_report(db, now=NOW) is None
    row = await _row(maker)
    assert (row.report_status, row.report_attempts) == ("generating", 1)
    assert row.report_claimed_at == NOW


@pytest.mark.asyncio
async def test_two_workers_racing_for_one_report_give_exactly_one_winner(maker):
    await _seed(maker, report_status="queued")

    async def worker():
        async with maker() as db:
            return await claim_next_report(db, now=NOW)

    results = await asyncio.gather(worker(), worker())
    assert sorted(r for r in results if r) == ["ms1"] and results.count(None) == 1
    assert (await _row(maker)).report_attempts == 1


@pytest.mark.asyncio
async def test_a_claim_on_a_report_someone_else_just_took_is_refused(maker):
    # The candidate list is read before the claim, so a second worker can hold a stale list. The
    # conditional update is what keeps it from taking a report the first worker already has.
    await _seed(maker, report_status="queued")
    cutoff = NOW - CLAIM_LEASE
    async with maker() as first, maker() as second:
        assert await _claim_one(first, "ms1", now=NOW, cutoff=cutoff) is True
        await first.commit()
        assert await _claim_one(second, "ms1", now=NOW, cutoff=cutoff) is False
    assert (await _row(maker)).report_attempts == 1


@pytest.mark.asyncio
async def test_a_queued_report_that_already_used_every_run_is_not_claimed(maker):
    await _seed(maker, report_status="queued", attempts=MAX_REPORT_RUNS)
    async with maker() as db:
        assert await claim_next_report(db, now=NOW) is None
    assert (await _row(maker)).report_attempts == MAX_REPORT_RUNS


@pytest.mark.asyncio
async def test_the_oldest_finished_session_is_claimed_first(maker):
    await _seed(maker, session_id="ms_new", report_status="queued", completed_at=NOW)
    await _seed(maker, session_id="ms_old", report_status="queued",
                completed_at=NOW - timedelta(hours=2))
    async with maker() as db:
        assert await claim_next_report(db, now=NOW) == "ms_old"


@pytest.mark.asyncio
async def test_a_generating_report_is_reclaimed_after_the_lease_and_not_before(maker):
    await _seed(maker, report_status="generating", attempts=1,
                claimed_at=NOW - CLAIM_LEASE + timedelta(seconds=1))
    async with maker() as db:
        assert await claim_next_report(db, now=NOW) is None
    async with maker() as db:
        assert await claim_next_report(db, now=NOW + timedelta(seconds=2)) == "ms1"
    assert (await _row(maker)).report_attempts == 2


@pytest.mark.asyncio
async def test_a_report_that_used_all_its_runs_is_failed_not_reclaimed(maker):
    await _seed(maker, report_status="generating", attempts=MAX_REPORT_RUNS,
                claimed_at=NOW - CLAIM_LEASE - timedelta(seconds=1))
    async with maker() as db:
        assert await claim_next_report(db, now=NOW) is None
    row = await _row(maker)
    assert row.report_status == "failed" and row.report_attempts == MAX_REPORT_RUNS
    assert row.report_error


@pytest.mark.asyncio
async def test_nothing_is_claimed_from_reports_that_are_not_waiting(maker):
    await _seed(maker, session_id="ms_ready", report_status="ready")
    await _seed(maker, session_id="ms_failed", report_status="failed", attempts=1)
    await _seed(maker, session_id="ms_active", status="active", completed_at=None)
    async with maker() as db:
        assert await claim_next_report(db, now=NOW) is None


# --- running a claimed report -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_successful_run_marks_the_report_ready(maker, monkeypatch):
    await _seed(maker, report_status="queued")
    agent = FakeReviewerAgent(maker, report=GOOD_REPORT)
    _use_reviewer(monkeypatch, maker, agent)
    async with maker() as db:
        assert await claim_next_report(db, now=NOW) == "ms1"
    assert await generate_report("ms1") is True
    row = await _row(maker)
    assert (row.report_status, row.report_error, row.report_claimed_at) == ("ready", None, None)
    assert row.report["overall"]["depth"] == 6.0
    assert len(agent.runs) == 1


@pytest.mark.asyncio
async def test_a_run_that_stores_nothing_marks_it_failed_with_a_short_reason(maker, monkeypatch):
    await _seed(maker, report_status="queued")
    _use_reviewer(monkeypatch, maker, FakeReviewerAgent(maker, report=None))
    async with maker() as db:
        await claim_next_report(db, now=NOW)
    assert await generate_report("ms1") is False
    row = await _row(maker)
    assert row.report_status == "failed" and row.report_error == "评审没有产出报告。"


@pytest.mark.asyncio
async def test_an_error_in_the_run_is_stored_as_a_short_reason_not_a_traceback(maker, monkeypatch):
    await _seed(maker, report_status="queued")
    boom = RuntimeError("gateway said: " + "x" * 500)
    _use_reviewer(monkeypatch, maker, FakeReviewerAgent(maker, error=boom))
    async with maker() as db:
        await claim_next_report(db, now=NOW)
    assert await generate_report("ms1") is False
    row = await _row(maker)
    assert row.report_status == "failed"
    assert row.report_error and len(row.report_error) <= 255
    assert "gateway" not in row.report_error and "Traceback" not in row.report_error


# --- retry ------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_requeue_failed_is_allowed_until_every_run_has_been_used(maker):
    await _seed(maker, session_id="ms_3", report_status="failed", attempts=MAX_REPORT_RUNS - 1)
    await _seed(maker, session_id="ms_4", report_status="failed", attempts=MAX_REPORT_RUNS)
    await _seed(maker, session_id="ms_ready", report_status="ready")
    await _seed(maker, session_id="ms_queued", report_status="queued")
    async with maker() as db:
        assert await requeue_failed(db, "ms_3") is True
        assert await requeue_failed(db, "ms_4") is False
        assert await requeue_failed(db, "ms_ready") is False
        assert await requeue_failed(db, "ms_queued") is False
    requeued = await _row(maker, "ms_3")
    assert (requeued.report_status, requeued.report_error) == ("queued", None)
    assert (await _row(maker, "ms_4")).report_status == "failed"


# --- the dispatcher ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_dispatcher_generates_a_queued_report_and_stops_when_cancelled(
    maker, monkeypatch
):
    await _seed(maker, report_status="queued")
    _use_reviewer(monkeypatch, maker, FakeReviewerAgent(maker, report=GOOD_REPORT))
    worker = asyncio.create_task(run_mock_report_dispatcher(poll_seconds=0.02))
    try:
        for _ in range(200):
            if (await _row(maker)).report_status == "ready":
                break
            await asyncio.sleep(0.02)
    finally:
        worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker
    assert (await _row(maker)).report_status == "ready"


# --- the migration ----------------------------------------------------------------------------


def _load_migration():
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "024_mock_report_queue.py"
    spec = importlib.util.spec_from_file_location("migration_024", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _legacy_table(conn) -> None:
    conn.exec_driver_sql(
        "CREATE TABLE jc_mock_session (id TEXT PRIMARY KEY, status TEXT NOT NULL, report TEXT)")
    for row in (
        ("with_report", "completed", '{"overall": {}}'),
        ("no_report", "completed", None),
        ("blank_report", "completed", ""),
        ("empty_report", "completed", "{}"),
        ("null_report", "completed", "null"),
        ("still_active", "active", None),
    ):
        conn.exec_driver_sql("INSERT INTO jc_mock_session VALUES (?, ?, ?)", row)


def _run_upgrade(conn) -> None:
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with Operations.context(MigrationContext.configure(conn)):
        _load_migration().upgrade()


def _backfilled(conn) -> dict:
    return {
        r[0]: r[1:] for r in conn.exec_driver_sql(
            "SELECT id, report_status, report_attempts, report_error FROM jc_mock_session")
    }


def test_the_migration_adds_the_columns_and_backfills_legacy_sessions():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        _legacy_table(conn)
        _run_upgrade(conn)
        rows = _backfilled(conn)
    assert rows["with_report"] == ("ready", 0, None)
    # No note is written: a migration that writes text fails on a table whose character set
    # cannot hold it, after the columns were already added. The page words a failed report that
    # has no reason.
    for legacy in ("no_report", "blank_report", "empty_report", "null_report"):
        assert rows[legacy] == ("failed", 0, None)
    assert rows["still_active"] == (None, 0, None)


def test_a_migration_that_stopped_halfway_can_be_run_again():
    # MySQL does not roll back column changes, so a failure after the columns were added leaves them
    # there with the version unchanged. The next run must carry on, not stop at "duplicate column".
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        _legacy_table(conn)
        conn.exec_driver_sql("ALTER TABLE jc_mock_session ADD COLUMN report_status VARCHAR(16)")
        conn.exec_driver_sql(
            "ALTER TABLE jc_mock_session ADD COLUMN report_attempts INTEGER NOT NULL DEFAULT 0")
        conn.exec_driver_sql("CREATE INDEX ix_jc_mock_session_report_status "
                             "ON jc_mock_session (report_status)")
        _run_upgrade(conn)
        rows = _backfilled(conn)
        columns = {c["name"] for c in sa.inspect(conn).get_columns("jc_mock_session")}
    assert {"report_claimed_at", "report_error"} <= columns
    assert rows["with_report"][0] == "ready" and rows["no_report"][0] == "failed"


def test_running_the_migration_twice_changes_nothing_the_second_time():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        _legacy_table(conn)
        _run_upgrade(conn)
        conn.exec_driver_sql(
            "UPDATE jc_mock_session SET report_status = 'queued', report_attempts = 2 "
            "WHERE id = 'no_report'")
        _run_upgrade(conn)
        assert _backfilled(conn)["no_report"] == ("queued", 2, None)


def test_no_migration_writes_text_a_non_unicode_table_could_not_hold():
    # Non-ASCII text may be in a docstring or a comment. Any other string in a migration is data or
    # schema that reaches the database, and the table's character set is not ours to assume.
    import ast

    versions = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    offenders = []
    for path in sorted(versions.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {
            id(node.body[0].value) for node in ast.walk(tree)
            if isinstance(node, ast.Module | ast.FunctionDef | ast.ClassDef)
            and node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        }
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in docstrings and not node.value.isascii()):
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == []


# --- shutdown in the middle of a run ----------------------------------------------------------


async def _until(condition, *, seconds: float = 5.0) -> None:
    for _ in range(int(seconds / 0.02)):
        if condition():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition not reached")


async def _claim_and_start(maker, monkeypatch) -> tuple[asyncio.Task, FakeReviewerAgent]:
    """A claimed report whose reviewer is slow, so the run is still going when we cancel it."""
    agent = FakeReviewerAgent(maker, report=GOOD_REPORT, delay=30)
    _use_reviewer(monkeypatch, maker, agent)
    async with maker() as db:
        assert await claim_next_report(db) == "ms1"
    task = asyncio.create_task(generate_report("ms1"))
    await _until(lambda: len(agent.runs) == 1)
    return task, agent


@pytest.mark.asyncio
async def test_a_run_cancelled_by_shutdown_gives_its_run_back(maker, monkeypatch):
    # A deploy cancels the worker. The model never failed, so the report must not lose a run to it,
    # and must not wait out the lease before another worker may take it.
    await _seed(maker, report_status="queued")
    task, _ = await _claim_and_start(maker, monkeypatch)
    assert (await _row(maker)).report_attempts == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    row = await _row(maker)
    assert (row.report_status, row.report_attempts, row.report_claimed_at) == ("queued", 0, None)
    async with maker() as db:
        assert await claim_next_report(db) == "ms1"


@pytest.mark.asyncio
async def test_the_dispatcher_cancelled_mid_run_gives_the_run_back(maker, monkeypatch):
    await _seed(maker, report_status="queued")
    agent = FakeReviewerAgent(maker, report=GOOD_REPORT, delay=30)
    _use_reviewer(monkeypatch, maker, agent)
    worker = asyncio.create_task(run_mock_report_dispatcher(poll_seconds=0.02))
    await _until(lambda: len(agent.runs) == 1)
    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker
    row = await _row(maker)
    assert (row.report_status, row.report_attempts, row.report_claimed_at) == ("queued", 0, None)


@pytest.mark.asyncio
async def test_a_cancelled_run_leaves_a_claim_someone_else_took_over(maker, monkeypatch):
    # The lease ran out, another worker reclaimed the report, and this slow run is then cancelled.
    # It must not undo the new claim.
    await _seed(maker, report_status="queued")
    task, _ = await _claim_and_start(maker, monkeypatch)
    takeover = NOW + timedelta(hours=1)
    async with maker() as db:
        session = await db.get(MockSession, "ms1")
        session.report_claimed_at, session.report_attempts = takeover, 2
        await db.commit()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    row = await _row(maker)
    assert (row.report_status, row.report_attempts, row.report_claimed_at) == (
        "generating", 2, takeover)


# --- a slow run must not overwrite a newer claim -----------------------------------------------


@pytest.mark.asyncio
async def test_a_run_that_finishes_after_another_worker_took_over_leaves_the_new_claim(
    maker, monkeypatch
):
    # The lease ran out, a second worker reclaimed the report, and the first (slow) run then ends in
    # failure. Its result must not overwrite what the second worker is doing.
    await _seed(maker, report_status="queued")
    agent = FakeReviewerAgent(maker, report=None, delay=0.4)
    _use_reviewer(monkeypatch, maker, agent)
    async with maker() as db:
        assert await claim_next_report(db) == "ms1"
    slow = asyncio.create_task(generate_report("ms1"))
    await _until(lambda: len(agent.runs) == 1)
    takeover = NOW + timedelta(hours=1)
    async with maker() as db:
        session = await db.get(MockSession, "ms1")
        session.report_claimed_at, session.report_attempts = takeover, 2
        await db.commit()
    assert await slow is False
    row = await _row(maker)
    assert (row.report_status, row.report_attempts, row.report_claimed_at) == (
        "generating", 2, takeover)
    assert row.report_error is None
