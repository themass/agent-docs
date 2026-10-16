"""Background jobs that must not block upload/confirm HTTP."""

from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import select

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


async def parse_profile_source(profile_id: str, source_id: str) -> None:
    """Background resume parse — keeps POST /profiles/upload fast for reverse proxies."""
    from jc.services.profile_service import ProfileService

    started = time.monotonic()
    logger.info(
        "profile_parse profile_id=%s source_id=%s phase=worker_started",
        profile_id,
        source_id,
    )
    ok = False
    async with AsyncSessionLocal() as db:
        try:
            ok = await ProfileService(db).parse_stored_source(profile_id, source_id)
        except Exception:
            logger.exception(
                "parse_profile_source failed profile_id=%s source_id=%s",
                profile_id,
                source_id,
            )
            await db.rollback()
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


async def recover_stale_profile_parses() -> None:
    """Re-queue sources left in processing after API reload or crashed workers."""
    async with AsyncSessionLocal() as db:
        stmt = select(ProfileSource).where(ProfileSource.parse_status == ParseStatus.PROCESSING)
        rows = list((await db.execute(stmt)).scalars().all())
    if not rows:
        return
    logger.warning(
        "Recovering %s profile source(s) stuck in processing (likely prior reload)",
        len(rows),
    )
    for source in rows:
        asyncio.create_task(parse_profile_source(source.profile_id, source.id))
