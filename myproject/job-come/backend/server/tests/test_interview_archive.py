"""Interview archive and question bank: saving an interview, logging a question, finding it again,
and the campaign board counting the real interview."""

from __future__ import annotations

from datetime import date

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401 — registers every table on Base.metadata
from jc.db.base import Base
from jc.models.profile import Profile
from jc.models.user import User
from jc.schemas.coach import InterviewSaveRequest, QuestionUpsertRequest
from jc.services.campaign_service import CampaignService
from jc.services.interview_service import InterviewService

ACTOR = UserActor(user_id="alice", session_id="s")


@pytest.fixture
async def sessions(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/archive.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
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
        await db.commit()
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.mark.asyncio
async def test_a_saved_interview_is_listed_and_counted_on_the_campaign_board(sessions):
    async with sessions() as db:
        saved = await InterviewService(db).save_interview(
            "p1",
            actor=ACTOR,
            body=InterviewSaveRequest(
                company="Acme",
                role_title="Backend",
                interview_date=date(2026, 10, 20),
                round="first",
                type="target",
                result="fail",
                failure_tags=["depth"],
                notes="could not explain the cache",
            ),
        )
    async with sessions() as db:
        listed = await InterviewService(db).list_interviews("p1", actor=ACTOR)
        stats = await CampaignService(db).get_stats("p1", actor=ACTOR)
    assert [i.id for i in listed.interviews] == [saved.id]
    assert listed.interviews[0].failure_tags == ["depth"]
    assert stats.progress["real_interviews"] == 1, "the campaign board must count real interviews"


@pytest.mark.asyncio
async def test_a_logged_question_can_be_found_again_in_the_bank(sessions):
    async with sessions() as db:
        await InterviewService(db).log_question(
            "p1",
            actor=ACTOR,
            body=QuestionUpsertRequest(
                source="real",
                stem="请讲一次你排查线上故障的过程",
                question_type="behavioral",
                company="Acme",
            ),
        )
    async with sessions() as db:
        found = await InterviewService(db).search_bank("p1", actor=ACTOR, query="故障")
        other = await InterviewService(db).search_bank("p1", actor=ACTOR, query="完全不相关的词")
    assert [q.stem for q in found.questions] == ["请讲一次你排查线上故障的过程"]
    assert other.questions == []
