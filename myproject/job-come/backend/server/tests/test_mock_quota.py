"""Monthly full mock-interview quota: one free run per Shanghai calendar month, race-safe, and
given back when a session never starts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.db.base import Base
from jc.exceptions import ForbiddenError
from jc.models.mock_quota import MockFullRunQuota
from jc.models.user import User
from jc.services.mock_quota_service import MockQuotaService, month_key


@pytest.fixture
async def sessions(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/quota.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        db.add(User(id="free", email="free@example.test", password_hash="x", role="user"))
        db.add(
            User(
                id="member",
                email="m@example.test",
                password_hash="x",
                role="user",
                vip_expires_at=datetime(2099, 1, 1),
            )
        )
        await db.commit()
    yield maker
    await engine.dispose()


# A fixed instant in Shanghai November, away from any month edge.
NOV = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)


def test_month_is_the_shanghai_calendar_month_not_utc():
    # 00:30 on 1 Dec in Shanghai is still 30 Nov in UTC: it belongs to December.
    assert month_key(datetime(2026, 11, 30, 16, 30, tzinfo=UTC)) == "2026-12"
    assert month_key(datetime(2026, 11, 30, 15, 59, tzinfo=UTC)) == "2026-11"


@pytest.mark.asyncio
async def test_a_free_account_gets_one_full_run_per_month(sessions):
    async with sessions() as db:
        await MockQuotaService(db).claim_full_run("free", "mock_a", now=NOV)
        await db.commit()
    async with sessions() as db:
        with pytest.raises(ForbiddenError) as exc:
            await MockQuotaService(db).claim_full_run("free", "mock_b", now=NOV)
    assert exc.value.code == "mock_full_run_quota_exhausted"


@pytest.mark.asyncio
async def test_the_quota_resets_in_the_next_month(sessions):
    async with sessions() as db:
        await MockQuotaService(db).claim_full_run("free", "mock_a", now=NOV)
        await db.commit()
    dec = datetime(2026, 12, 2, 12, 0, tzinfo=UTC)
    async with sessions() as db:
        await MockQuotaService(db).claim_full_run("free", "mock_c", now=dec)
        await db.commit()
    async with sessions() as db:
        rows = (
            (
                await db.execute(
                    select(MockFullRunQuota.month)
                    .where(MockFullRunQuota.user_id == "free")
                    .order_by(MockFullRunQuota.month)
                )
            )
            .scalars()
            .all()
        )
    assert rows == ["2026-11", "2026-12"]


@pytest.mark.asyncio
async def test_members_are_never_counted(sessions):
    async with sessions() as db:
        for i in range(3):
            await MockQuotaService(db).claim_full_run("member", f"mock_m{i}", now=NOV)
        await db.commit()
    async with sessions() as db:
        rows = (
            (await db.execute(select(MockFullRunQuota).where(MockFullRunQuota.user_id == "member")))
            .scalars()
            .all()
        )
    assert rows == []


@pytest.mark.asyncio
async def test_two_concurrent_claims_for_one_month_only_one_wins(sessions):
    import asyncio

    async def attempt(name: str) -> str:
        async with sessions() as db:
            try:
                await MockQuotaService(db).claim_full_run("free", name, now=NOV)
                await db.commit()
                return "won"
            except ForbiddenError:
                await db.rollback()
                return "refused"

    outcomes = await asyncio.gather(attempt("mock_x"), attempt("mock_y"))
    assert sorted(outcomes) == ["refused", "won"], "exactly one run may hold the month"


@pytest.mark.asyncio
async def test_releasing_a_session_gives_the_slot_back(sessions):
    async with sessions() as db:
        await MockQuotaService(db).claim_full_run("free", "mock_a", now=NOV)
        await db.commit()
    async with sessions() as db:
        await MockQuotaService(db).release_full_run("mock_a")
        await db.commit()
    async with sessions() as db:
        await MockQuotaService(db).claim_full_run("free", "mock_b", now=NOV)
        await db.commit()
