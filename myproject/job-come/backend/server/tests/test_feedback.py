"""Feedback inbox: user submission/reply, admin list/reply/status, and the
ownership isolation between users.

Same direct-call pattern as `test_admin_users.py` — `jc.main.app` eagerly
builds a real async MySQL engine on import, which this sandbox has no driver
for, so handlers/services are exercised directly against a SQLite-backed
`AsyncSession`.
"""

from __future__ import annotations

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.api.admin_router import (
    admin_get_feedback,
    admin_list_feedback,
    admin_reply_feedback,
    admin_set_feedback_status,
)
from jc.api.feedback_router import (
    add_feedback_message,
    create_feedback,
    get_feedback,
    list_feedback,
)
from jc.db.base import Base
from jc.exceptions import AppError, NotFoundError
from jc.models import *  # noqa: F403
from jc.models.enums import UserRole
from jc.models.user import User, UserMeta
from jc.schemas.admin_feedback import AdminFeedbackReplyRequest, AdminFeedbackStatusRequest
from jc.schemas.feedback import FeedbackCreateRequest, FeedbackReplyRequest
from jc.services.feedback_service import FeedbackService


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        admin = User(
            id="usr_admin", email="admin@example.test", password_hash="x", role=UserRole.ADMIN
        )
        alice = User(id="usr_alice", email="alice@example.test", password_hash="x")
        bob = User(id="usr_bob", email="bob@example.test", password_hash="x")
        session.add_all([admin, alice, bob])
        session.add(UserMeta(user_id="usr_alice", display_name="爱丽丝"))
        await session.commit()
        yield session
    await engine.dispose()


def _svc(db) -> FeedbackService:
    return FeedbackService(db)


def _alice() -> UserActor:
    return UserActor(user_id="usr_alice", session_id="sess_alice")


def _bob() -> UserActor:
    return UserActor(user_id="usr_bob", session_id="sess_bob")


def _admin() -> UserActor:
    return UserActor(user_id="usr_admin", session_id="sess_admin")


@pytest.mark.asyncio
async def test_create_and_list_feedback_for_user(db) -> None:
    created = await create_feedback(
        body=FeedbackCreateRequest(title="无法上传简历", category="bug", body="点上传没反应"),
        actor=_alice(),
        svc=_svc(db),
    )
    assert created.status == "open"
    assert created.message_count == 1
    assert created.messages[0].role == "user"

    listing = await list_feedback(actor=_alice(), svc=_svc(db))
    assert len(listing.threads) == 1
    assert listing.threads[0].id == created.id

    # Bob has no threads of his own.
    bob_listing = await list_feedback(actor=_bob(), svc=_svc(db))
    assert bob_listing.threads == []


@pytest.mark.asyncio
async def test_create_feedback_rejects_invalid_category(db) -> None:
    with pytest.raises(AppError):
        await create_feedback(
            body=FeedbackCreateRequest(title="x", category="not_a_category", body="y"),
            actor=_alice(),
            svc=_svc(db),
        )


@pytest.mark.asyncio
async def test_user_cannot_read_or_reply_to_someone_elses_thread(db) -> None:
    created = await create_feedback(
        body=FeedbackCreateRequest(title="无法上传简历", category="bug", body="点上传没反应"),
        actor=_alice(),
        svc=_svc(db),
    )

    with pytest.raises(NotFoundError):
        await get_feedback(thread_id=created.id, actor=_bob(), svc=_svc(db))

    with pytest.raises(NotFoundError):
        await add_feedback_message(
            thread_id=created.id,
            body=FeedbackReplyRequest(body="我也遇到了"),
            actor=_bob(),
            svc=_svc(db),
        )


@pytest.mark.asyncio
async def test_user_reply_reopens_resolved_thread(db) -> None:
    created = await create_feedback(
        body=FeedbackCreateRequest(title="无法上传简历", category="bug", body="点上传没反应"),
        actor=_alice(),
        svc=_svc(db),
    )
    await admin_set_feedback_status(
        thread_id=created.id,
        body=AdminFeedbackStatusRequest(status="resolved"),
        _=None,
        svc=_svc(db),
    )

    reopened = await add_feedback_message(
        thread_id=created.id,
        body=FeedbackReplyRequest(body="还是不行"),
        actor=_alice(),
        svc=_svc(db),
    )
    assert reopened.status == "open"
    assert reopened.message_count == 2
    assert reopened.last_message_role == "user"


@pytest.mark.asyncio
async def test_admin_list_filters_by_status_and_joins_user_identity(db) -> None:
    a = await create_feedback(
        body=FeedbackCreateRequest(title="A", category="bug", body="x"),
        actor=_alice(),
        svc=_svc(db),
    )
    await create_feedback(
        body=FeedbackCreateRequest(title="B", category="feature", body="y"),
        actor=_bob(),
        svc=_svc(db),
    )
    await admin_set_feedback_status(
        thread_id=a.id, body=AdminFeedbackStatusRequest(status="resolved"), _=None, svc=_svc(db)
    )

    everything = await admin_list_feedback(
        limit=50, offset=0, status=None, _=None, svc=_svc(db)
    )
    assert everything.total == 2
    by_id = {t.id: t for t in everything.threads}
    assert by_id[a.id].user_email == "alice@example.test"
    assert by_id[a.id].user_display_name == "爱丽丝"

    only_open = await admin_list_feedback(limit=50, offset=0, status="open", _=None, svc=_svc(db))
    assert only_open.total == 1
    assert only_open.threads[0].title == "B"


