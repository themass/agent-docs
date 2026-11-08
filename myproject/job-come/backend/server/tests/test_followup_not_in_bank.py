"""A follow-up is about one answer in one interview, so it never enters the question bank.

Live (2026-11-08): the interviewer's follow-up "你又绕回 A/B 测试那句了……" was stored as a bank
question. Later interviews drew that row as a main question, so the next candidate heard a reply to
something they never said. A follow-up is now kept for its own interview only."""

from __future__ import annotations

import pytest
from sqlalchemy import select

import test_mock_ask_stem as _stem
from jc.models.enums import QuestionSource
from jc.models.interview import InterviewQuestion
from jc.stores.interview_store import InterviewStore
from test_mock_ask_stem import _ask, _open_session

maker = _stem.maker  # the same database fixture

Q1 = {"question_id": "q1", "kind": "main", "parent_question_id": None}
FOLLOW = "你又绕回 A/B 测试那句了，我没问这个。我问的是预算。"
MAIN_SAME_TEXT = "你又绕回 A/B 测试那句了，我没问这个。我问的是预算。"


async def _row(maker, stem: str) -> InterviewQuestion | None:
    async with maker() as db:
        return (await db.execute(
            select(InterviewQuestion).where(InterviewQuestion.stem == stem)
        )).scalars().first()


@pytest.mark.asyncio
async def test_a_follow_up_is_stored_as_a_follow_up_not_a_bank_question(maker):
    await _open_session(maker, asked=[Q1])
    result = await _ask(maker, kind="followup", parent_question_id="q1", stem=FOLLOW)
    assert result.get("accepted") is True, result
    row = await _row(maker, FOLLOW)
    assert row is not None and row.source == QuestionSource.FOLLOWUP


@pytest.mark.asyncio
async def test_a_follow_up_is_not_found_by_the_bank_search(maker):
    await _open_session(maker, asked=[Q1])
    await _ask(maker, kind="followup", parent_question_id="q1", stem=FOLLOW)
    async with maker() as db:
        found = await InterviewStore(db).search_questions("p1", query="绕回", limit=20)
    assert found == []


@pytest.mark.asyncio
async def test_the_same_text_asked_in_another_interview_is_a_new_row(maker):
    from datetime import UTC, datetime

    from jc.authz.scope import RunScope
    from jc.models.interview import MockSession
    from jc.services.mock_guard_service import ask

    await _open_session(maker, asked=[Q1])
    await _ask(maker, kind="followup", parent_question_id="q1", stem=FOLLOW)
    async with maker() as db:
        db.add(MockSession(
            id="ms2", profile_id="p1", user_id="u1", mode="target", question_ids=[],
            bank_draw_count=0, generated_count=0, status="active", started_at=datetime.now(UTC),
            style="standard", quota_counted=False, coverage={"asked": []},
        ))
        await db.commit()
    async with maker() as db:
        scope = RunScope(db=db, user_id="u1", profile_id="p1", mock_session_id="ms2")
        result = await ask(scope, mock_session_id="ms2", stem=MAIN_SAME_TEXT, kind="main")
    assert result.get("accepted") is True, result
    async with maker() as db:
        rows = (await db.execute(
            select(InterviewQuestion).where(InterviewQuestion.stem == FOLLOW)
        )).scalars().all()
    assert len(rows) == 2, "the main question must not reuse the follow-up row"
    assert {r.source for r in rows} == {QuestionSource.FOLLOWUP, QuestionSource.MOCK}


@pytest.mark.asyncio
async def test_a_new_main_question_still_goes_into_the_bank(maker):
    await _open_session(maker)
    stem = "讲一次你处理线上故障的经历"
    result = await _ask(maker, kind="main", stem=stem)
    assert result.get("accepted") is True, result
    row = await _row(maker, stem)
    assert row is not None and row.source == QuestionSource.MOCK
