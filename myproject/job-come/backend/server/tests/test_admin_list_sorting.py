"""Admin lists are sortable by column, and an unsupported sort is rejected.

Why these exist: every admin list was pinned to one order (`updated_at DESC`,
`created_at DESC`, `last_message_at DESC`), so "which call burned the most
tokens", "what is the slowest call" and "what feedback has been waiting longest"
were unanswerable without paging through everything.

Three properties are easy to lose later and are each pinned below:
  * The sort key never reaches SQL unless it is in the store's allow-list.
  * An unknown key is a 400, not a silent fallback — a header rendered as sorted
    over rows that are not sorted is worse than an error.
  * Every order carries a unique tiebreaker, so offset pagination over a
    low-cardinality column (`status`) cannot repeat or skip a row.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.api.admin_router import admin_list_feedback, admin_list_llm_calls, admin_list_sessions, admin_list_users
from jc.db.base import Base
from jc.exceptions import AppError
from jc.models import *  # noqa: F403
from jc.models.agent import AgentSession
from jc.models.feedback import FeedbackThread
from jc.models.llm_call import LlmCall
from jc.models.user import User, UserMeta
from jc.services.admin_user_service import AdminUserService
from jc.services.feedback_service import FeedbackService
from jc.services.session_audit_service import SessionAuditService
from jc.stores.agent_store import SESSION_SORT
from jc.stores.feedback_store import FEEDBACK_SORT
from jc.stores.llm_call_store import LLM_CALL_SORT
from jc.stores.sorting import SortSpec
from jc.stores.user_store import USER_SORT

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        # Users: created in a deliberately different order than their emails and
        # display names sort, so a passing assertion cannot be an accident of
        # insertion order.
        session.add(User(id="usr_b", email="b@example.com", password_hash="x", created_at=_at(10)))
        session.add(UserMeta(user_id="usr_b", display_name="周一"))
        session.add(User(id="usr_a", email="a@example.com", password_hash="x", created_at=_at(30)))
        session.add(UserMeta(user_id="usr_a", display_name="吴二"))
        session.add(User(id="usr_c", email="c@example.com", password_hash="x", created_at=_at(20)))

        for sid, updated, status in (
            ("agsn_old", _at(5), "active"),
            ("agsn_new", _at(50), "active"),
            ("agsn_mid", _at(25), "closed"),
        ):
            session.add(
                AgentSession(
                    id=sid,
                    user_id="usr_a",
                    deerflow_thread_id=f"t-{sid}",
                    status=status,
                    updated_at=updated,
                    created_at=_at(0),
                )
            )

        for cid, created, tokens, latency, cost in (
            ("llm_cheap", _at(40), 100, 900, 5),
            ("llm_heavy", _at(10), 50_000, 120, 9_000),
            ("llm_slow", _at(20), 2_000, 45_000, 300),
        ):
            session.add(
                LlmCall(
                    id=cid,
                    user_id="usr_a",
                    scenario="writer",
                    caller="resume_elevator",
                    channel="harness",
                    status="success",
                    total_tokens=tokens,
                    latency_ms=latency,
                    cost_micro_usd=cost,
                    created_at=created,
                )
            )

        for tid, created, last, count in (
            ("fbt_oldest", _at(1), _at(60), 9),
            ("fbt_newest", _at(55), _at(56), 1),
            ("fbt_mid", _at(20), _at(21), 4),
        ):
            session.add(
                FeedbackThread(
                    id=tid,
                    user_id="usr_a",
                    title=f"标题 {tid}",
                    category="bug",
                    status="open",
                    last_message_role="user",
                    last_message_at=last,
                    message_count=count,
                    created_at=created,
                )
            )
        await session.commit()
        yield session
    await engine.dispose()


# --- SortSpec itself -------------------------------------------------------------


def test_an_unknown_field_is_rejected_rather_than_reaching_sql() -> None:
    """The key arrives from a query string, so the allow-list is the boundary."""
    with pytest.raises(AppError) as err:
        SESSION_SORT.resolve("payload_json", "asc")
    assert err.value.code == "invalid_sort_field"
    # The message names what *is* allowed, so the caller can fix the request.
    assert "updated_at" in err.value.message


def test_an_unknown_direction_is_rejected() -> None:
    with pytest.raises(AppError) as err:
        SESSION_SORT.resolve("updated_at", "sideways")
    assert err.value.code == "invalid_sort_direction"


def test_no_sort_resolves_to_the_lists_own_default() -> None:
    assert SESSION_SORT.resolve(None, None) == ("updated_at", "desc")
    assert LLM_CALL_SORT.resolve(None, None) == ("created_at", "desc")


def test_a_direction_is_case_insensitive() -> None:
    assert SESSION_SORT.resolve("created_at", "ASC") == ("created_at", "asc")


def test_every_order_carries_a_tiebreaker() -> None:
    """`ORDER BY status` alone is not a total order, and offset pagination over a
    non-total order can return the same row on two pages or no page at all."""
    clauses, _, _ = SESSION_SORT.order_by("status", "asc")
    assert len(clauses) == 2

    # Sorting *by* the tiebreaker must not repeat it.
    clauses, _, _ = SESSION_SORT.order_by("id", "asc")
    assert len(clauses) == 1


def test_a_misdeclared_spec_fails_at_declaration_time() -> None:
    """A bad spec is a programming error; it should not wait for a request."""
    with pytest.raises(ValueError):
        SortSpec(fields={"id": User.id}, default="created_at", tiebreaker=User.id)
    with pytest.raises(ValueError):
        SortSpec(
            fields={"id": User.id},
            default="id",
            tiebreaker=User.id,
            default_direction="downwards",
        )


# --- sessions --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sessions_default_to_most_recently_active(db) -> None:
    res = await admin_list_sessions(audit=SessionAuditService(db))
    assert [s.id for s in res.sessions] == ["agsn_new", "agsn_mid", "agsn_old"]
    assert (res.sort_by, res.sort_dir) == ("updated_at", "desc")


@pytest.mark.asyncio
async def test_sessions_can_be_sorted_oldest_first(db) -> None:
    res = await admin_list_sessions(sort_by="updated_at", sort_dir="asc", audit=SessionAuditService(db))
    assert [s.id for s in res.sessions] == ["agsn_old", "agsn_mid", "agsn_new"]
    # The response echoes the applied order so the header marks the right column.
    assert (res.sort_by, res.sort_dir) == ("updated_at", "asc")


@pytest.mark.asyncio
async def test_an_unsupported_session_sort_is_an_error(db) -> None:
    with pytest.raises(AppError):
        await admin_list_sessions(sort_by="trace_id", audit=SessionAuditService(db))


# --- llm calls -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_calls_sort_by_tokens_to_find_the_expensive_turn(db) -> None:
    res = await admin_list_llm_calls(sort_by="total_tokens", sort_dir="desc", db=db)
    assert [c.id for c in res.calls] == ["llm_heavy", "llm_slow", "llm_cheap"]


@pytest.mark.asyncio
async def test_llm_calls_sort_by_latency_to_find_the_slow_turn(db) -> None:
    res = await admin_list_llm_calls(sort_by="latency_ms", sort_dir="desc", db=db)
    assert [c.id for c in res.calls] == ["llm_slow", "llm_cheap", "llm_heavy"]


@pytest.mark.asyncio
async def test_llm_calls_sort_by_cost(db) -> None:
    res = await admin_list_llm_calls(sort_by="cost_micro_usd", sort_dir="asc", db=db)
    assert [c.id for c in res.calls] == ["llm_cheap", "llm_slow", "llm_heavy"]
    assert (res.sort_by, res.sort_dir) == ("cost_micro_usd", "asc")


@pytest.mark.asyncio
async def test_llm_calls_default_to_newest_first(db) -> None:
    res = await admin_list_llm_calls(db=db)
    assert [c.id for c in res.calls] == ["llm_cheap", "llm_slow", "llm_heavy"]


# --- users -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_users_sort_by_email(db) -> None:
    res = await admin_list_users(sort_by="email", sort_dir="asc", service=AdminUserService(db))
    assert [u.email for u in res.users] == [
        "a@example.com",
        "b@example.com",
        "c@example.com",
    ]


@pytest.mark.asyncio
async def test_users_sort_by_display_name_which_lives_on_another_table(db) -> None:
    """`display_name` is on `UserMeta`, so this is the case the unconditional
    outer join exists for. The user without a meta row must still appear."""
    res = await admin_list_users(
        sort_by="display_name", sort_dir="asc", service=AdminUserService(db)
    )
    assert len(res.users) == 3
    named = [u.display_name for u in res.users if u.display_name]
    assert named == ["吴二", "周一"]


@pytest.mark.asyncio
async def test_users_sort_by_verification_groups_the_unverified(db) -> None:
    """The table's "邮箱验证" column renders from `email_verified_at`, so that is
    the key the header has to send — not `status`, which is a different column."""
    res = await admin_list_users(
        sort_by="email_verified_at", sort_dir="asc", service=AdminUserService(db)
    )
    assert len(res.users) == 3
    assert (res.sort_by, res.sort_dir) == ("email_verified_at", "asc")


@pytest.mark.asyncio
async def test_every_clickable_header_key_is_actually_sortable() -> None:
    """Each admin table renders `SortableTh columnKey=...`; a key the store does
    not allow renders a clickable header that only ever produces a 400."""
    assert {"email", "display_name", "role", "email_verified_at", "created_at"} <= set(USER_SORT.keys)
    assert {
        "created_at",
        "user_id",
        "scenario",
        "session_id",
        "channel",
        "final_model",
        "status",
        "attempt_count",
        "latency_ms",
        "total_tokens",
        "cost_micro_usd",
    } <= set(LLM_CALL_SORT.keys)
    assert {
        "title",
        "user_id",
        "category",
        "status",
        "message_count",
        "last_message_at",
    } <= set(FEEDBACK_SORT.keys)
    # The sessions rail offers these in a picker rather than as headers.
    assert {"updated_at", "created_at", "status", "kind", "skill_hint", "user_id", "id"} <= set(
        SESSION_SORT.keys
    )


@pytest.mark.asyncio
async def test_users_search_still_works_alongside_a_sort(db) -> None:
    res = await admin_list_users(
        search="example.com", sort_by="email", sort_dir="desc", service=AdminUserService(db)
    )
    # The join is one-to-one, so searching must not duplicate rows.
    assert [u.email for u in res.users] == [
        "c@example.com",
        "b@example.com",
        "a@example.com",
    ]
    assert res.total == 3


# --- feedback --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_feedback_defaults_to_the_most_recently_active_thread(db) -> None:
    res = await admin_list_feedback(svc=FeedbackService(db))
    assert [t.id for t in res.threads] == ["fbt_oldest", "fbt_newest", "fbt_mid"]
    assert (res.sort_by, res.sort_dir) == ("last_message_at", "desc")


@pytest.mark.asyncio
async def test_feedback_sorts_by_filing_time_to_find_what_waited_longest(db) -> None:
    res = await admin_list_feedback(sort_by="created_at", sort_dir="asc", svc=FeedbackService(db))
    assert [t.id for t in res.threads] == ["fbt_oldest", "fbt_mid", "fbt_newest"]


@pytest.mark.asyncio
async def test_feedback_sorts_by_message_count(db) -> None:
    res = await admin_list_feedback(
        sort_by="message_count", sort_dir="desc", svc=FeedbackService(db)
    )
    assert [t.id for t in res.threads] == ["fbt_oldest", "fbt_mid", "fbt_newest"]
