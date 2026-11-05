"""`require_admin`: authorization is the caller's `User.role`, not a shared secret.

`JC_ADMIN_ENABLED` is only the deployment-level kill switch; a logged-in
non-admin user must still be rejected, and an admin user must pass.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.api.deps import require_admin
from jc.db.base import Base
from jc.exceptions import ForbiddenError
from jc.models import *  # noqa: F403
from jc.models.enums import UserRole
from jc.models.user import User


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add(
            User(id="usr_admin", email="admin@example.test", password_hash="x", role=UserRole.ADMIN)
        )
        session.add(User(id="usr_plain", email="plain@example.test", password_hash="x"))
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_role_passes(db) -> None:
    with patch("jc.api.deps.settings.jc_admin_enabled", True):
        actor = UserActor(user_id="usr_admin", session_id="sess_1")
        result = await require_admin(request=None, actor=actor, db=db)
        assert result is actor


@pytest.mark.asyncio
async def test_non_admin_role_is_rejected(db) -> None:
    with patch("jc.api.deps.settings.jc_admin_enabled", True):
        actor = UserActor(user_id="usr_plain", session_id="sess_2")
        with pytest.raises(ForbiddenError):
            await require_admin(request=None, actor=actor, db=db)


@pytest.mark.asyncio
async def test_disabled_deployment_rejects_even_an_admin(db) -> None:
    with (
        patch("jc.api.deps.settings.jc_admin_enabled", False),
        patch("jc.api.deps.settings.jc_env", "production"),
    ):
        actor = UserActor(user_id="usr_admin", session_id="sess_1")
        with pytest.raises(ForbiddenError):
            await require_admin(request=None, actor=actor, db=db)


@pytest.mark.asyncio
async def test_missing_user_is_rejected(db) -> None:
    with patch("jc.api.deps.settings.jc_admin_enabled", True):
        actor = UserActor(user_id="usr_deleted", session_id="sess_3")
        with pytest.raises(ForbiddenError):
            await require_admin(request=None, actor=actor, db=db)
