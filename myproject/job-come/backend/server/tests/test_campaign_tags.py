"""Campaign board: tagging a job as warm-up or target keeps the campaign lists and the job agree."""

from __future__ import annotations

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401 — registers every table on Base.metadata
from jc.db.base import Base
from jc.models.enums import JobTag
from jc.models.job import Campaign, Job
from jc.models.profile import Profile
from jc.models.user import User
from jc.services.campaign_service import CampaignService


@pytest.fixture
async def sessions(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/campaign.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _seed(sessions):
    async with sessions() as db:
        db.add(User(id="alice", email="alice@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(
            Profile(
                id="p1",
                user_id="alice",
                owner_kind="user",
                payload={"contact": {"name": "A"}},
                version=1,
            )
        )
        await db.flush()
        db.add(
            Job(
                id="j1",
                profile_id="p1",
                company="Acme",
                title="Backend",
                raw_text="jd",
                requirements={},
            )
        )
        await db.commit()


ACTOR = UserActor(user_id="alice", session_id="s")


@pytest.mark.asyncio
async def test_tagging_target_moves_the_job_out_of_warmup(sessions):
    await _seed(sessions)
    async with sessions() as db:
        await CampaignService(db).tag_job("p1", "j1", actor=ACTOR, tag="warmup")
    async with sessions() as db:
        await CampaignService(db).tag_job("p1", "j1", actor=ACTOR, tag="target")
    # A job is in exactly one list: moving it to target must remove it from warm-up.
    async with sessions() as db:
        campaign = (await db.execute(select(Campaign))).scalar_one()
    assert "j1" in campaign.target_job_ids
    assert "j1" not in campaign.warmup_job_ids, "a job must not sit in both lists"


@pytest.mark.asyncio
async def test_the_job_tag_follows_the_campaign_tag(sessions):
    await _seed(sessions)
    async with sessions() as db:
        await CampaignService(db).tag_job("p1", "j1", actor=ACTOR, tag="target")
    async with sessions() as db:
        job = await db.get(Job, "j1")
    assert job.tag == JobTag.TARGET, "the job row and the campaign list must not disagree"
