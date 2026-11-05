"""`jc_mock_ask` takes the question itself.

The interviewer used to call `jc_question_upsert` for a question id and then `jc_mock_ask` to
register it: two calls, and a refusal in the second left the first one's question behind. The
question is now created and registered in one call, and a refusal leaves nothing."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.authz.scope import RunScope
from jc.db.base import Base
from jc.mcp.handlers import dispatch_tool
from jc.models.interview import InterviewQuestion, MockSession
from jc.models.profile import Profile
from jc.models.user import User

NEW_STEM = "讲一次你处理线上故障的经历"
BANK_STEM = "讲一个你拆分数据的经历"
FULL_OF_MAINS = [{"question_id": f"q{i}", "kind": "main", "parent_question_id": None}
                 for i in range(1, 6)]


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/askstem.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    makers = async_sessionmaker(engine, expire_on_commit=False)
    async with makers() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(Profile(id="p1", user_id="u1", owner_kind="user",
                       payload={"experience": "结算接口拆表"}, version=1))
        db.add(InterviewQuestion(id="bank1", profile_id="p1", stem=BANK_STEM,
                                 question_type="behavioral"))
        for i in range(1, 6):
            db.add(InterviewQuestion(id=f"q{i}", profile_id="p1", stem=f"第 {i} 个问题",
                                     question_type="behavioral"))
        await db.commit()
    yield makers
    await engine.dispose()


async def _open_session(maker, asked: list[dict] | None = None) -> None:
    asked = asked or []
    async with maker() as db:
        db.add(MockSession(
            id="ms1", profile_id="p1", user_id="u1", mode="target",
            question_ids=[a["question_id"] for a in asked], bank_draw_count=0,
            generated_count=0, status="active", started_at=datetime.now(UTC),
            style="standard", quota_counted=False, coverage={"asked": asked},
        ))
        await db.commit()


async def _ask(maker, **arguments):
    async with maker() as db:
        scope = RunScope(db=db, user_id="u1", profile_id="p1", mock_session_id="ms1")
        return await dispatch_tool(scope, "jc_mock_ask", {"mock_session_id": "ms1", **arguments})


async def _stem_count(maker, stem: str) -> int:
    async with maker() as db:
        return (await db.execute(
            select(func.count()).select_from(InterviewQuestion)
            .where(InterviewQuestion.stem == stem)
        )).scalar_one()


async def _session(maker) -> MockSession:
    async with maker() as db:
        return (await db.execute(select(MockSession))).scalar_one()


@pytest.mark.asyncio
async def test_asking_by_stem_creates_the_question_and_registers_it_once(maker):
    await _open_session(maker)
    result = await _ask(maker, stem=NEW_STEM, kind="main")
    assert result["accepted"] is True and result["label"] == "第 1 题"
    assert await _stem_count(maker, NEW_STEM) == 1
    stored = await _session(maker)
    assert stored.question_ids == [result["question_id"]]
    assert stored.generated_count == 1
    assert [a["question_id"] for a in stored.coverage["asked"]] == [result["question_id"]]


@pytest.mark.asyncio
async def test_asking_a_stem_already_in_the_bank_reuses_that_question(maker):
    await _open_session(maker)
    result = await _ask(maker, stem=BANK_STEM, kind="main")
    assert result["accepted"] is True and result["question_id"] == "bank1"
    assert await _stem_count(maker, BANK_STEM) == 1
    assert (await _session(maker)).generated_count == 0


@pytest.mark.asyncio
async def test_a_follow_up_can_be_asked_by_stem_under_the_id_the_main_question_returned(maker):
    await _open_session(maker)
    main = await _ask(maker, stem=NEW_STEM, kind="main")
    follow = await _ask(maker, stem="那次故障你是怎么定位到根因的", kind="followup",
                        parent_question_id=main["question_id"])
    assert follow["accepted"] is True and follow["label"] == "第 1 题 · 追问 1"


@pytest.mark.asyncio
async def test_asking_by_id_still_works_and_returns_the_id(maker):
    await _open_session(maker)
    result = await _ask(maker, question_id="bank1", kind="main")
    assert result["accepted"] is True and result["question_id"] == "bank1"


@pytest.mark.parametrize(
    ("arguments", "code"),
    [
        ({"kind": "main"}, "main_limit"),
        ({"kind": "followup", "parent_question_id": "never-asked"}, "parent_not_asked"),
    ],
)
@pytest.mark.asyncio
async def test_a_refused_ask_leaves_no_new_question_behind(maker, arguments, code):
    asked = FULL_OF_MAINS if code == "main_limit" else FULL_OF_MAINS[:1]
    await _open_session(maker, asked)
    before = await _session(maker)
    result = await _ask(maker, stem=NEW_STEM, **arguments)
    assert result["accepted"] is False and result["code"] == code
    assert await _stem_count(maker, NEW_STEM) == 0
    after = await _session(maker)
    assert after.question_ids == before.question_ids
    assert after.generated_count == before.generated_count
    assert after.coverage == before.coverage


@pytest.mark.asyncio
async def test_giving_both_or_neither_of_id_and_stem_is_an_error(maker):
    await _open_session(maker)
    with pytest.raises(ValueError, match="question_id or stem"):
        await _ask(maker, kind="main")
    with pytest.raises(ValueError, match="question_id or stem"):
        await _ask(maker, question_id="bank1", stem=NEW_STEM, kind="main")
    assert (await _session(maker)).coverage == {"asked": []}


@pytest.mark.asyncio
async def test_asking_the_same_stem_twice_is_refused_the_second_time(maker):
    await _open_session(maker)
    first = await _ask(maker, stem=NEW_STEM, kind="main")
    again = await _ask(maker, stem=NEW_STEM, kind="main")
    assert first["accepted"] is True
    assert again["accepted"] is False and again["code"] == "already_asked"
    assert await _stem_count(maker, NEW_STEM) == 1
    stored = await _session(maker)
    assert stored.question_ids == [first["question_id"]] and stored.generated_count == 1
