"""Admin user directory: `GET /admin/users` and `GET /admin/users/{id}`.

Same direct-call pattern as `test_admin_trace_export.py` — `jc.main.app` eagerly
builds a real async MySQL engine on import, which this sandbox has no driver for,
so the handler is exercised directly against a SQLite-backed `AsyncSession`.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.api.admin_router import admin_get_profile, admin_get_user, admin_list_users
from jc.db.base import Base
from jc.models import *  # noqa: F403
from jc.models.agent import AgentSession
from jc.models.enums import ProfileStatus, UserRole
from jc.models.profile import Profile
from jc.models.user import User, UserMeta


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        admin = User(
            id="usr_admin", email="admin@example.test", password_hash="x", role=UserRole.ADMIN
        )
        plain = User(id="usr_plain", email="plain@example.test", password_hash="x")
        session.add_all([admin, plain])
        session.add(UserMeta(user_id="usr_plain", display_name="张三"))
        session.add(Profile(id="prof_1", user_id="usr_plain", status=ProfileStatus.CONFIRMED))
        session.add(AgentSession(id="agsn_1", user_id="usr_plain", deerflow_thread_id="thread_1"))
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_list_users_includes_profile_and_session_counts(db) -> None:
    response = await admin_list_users(limit=50, offset=0, search=None, _=None, service=_service(db))
    by_id = {u.id: u for u in response.users}
    assert response.total == 2
    assert by_id["usr_plain"].profile_count == 1
    assert by_id["usr_plain"].session_count == 1
    assert by_id["usr_plain"].display_name == "张三"
    assert by_id["usr_admin"].role == "admin"


@pytest.mark.asyncio
async def test_list_users_search_matches_email_or_display_name(db) -> None:
    response = await admin_list_users(
        limit=50, offset=0, search="张三", _=None, service=_service(db)
    )
    assert [u.id for u in response.users] == ["usr_plain"]

    response = await admin_list_users(
        limit=50, offset=0, search="admin@", _=None, service=_service(db)
    )
    assert [u.id for u in response.users] == ["usr_admin"]


@pytest.mark.asyncio
async def test_get_user_detail_lists_profiles(db) -> None:
    detail = await admin_get_user(user_id="usr_plain", _=None, service=_service(db))
    assert detail.id == "usr_plain"
    assert len(detail.profiles) == 1
    assert detail.profiles[0].id == "prof_1"
    assert detail.profiles[0].status == "confirmed"


@pytest.mark.asyncio
async def test_get_user_detail_missing_user_raises_not_found(db) -> None:
    from jc.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        await admin_get_user(user_id="usr_missing", _=None, service=_service(db))


@pytest.mark.asyncio
async def test_get_profile_returns_full_payload(db) -> None:
    detail = await admin_get_profile(profile_id="prof_1", _=None, service=_service(db))
    assert detail.id == "prof_1"
    assert detail.status == "confirmed"
    assert detail.payload is not None


@pytest.mark.asyncio
async def test_get_profile_missing_raises_not_found(db) -> None:
    from jc.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        await admin_get_profile(profile_id="prof_missing", _=None, service=_service(db))


def _service(db):
    from jc.services.admin_user_service import AdminUserService

    return AdminUserService(db)