@pytest.mark.asyncio
async def test_admin_reply_sets_replying_status_and_appends_message(db) -> None:
    created = await create_feedback(
        body=FeedbackCreateRequest(title="A", category="bug", body="x"),
        actor=_alice(),
        svc=_svc(db),
    )

    replied = await admin_reply_feedback(
        thread_id=created.id,
        body=AdminFeedbackReplyRequest(body="已定位问题，修复中"),
        actor=_admin(),
        svc=_svc(db),
    )
    assert replied.status == "replying"
    assert replied.message_count == 2
    assert replied.messages[-1].role == "admin"


@pytest.mark.asyncio
async def test_admin_get_missing_thread_raises_not_found(db) -> None:
    with pytest.raises(NotFoundError):
        await admin_get_feedback(thread_id="fbt_missing", _=None, svc=_svc(db))


@pytest.mark.asyncio
async def test_admin_set_status_rejects_invalid_status(db) -> None:
    created = await create_feedback(
        body=FeedbackCreateRequest(title="A", category="bug", body="x"),
        actor=_alice(),
        svc=_svc(db),
    )
    with pytest.raises(AppError):
        await admin_set_feedback_status(
            thread_id=created.id,
            body=AdminFeedbackStatusRequest(status="not_a_status"),
            _=None,
            svc=_svc(db),
        )


# --- TimestampMixin: created_at must be populated without a DB round-trip ---

from sqlalchemy import inspect as sa_inspect  # noqa: E402


async def test_created_at_is_populated_client_side_after_flush(db):
    """Regression test for `MissingGreenlet` on real async MySQL.

    `jc_feedback_thread.created_at` used to rely solely on `server_default`,
    which leaves the attribute "expired" after flush — reading it outside an
    awaited context (exactly what `_thread_item()` does synchronously inside
    `model_dump()`) crashed with `sqlalchemy.exc.MissingGreenlet` against the
    real aiomysql driver. SQLite's driver tolerated it, which is why this
    shipped unnoticed. `sa_inspect(row).unloaded` is the direct way to assert
    "this attribute needs a DB trip to read" without actually triggering one.
    """
    svc = _svc(db)
    created = await svc.create_thread(
        user_id="usr_alice",
        body=FeedbackCreateRequest(title="标题", category="bug", body="内容"),
    )
    thread = await db.get(FeedbackThread, created.id)
    unloaded = sa_inspect(thread).unloaded
    assert "created_at" not in unloaded
    assert "updated_at" not in unloaded
    assert thread.created_at is not None


# --- commit discipline: writes must survive past this request's session ----
#
# `get_db_session()` only closes the session at the end of a request; it
# never commits (see `src/jc/db/session.py`). Every write method on a
# service is individually responsible for calling `self._db.commit()`.
#
# A visibility test across two independent SQLite ":memory:" sessions can't
# tell commit from no-commit here: this fixture's engine hands out a single
# pooled connection, so a second session shares that connection's
# (uncommitted) transaction state regardless of whether `commit()` ran —
# the exact trap `test_created_at_is_populated_client_side_after_flush`'s
# docstring already flags for this file ("SQLite's driver tolerated it").
# `NullPool`/shared-cache URIs dodge that but then lose the schema between
# connections instead. So: spy on `AsyncSession.commit` directly and assert
# it was actually called for every write path, which is dialect-independent
# and catches exactly the bug that shipped (`flush()`-only, no `commit()`).


def _commit_spy(db, monkeypatch):
    calls = {"count": 0}
    original_commit = db.commit

    async def spy():
        calls["count"] += 1
        await original_commit()

    monkeypatch.setattr(db, "commit", spy)
    return calls


async def test_create_thread_commits(db, monkeypatch):
    calls = _commit_spy(db, monkeypatch)
    await create_feedback(
        body=FeedbackCreateRequest(title="A", category="bug", body="x"),
        actor=_alice(),
        svc=_svc(db),
    )
    assert calls["count"] >= 1, "create_thread() did not call db.commit()"


async def test_add_user_message_commits(db, monkeypatch):
    created = await create_feedback(
        body=FeedbackCreateRequest(title="A", category="bug", body="x"),
        actor=_alice(),
        svc=_svc(db),
    )
    calls = _commit_spy(db, monkeypatch)
    await add_feedback_message(
        thread_id=created.id,
        body=FeedbackReplyRequest(body="追问"),
        actor=_alice(),
        svc=_svc(db),
    )
    assert calls["count"] >= 1, "add_user_message() did not call db.commit()"


async def test_admin_reply_commits(db, monkeypatch):
    created = await create_feedback(
        body=FeedbackCreateRequest(title="A", category="bug", body="x"),
        actor=_alice(),
        svc=_svc(db),
    )
    calls = _commit_spy(db, monkeypatch)
    await admin_reply_feedback(
        thread_id=created.id,
        body=AdminFeedbackReplyRequest(body="已收到"),
        actor=_admin(),
        svc=_svc(db),
    )
    assert calls["count"] >= 1, "admin_reply() did not call db.commit()"


async def test_admin_set_status_commits(db, monkeypatch):
    created = await create_feedback(
        body=FeedbackCreateRequest(title="A", category="bug", body="x"),
        actor=_alice(),
        svc=_svc(db),
    )
    calls = _commit_spy(db, monkeypatch)
    await admin_set_feedback_status(
        thread_id=created.id,
        body=AdminFeedbackStatusRequest(status="resolved"),
        _=None,
        svc=_svc(db),
    )
    assert calls["count"] >= 1, "admin_set_status() did not call db.commit()"
