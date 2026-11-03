"""Apply pipeline: the interview prep pack for a job, and the ownership check on it. The pipeline
run itself calls the model and is covered by the agent tests, not here."""

from __future__ import annotations

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.db.base import Base
from jc.exceptions import AppError
from jc.models.job import Job
from jc.models.profile import Profile
from jc.models.user import User
from jc.services.apply_pipeline_service import ApplyPipelineService

ALICE = UserActor(user_id="alice", session_id="s")
BOB = UserActor(user_id="bob", session_id="s")


@pytest.fixture
async def sessions(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/prep.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        for uid in ("alice", "bob"):
            db.add(User(id=uid, email=f"{uid}@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(
            Profile(
                id="p_alice",
                user_id="alice",
                owner_kind="user",
                payload={"contact": {"name": "A"}, "summary": "Built payment services."},
                version=1,
            )
        )
        db.add(
            Profile(
                id="p_bob",
                user_id="bob",
                owner_kind="user",
                payload={"contact": {"name": "B"}},
                version=1,
            )
        )
        await db.flush()
        db.add(
            Job(
                id="j_alice",
                profile_id="p_alice",
                company="Acme",
                title="Backend",
                raw_text="jd",
                requirements={"must": ["Python"]},
                fit_score=82,
                fit_recommendation="go",
            )
        )
        await db.commit()
    yield maker
    await engine.dispose()


@pytest.mark.asyncio
async def test_prep_pack_contains_the_job_and_the_profile_summary(sessions):
    async with sessions() as db:
        pack = await ApplyPipelineService(db).prep_context("p_alice", "j_alice", actor=ALICE)
    assert pack["job"]["company"] == "Acme"
    assert pack["job"]["fit_score"] == 82
    assert pack["profile_summary"].startswith("Built payment services")


@pytest.mark.asyncio
async def test_prep_pack_refuses_another_users_job_and_profile(sessions):
    async with sessions() as db:
        with pytest.raises(AppError):
            await ApplyPipelineService(db).prep_context("p_alice", "j_alice", actor=BOB)
    async with sessions() as db:
        with pytest.raises(AppError):
            await ApplyPipelineService(db).prep_context("p_bob", "j_alice", actor=BOB)
