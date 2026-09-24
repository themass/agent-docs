"""Background jobs that must not block upload/confirm HTTP."""

from __future__ import annotations

import logging

from jobcome.db.session import AsyncSessionLocal
from jobcome.services.resume_service import ResumeService

logger = logging.getLogger(__name__)


async def prepare_resume_tracks(profile_id: str, elevation_level: str = "conservative") -> None:
    async with AsyncSessionLocal() as db:
        try:
            await ResumeService(db).prepare_tracks(profile_id, elevation_level=elevation_level)
        except Exception:
            logger.exception("prepare_resume_tracks failed profile_id=%s", profile_id)
