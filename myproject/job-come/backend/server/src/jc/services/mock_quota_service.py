"""Monthly full mock-interview quota for free accounts.

The check and the claim are one insert against a (user, month) primary key, so two concurrent
creates in the same month cannot both succeed. A session that never completes gives its slot
back (`release`), so a failed start does not cost the user their month.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from jc.exceptions import ForbiddenError
from jc.models.interview import MockSession
from jc.models.mock_quota import MockFullRunQuota
from jc.services.membership_service import TIER_FREE, MembershipService

SHANGHAI = ZoneInfo("Asia/Shanghai")

FREE_FULL_RUNS_PER_MONTH = 1


def month_key(now: datetime | None = None) -> str:
    """The calendar month in Asia/Shanghai, e.g. '2026-11'. Quota resets on the local month."""
    moment = (now or datetime.now(UTC)).astimezone(SHANGHAI)
    return f"{moment.year:04d}-{moment.month:02d}"


class MockQuotaService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def claim_full_run(
        self, user_id: str, session_id: str, *, now: datetime | None = None
    ) -> None:
        """Take this month's full-run slot for a free account. Members pass straight through.

        Raises ForbiddenError when the free slot for this month is already held.
        """
        tier = (await MembershipService(self._db).snapshot(user_id)).tier
        if tier != TIER_FREE:
            return
        month = month_key(now)
        try:
            async with self._db.begin_nested():
                self._db.add(MockFullRunQuota(user_id=user_id, month=month, session_id=session_id))
                await self._db.flush()
        except IntegrityError as exc:
            raise ForbiddenError(
                "本月的完整模拟面试次数已用完（免费账号每月 1 场）。热身模拟不限次数；"
                "开通会员后完整模拟不限次数。",
                code="mock_full_run_quota_exhausted",
            ) from exc

    async def release_full_run(self, session_id: str) -> None:
        """Give the slot back when its session never got going. A no-op if it held none."""
        await self._db.execute(
            delete(MockFullRunQuota).where(MockFullRunQuota.session_id == session_id)
        )
        await self._db.execute(
            update(MockSession)
            .where(MockSession.id == session_id)
            .values(quota_counted=False)
            .execution_options(synchronize_session=False)
        )
