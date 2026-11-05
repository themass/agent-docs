"""The queue of mock-interview reports. The session row is the queue (SPEC-MOCK-INTERVIEW-V2 §5.3).

Ending a session marks its report `queued`. A worker claims one with a conditional update, so of
two workers racing for it exactly one wins. A worker that dies leaves the row `generating`; once
its lease is out another worker takes the report over. Runs are capped, so a report that keeps
failing ends up `failed` with a reason the user can read, and the user may retry it until the cap
is used.

The tool that ends a session runs in the agent's own process, which cannot start work in the API
process. A table the API process polls (the same idea as the profile-parse dispatcher) does not
need to.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jc.db.session import AsyncSessionLocal
from jc.models.enums import MAX_REPORT_RUNS, MockReportStatus, MockSessionStatus
from jc.models.interview import MockSession

logger = logging.getLogger(__name__)

__all__ = [
    "CLAIM_LEASE",
    "MAX_REPORT_RUNS",
    "claim_next_report",
    "generate_report",
    "requeue_failed",
    "run_mock_report_dispatcher",
]

#: Longer than the reviewer's own time budget (300 s), so a run still going is never taken over.
CLAIM_LEASE = timedelta(seconds=600)
#: How many reports one API process generates at once; each is a model run.
MAX_CONCURRENT_REPORTS = 2

_NO_REPORT = "评审没有产出报告。"
_RUN_FAILED = "生成报告时出错了。"
_RUNS_USED = "多次生成都没有成功。"


def _waiting(cutoff: datetime):
    """Reports a worker may take: queued, or generating by a worker whose lease has run out."""
    return (
        (MockSession.status == MockSessionStatus.COMPLETED)
        & (MockSession.report_attempts < MAX_REPORT_RUNS)
        & (
            (MockSession.report_status == MockReportStatus.QUEUED)
            | (
                (MockSession.report_status == MockReportStatus.GENERATING)
                & (MockSession.report_claimed_at < cutoff)
            )
        )
    )


async def claim_next_report(db: AsyncSession, *, now: datetime | None = None) -> str | None:
    """Take the oldest finished session whose report is waiting. Returns its id, or None.

    The claim is one conditional UPDATE, and a row count of 1 is the win, so two workers asking at
    once cannot both get the same report.
    """
    now = now or datetime.now(UTC)
    cutoff = now - CLAIM_LEASE

    # A worker that died on its last allowed run leaves a row nobody may claim again: settle it.
    # Found first and updated by primary key, so a poll that finds nothing writes nothing and a
    # poll that finds something locks only those rows, not a range of the status index that a
    # claim on another instance is also reaching into.
    stuck = (
        await db.execute(
            select(MockSession.id).where(
                MockSession.report_status == MockReportStatus.GENERATING,
                MockSession.report_attempts >= MAX_REPORT_RUNS,
                MockSession.report_claimed_at < cutoff,
            )
        )
    ).scalars().all()
    for stuck_id in stuck:
        await db.execute(
            update(MockSession)
            .where(
                MockSession.id == stuck_id,
                MockSession.report_status == MockReportStatus.GENERATING,
                MockSession.report_attempts >= MAX_REPORT_RUNS,
            )
            .values(report_status=MockReportStatus.FAILED, report_error=_RUNS_USED)
        )

    candidates = (
        await db.execute(
            select(MockSession.id)
            .where(_waiting(cutoff))
            .order_by(MockSession.completed_at.asc(), MockSession.id.asc())
            .limit(5)
        )
    ).scalars().all()

    for session_id in candidates:
        if await _claim_one(db, session_id, now=now, cutoff=cutoff):
            await db.commit()
            return session_id
    await db.commit()
    return None


async def _claim_one(db: AsyncSession, session_id: str, *, now: datetime, cutoff: datetime) -> bool:
    """Claim one specific report if it is still waiting. The candidate list was read a moment
    ago and another worker may have taken the report since; the condition decides, not the list."""
    claimed = await db.execute(
        update(MockSession)
        .where(MockSession.id == session_id, _waiting(cutoff))
        .values(
            report_status=MockReportStatus.GENERATING,
            report_attempts=MockSession.report_attempts + 1,
            report_claimed_at=now,
            report_error=None,
        )
    )
    return claimed.rowcount == 1


async def generate_report(session_id: str) -> bool:
    """Run the reviewer for a claimed report and record how it went. True when a report was stored.

    Whatever goes wrong, the user gets a short reason; the cause goes to the log.
    """
    from jc.services.interview_reviewer import review_session

    async with AsyncSessionLocal() as db:
        session = await db.get(MockSession, session_id)
        if session is None:
            return False
        user_id, profile_id = session.user_id, session.profile_id
        my_claim = session.report_claimed_at
        error: str | None = None
        stored = False
        try:
            stored = await review_session(
                db, user_id=user_id, profile_id=profile_id, mock_session_id=session_id
            )
            if not stored:
                error = _NO_REPORT
        except asyncio.CancelledError:
            # Shutdown (a deploy, a restart) cancels the worker. The model did not fail, so the
            # report keeps its run and goes straight back to the queue instead of waiting out the
            # lease. Shielded: the cancellation must not interrupt the write that undoes it.
            await asyncio.shield(_give_the_run_back(session_id, my_claim))
            raise
        except Exception:  # noqa: BLE001 — every failure is a failed report, never a crashed worker
            logger.warning("mock_report_failed session=%s", session_id, exc_info=True)
            error = _RUN_FAILED
            await db.rollback()
        # Only the claim this run made is closed. A run that outlived its lease finds the report in
        # another worker's hands, and what it learned must not overwrite what that worker is doing.
        # The report it stored, if any, is already on the row and is shown either way.
        await db.execute(
            update(MockSession)
            .where(
                MockSession.id == session_id,
                MockSession.report_status == MockReportStatus.GENERATING,
                MockSession.report_claimed_at == my_claim,
            )
            .values(
                report_status=MockReportStatus.READY if stored else MockReportStatus.FAILED,
                report_error=None if stored else error,
                report_claimed_at=None,
            )
        )
        await db.commit()
        return stored


async def _give_the_run_back(session_id: str, claimed_at: datetime | None) -> None:
    """Undo a claim whose run was cut short: back to queued, the run not counted.

    Only the claim that was made is undone. If the lease ran out and another worker took the
    report over, its claim time differs and nothing is touched."""
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(MockSession)
                .where(
                    MockSession.id == session_id,
                    MockSession.report_status == MockReportStatus.GENERATING,
                    MockSession.report_claimed_at == claimed_at,
                )
                .values(
                    report_status=MockReportStatus.QUEUED,
                    report_attempts=MockSession.report_attempts - 1,
                    report_claimed_at=None,
                )
            )
            await db.commit()
    except Exception:  # noqa: BLE001 — shutting down; the lease is the fallback
        logger.warning("could not give back the report run session=%s", session_id, exc_info=True)


async def requeue_failed(db: AsyncSession, session_id: str) -> bool:
    """Put a failed report back in the queue. False unless it is failed and has runs left."""
    result = await db.execute(
        update(MockSession)
        .where(
            MockSession.id == session_id,
            MockSession.report_status == MockReportStatus.FAILED,
            MockSession.report_attempts < MAX_REPORT_RUNS,
        )
        .values(report_status=MockReportStatus.QUEUED, report_error=None)
    )
    await db.commit()
    return result.rowcount == 1


async def run_mock_report_dispatcher(*, poll_seconds: float = 5) -> None:
    """Claim waiting reports and generate them, a few at a time, until cancelled."""
    running: set[asyncio.Task[bool]] = set()

    def _done(task: asyncio.Task[bool]) -> None:
        running.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.error("mock report task crashed", exc_info=task.exception())

    try:
        while True:
            try:
                while len(running) < MAX_CONCURRENT_REPORTS:
                    async with AsyncSessionLocal() as db:
                        session_id = await claim_next_report(db)
                    if session_id is None:
                        break
                    task = asyncio.create_task(generate_report(session_id))
                    running.add(task)
                    task.add_done_callback(_done)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Mock report dispatcher poll failed")
            await asyncio.sleep(poll_seconds)
    finally:
        for task in running:
            task.cancel()
        if running:
            await asyncio.gather(*running, return_exceptions=True)
