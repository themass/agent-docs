"""The agent's two intake tools: read the plan, write the user's answers.

These exist because the interview-by-chat path had no way to make progress. The coach
was handed the shortfall as prose composed before its turn started, so after writing an
answer down it could not tell whether the profile now cleared the bar, and the only
write path it had (`jc_profile_patch`) turned every transcribed sentence into a confirm
card asking the user to approve their own words.

`jc_intake_record` is the one place in JC where a model writes to a profile without a
confirmation card. What makes that safe is not trust, it is the plan: the question must
be currently open, and the path is taken from the plan rather than from the model. The
tests below are mostly about that boundary holding.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.authz import RunScope
from jc.db.base import Base
from jc.mcp.handlers import dispatch_tool, intake_plan, intake_record
from jc.models import *  # noqa: F403
from jc.models.profile import Profile
from jc.models.user import User


@pytest.fixture
async def ctx():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        db.add(User(id="usr_owner", email="owner@example.test", password_hash="test"))
        db.add(
            Profile(
                id="prof_owned",
                user_id="usr_owner",
                owner_kind="user",
                payload={"contact": {"name": ""}},
                version=1,
            )
        )
        db.add(Profile(id="prof_other", owner_kind="guest", payload={}, version=1))
        await db.commit()
        yield RunScope(
            db=db, user_id="usr_owner", profile_id="prof_owned", session_id="agsn_test"
        )
    await engine.dispose()


@pytest.mark.asyncio
async def test_plan_reports_what_an_empty_profile_is_missing(ctx) -> None:
    plan = await intake_plan(ctx)
    assert plan["mode"] == "empty"
    assert plan["can_generate"] is False
    assert plan["blocking"], "an empty profile must say what it needs"
    assert plan["questions"], "an empty profile must have something to ask"
    assert all(q["id"] and q["target_path"] for q in plan["questions"])


@pytest.mark.asyncio
async def test_recording_an_answer_writes_it_verbatim_and_advances_the_plan(ctx) -> None:
    plan = await intake_plan(ctx)
    name_q = next(q for q in plan["questions"] if q["target_path"] == "contact.name")

    result = await intake_record(
        ctx, answers=[{"question_id": name_q["id"], "answer": "李雷"}]
    )
    assert result["stored"] == 1
    assert result["version"] == 2
    assert [w["path"] for w in result["applied"]] == ["contact.name"]
    # Labelled in the user's words, because an unverifiable confirmation is not one.
    assert result["applied"][0]["value"] == "李雷"

    after = await intake_plan(ctx)
    assert name_q["id"] not in {q["id"] for q in after["questions"]}
    assert "李雷" in {a["answer"] for a in after["answered"]}


@pytest.mark.asyncio
async def test_a_question_that_is_not_open_is_refused(ctx) -> None:
    """The plan is the authorization. A model that did not re-read it cannot write."""
    with pytest.raises(ValueError, match="not open"):
        await intake_record(
            ctx, answers=[{"question_id": "identity.invented", "answer": "任意内容"}]
        )


@pytest.mark.asyncio
async def test_an_already_answered_question_cannot_be_rewritten_blind(ctx) -> None:
    """Re-answering goes through the panel, where the user can see the old value.

    An agent re-submitting an answered question is the signature of a model working
    from a stale plan, and the content it would overwrite is the user's own earlier
    sentence.
    """
    plan = await intake_plan(ctx)
    name_q = next(q for q in plan["questions"] if q["target_path"] == "contact.name")
    await intake_record(ctx, answers=[{"question_id": name_q["id"], "answer": "李雷"}])

    with pytest.raises(ValueError, match="not open"):
        await intake_record(
            ctx, answers=[{"question_id": name_q["id"], "answer": "韩梅梅"}]
        )

    row = await ctx.db.get(Profile, "prof_owned")
    assert row.payload["contact"]["name"] == "李雷"


@pytest.mark.asyncio
async def test_a_mismatched_target_path_is_refused_without_writing(ctx) -> None:
    """The path comes from the plan. A model may not redirect an answer elsewhere."""
    plan = await intake_plan(ctx)
    name_q = next(q for q in plan["questions"] if q["target_path"] == "contact.name")

    with pytest.raises(ValueError, match="target_path"):
        await intake_record(
            ctx,
            answers=[
                {
                    "question_id": name_q["id"],
                    "answer": "李雷",
                    "target_path": "summary",
                }
            ],
        )
    row = await ctx.db.get(Profile, "prof_owned")
    assert row.version == 1
    assert not row.payload.get("summary")


@pytest.mark.asyncio
async def test_an_empty_or_blank_answer_is_refused(ctx) -> None:
    plan = await intake_plan(ctx)
    name_q = next(q for q in plan["questions"] if q["target_path"] == "contact.name")
    with pytest.raises(ValueError):
        await intake_record(ctx, answers=[])
    with pytest.raises(ValueError, match="answer"):
        await intake_record(ctx, answers=[{"question_id": name_q["id"], "answer": "   "}])


@pytest.mark.asyncio
async def test_neither_tool_reaches_a_profile_the_run_does_not_own(ctx) -> None:
    ctx.profile_id = "prof_other"
    with pytest.raises(PermissionError):
        await intake_plan(ctx)
    with pytest.raises(PermissionError):
        await intake_record(ctx, answers=[{"question_id": "x", "answer": "y"}])


@pytest.mark.asyncio
async def test_record_marks_the_slot_the_plan_named_not_the_next_free_one(ctx) -> None:
    """The id written and the id the plan drops must be the same id.

    This is the silent failure the shared `highlight_slot_ids` exists to prevent: an
    answer filed under a different question than the one asked leaves that question
    open forever, so the interview keeps asking for a bullet it already holds.
    """
    row = await ctx.db.get(Profile, "prof_owned")
    row.payload = {
        "contact": {"name": "李雷"},
        "experiences": [
            {
                "id": "exp_1",
                "company": "某某科技",
                "title": "后端专家",
                "start_date": "2021-03",
                "highlights": ["把订单链路的超时率从 3% 降到 0.4%"],
            }
        ],
    }
    await ctx.db.commit()

    plan = await intake_plan(ctx, limit=20)
    slot_q = next(
        q for q in plan["questions"] if q["target_path"].startswith("experiences[0].highlights")
    )
    result = await intake_record(
        ctx,
        answers=[{"question_id": slot_q["id"], "answer": "带 4 个人做完支付迁移"}],
    )
    assert [w["path"] for w in result["applied"]] == [slot_q["target_path"]]

    after = await intake_plan(ctx, limit=20)
    assert slot_q["id"] not in {q["id"] for q in after["questions"]}
    row = await ctx.db.get(Profile, "prof_owned")
    assert "带 4 个人做完支付迁移" in row.payload["experiences"][0]["highlights"]


@pytest.mark.asyncio
async def test_both_tools_are_reachable_through_the_dispatcher(ctx) -> None:
    """The in-process path the harness actually calls, not just the functions."""
    plan = await dispatch_tool(ctx, "jc_intake_plan", {"limit": 3})
    assert len(plan["questions"]) <= 3
    name_q = next(q for q in plan["questions"] if q["target_path"] == "contact.name")
    result = await dispatch_tool(
        ctx,
        "jc_intake_record",
        {"answers": [{"question_id": name_q["id"], "answer": "李雷"}]},
    )
    assert result["stored"] == 1
