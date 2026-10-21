"""Database leases arbitrate parse work across independent API processes."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.db.base import Base
from jc.models import *  # noqa: F403
from jc.models.enums import ParseStatus
from jc.models.profile import Profile, ProfileSource


@pytest.mark.asyncio
async def test_only_one_instance_can_claim_a_source_until_its_lease_expires(monkeypatch):
    from jc import tasks

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(tasks, "AsyncSessionLocal", factory)

    async with factory() as db:
        db.add(Profile(
            id="prof_claim", owner_kind="guest", version=1,
            payload={}, guest_session_id=None,
        ))
        db.add(ProfileSource(
            id="psrc_claim", profile_id="prof_claim", file_name="resume.pdf",
            storage_key="profiles/source.pdf", parse_status=ParseStatus.PROCESSING,
        ))
        await db.commit()

    first = await tasks.claim_profile_parse("prof_claim", "psrc_claim")
    second_instance_attempt = await tasks.claim_profile_parse("prof_claim", "psrc_claim")
    assert first is not None
    assert second_instance_attempt is None

    # Simulate a crashed worker. A later poll may reclaim only after expiry.
    async with factory() as db:
        await db.execute(
            update(ProfileSource)
            .where(ProfileSource.id == "psrc_claim")
            .values(parse_lease_until=datetime.now(UTC) - timedelta(seconds=1))
        )
        await db.commit()

    reclaimed = await tasks.claim_profile_parse("prof_claim", "psrc_claim")
    assert reclaimed is not None
    assert reclaimed != first

    async with factory() as db:
        source = await db.get(ProfileSource, "psrc_claim")
        assert source.parse_claim_token == reclaimed
        assert source.parse_owner == tasks._PARSE_WORKER_ID
        assert source.parse_status == ParseStatus.PROCESSING
        assert source.parse_lease_until > datetime.now(UTC)

    await engine.dispose()


@pytest.mark.asyncio
async def test_dispatcher_respects_per_instance_parse_concurrency(monkeypatch):
    from jc import tasks

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(tasks, "AsyncSessionLocal", factory)
    monkeypatch.setattr(tasks.settings, "jc_profile_parse_concurrency", 1)
    tasks._PARSE_TASKS.clear()
    started = asyncio.Event()
    release = asyncio.Event()

    async def hold_parse(profile_id: str, source_id: str) -> None:
        started.set()
        await release.wait()

    monkeypatch.setattr(tasks, "parse_profile_source", hold_parse)
    async with factory() as db:
        db.add(Profile(
            id="prof_dispatch", owner_kind="guest", version=1,
            payload={}, guest_session_id=None,
        ))
        for index in range(3):
            db.add(ProfileSource(
                id=f"psrc_dispatch_{index}", profile_id="prof_dispatch",
                file_name=f"resume-{index}.pdf", storage_key=f"profiles/{index}.pdf",
                parse_status=ParseStatus.PENDING,
            ))
        await db.commit()

    try:
        await tasks.recover_stale_profile_parses()
        await started.wait()
        assert len(tasks._PARSE_TASKS) == 1
        await tasks.recover_stale_profile_parses()
        assert len(tasks._PARSE_TASKS) == 1
    finally:
        release.set()
        await asyncio.gather(*list(tasks._PARSE_TASKS), return_exceptions=True)
        tasks._PARSE_TASKS.clear()
        await engine.dispose()
