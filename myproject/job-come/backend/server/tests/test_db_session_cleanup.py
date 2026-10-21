"""Request teardown must finish driver cleanup even in a cancelled scope."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import anyio
import pytest
from sqlalchemy.exc import DBAPIError, IllegalStateChangeError

from jc.db import session as mod


@pytest.mark.asyncio
async def test_request_session_close_survives_disconnect(monkeypatch):
    done = asyncio.Event()
    async def close():
        await asyncio.sleep(.01)
        done.set()
    db = SimpleNamespace(close=close)
    monkeypatch.setattr(mod, "AsyncSessionLocal", lambda: db)
    dep = mod.get_db_session()
    assert await anext(dep) is db
    with anyio.CancelScope() as scope:
        scope.cancel()
        await dep.aclose()
    assert done.is_set()


@pytest.mark.asyncio
async def test_programming_error_is_not_misreported_as_mysql_disconnect(monkeypatch):
    db = SimpleNamespace(close=AsyncMock(side_effect=IllegalStateChangeError("concurrent owner")),
                         invalidate=AsyncMock())
    monkeypatch.setattr(mod, "AsyncSessionLocal", lambda: db)
    dep = mod.get_db_session()
    await anext(dep)
    with pytest.raises(IllegalStateChangeError):
        await dep.aclose()
    db.invalidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_real_driver_error_still_invalidates_session(monkeypatch):
    db = SimpleNamespace(close=AsyncMock(side_effect=DBAPIError(None, None, Exception("lost connection"))),
                         invalidate=AsyncMock())
    monkeypatch.setattr(mod, "AsyncSessionLocal", lambda: db)
    dep = mod.get_db_session()
    await anext(dep)
    await dep.aclose()
    db.invalidate.assert_awaited_once()
