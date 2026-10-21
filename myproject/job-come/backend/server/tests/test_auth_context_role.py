"""`AuthContextResponse`: role is surfaced on `user`, and an admin gets the extra
`"admin"` capability so the frontend nav tab has a single source of truth to
check instead of re-deriving admin-ness some other way.
"""

from __future__ import annotations

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.db.base import Base
from jc.models import *  # noqa: F403
from jc.models.enums import UserRole
from jc.models.user import User
from jc.services.auth_service import AuthService


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add(
            User(id="usr_admin", email="admin@example.com", password_hash="x", role=UserRole.ADMIN)
        )
        session.add(User(id="usr_plain", email="plain@example.com", password_hash="x"))
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_user_gets_admin_capability_and_role(db) -> None:
    context = await AuthService(db).build_context(
        actor=UserActor(user_id="usr_admin", session_id="sess_1")
    )
    assert context.user.role == "admin"
    assert "admin" in context.capabilities


@pytest.mark.asyncio
async def test_plain_user_does_not_get_admin_capability(db) -> None:
    context = await AuthService(db).build_context(
        actor=UserActor(user_id="usr_plain", session_id="sess_2")
    )
    assert context.user.role == "user"
    assert "admin" not in context.capabilities
