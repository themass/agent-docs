"""Background jobs that must not block upload/confirm HTTP."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update

from jc.config import settings
from jc.db.session import AsyncSessionLocal
from jc.models.enums import ParseStatus
from jc.models.profile import ProfileSource
from jc.services.resume_service import ResumeService

logger = logging.getLogger(__name__)


async def prepare_resume_tracks(profile_id: str, elevation_level: str = "conservative") -> None:
    async with AsyncSessionLocal() as db:
        try:
            await ResumeService(db).prepare_tracks(profile_id, elevation_level=elevation_level)
        except Exception:
            logger.exception("prepare_resume_tracks failed profile_id=%s", profile_id)


_PARSE_WORKER_ID = f"api-{uuid.uuid4().hex[:16]}"
# Distinguishes "the parse path itself crashed" from a real user parse failure
# (`USER_UPLOAD_PARSE_FAILED`), so support can tell an infra bug from a bad upload.
INFRA_PARSE_FAILED = "解析服务异常，请稍后重试或重新上传。"
_PARSE_TASKS: set[asyncio.Task[None]] = set()


async def claim_profile_parse(profile_id: str, source_id: str) -> str | None:
    """Atomically claim one queued/expired source across all API instances."""
    now = datetime.now(UTC)
    token = uuid.uuid4().hex
    lease_until = now + timedelta(seconds=settings.jc_profile_parse_lease_seconds)
    async with AsyncSessionLocal() as db:
        claimable_statuses = [ParseStatus.PENDING, ParseStatus.PROCESSING]
        lease_is_available = or_(
            ProfileSource.parse_claim_token.is_(None),
            ProfileSource.parse_lease_until.is_(None),
            ProfileSource.parse_lease_until <= now,
        )
        stmt = (
            update(ProfileSource)
            .where(
                ProfileSource.id == source_id,
                ProfileSource.profile_id == profile_id,
                ProfileSource.parse_status.in_(claimable_statuses),
                lease_is_available,
            )
            .values(
                parse_status=ParseStatus.PROCESSING,
                parse_owner=_PARSE_WORKER_ID,
                parse_claim_token=token,
                parse_lease_until=lease_until,
            )
            .execution_options(synchronize_session=False)
        )
        result = await db.execute(stmt)
        await db.commit()
        return token if result.rowcount == 1 else None


async def parse_profile_source(profile_id: str, source_id: str) -> None:
    """Claim and parse a stored resume without holding an API request session."""
    claim_token = await claim_profile_parse(profile_id, source_id)
    if claim_token is None:
        logger.info(
            "profile_parse profile_id=%s source_id=%s phase=claim_skipped "
            "reason=already_claimed_or_settled",
            profile_id,
            source_id,
        )
        return

    from jc.services.profile_service import ProfileService

    started = time.monotonic()
    logger.info(
        "profile_parse profile_id=%s source_id=%s phase=worker_claimed worker=%s",
        profile_id,
        source_id,
        _PARSE_WORKER_ID,
    )
    ok = False
    async with AsyncSessionLocal() as db:
        try:
            ok = await ProfileService(db).parse_stored_source(
                profile_id, source_id, claim_token=claim_token
            )
        except Exception:
            logger.exception(
                "parse_profile_source failed profile_id=%s source_id=%s",
                profile_id,
                source_id,
            )
            await db.rollback()
            # A deterministic crash (not a process death) must not become a poison
            # row. Without this the source stays PROCESSING, its lease expires, and
            # the dispatcher re-claims it forever — production 2026-11-18 re-raised
            # the same MissingGreenlet every 30s for one bad row. Move it to FAILED
            # under the claim token so it settles; a *process* death never reaches
            # this branch, so its lease still expires and the row is recovered.
            await db.execute(
                update(ProfileSource)
                .where(
                    ProfileSource.id == source_id,
                    ProfileSource.parse_claim_token == claim_token,
                )
                .values(
                    parse_status=ParseStatus.FAILED,
                    parse_phase="failed",
                    parse_error=INFRA_PARSE_FAILED,
                    parse_owner=None,
                    parse_claim_token=None,
                    parse_lease_until=None,
                )
                .execution_options(synchronize_session=False)
            )
            await db.commit()
            return
    logger.info(
        "parse_profile_source finished profile_id=%s source_id=%s ok=%s elapsed_sec=%.1f",
        profile_id,
        source_id,
        ok,
        time.monotonic() - started,
    )
    if ok:
        await prepare_resume_tracks(profile_id, "conservative")


def _track_parse_task(task: asyncio.Task[None]) -> None:
    _PARSE_TASKS.discard(task)
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Profile parse dispatch task crashed")


async def recover_stale_profile_parses() -> None:
    """Dispatch durable queued or expired parses; DB claims arbitrate instances."""
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        stmt = (
            select(ProfileSource.profile_id, ProfileSource.id)
            .where(
                ProfileSource.parse_status.in_([ParseStatus.PENDING, ParseStatus.PROCESSING]),
                or_(
                    ProfileSource.parse_claim_token.is_(None),
                    ProfileSource.parse_lease_until.is_(None),
                    ProfileSource.parse_lease_until <= now,
                ),
            )
            .order_by(ProfileSource.created_at.asc())
            .limit(max(0, settings.jc_profile_parse_concurrency - len(_PARSE_TASKS)))
        )
        rows = list((await db.execute(stmt)).all())
    if not rows:
        return
    logger.info(
        "profile_parse dispatcher candidates=%s active=%s limit=%s",
        len(rows),
        len(_PARSE_TASKS),
        settings.jc_profile_parse_concurrency,
    )
    for profile_id, source_id in rows:
        task = asyncio.create_task(parse_profile_source(profile_id, source_id))
        _PARSE_TASKS.add(task)
        task.add_done_callback(_track_parse_task)


async def run_profile_parse_dispatcher(*, poll_seconds: float = 10) -> None:
    """Poll the DB-backed source queue so process loss does not lose accepted work."""
    while True:
        try:
            await recover_stale_profile_parses()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Profile parse dispatcher poll failed")
        await asyncio.sleep(poll_seconds)
