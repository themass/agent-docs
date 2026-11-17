"""Regression tests for the profile-parse queue's failure paths (B-3).

Two production defects, 2026-11-18:

1. `parse_stored_source` read `profile.sources`, lazy-loading the relationship on a
   fresh background session — `MissingGreenlet`, raised *before* any try-block, so
   the row never settled.
2. The dispatcher's catch-all logged the crash and rolled back, leaving the row
   PROCESSING until its lease expired, then re-claiming it forever: one poison row
   re-raised the same traceback every 30s.

Each test below has the opposite-side control named in its docstring, so a fix that
merely silences the log (or blocks every row) fails.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc import tasks as tasks_module
from jc.db.base import Base
from jc.models.enums import ParseStatus
from jc.models.profile import Profile, ProfileSource
from jc.services import profile_service as ps_module
from jc.services.profile_service import ProfileService


class FakeStorage:
    def get_object_bytes(self, key: str) -> bytes:
        raise RuntimeError("storage down for test")


@pytest.fixture
async def env(monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/parse.sqlite")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(ps_module, "get_storage_backend", lambda: FakeStorage())
    # tasks.py binds AsyncSessionLocal at import time (module top), so the patch
    # target is the module attribute, not jc.db.session.
    monkeypatch.setattr(tasks_module, "AsyncSessionLocal", sessions)

    async def seed(*, parse_status=ParseStatus.PENDING, token=None, lease=None):
        async with sessions() as db:
            db.add(Profile(id="prof_p", payload={}))
            db.add(
                ProfileSource(
                    id="psrc_p",
                    profile_id="prof_p",
                    file_name="cv.pdf",
                    storage_key="jc/test/cv.pdf",
                    parse_status=parse_status,
                    parse_claim_token=token,
                    parse_lease_until=lease,
                )
            )
            await db.commit()

    return sessions, seed


async def _row(sessions, source_id="psrc_p"):
    async with sessions() as db:
        return await db.get(ProfileSource, source_id)


# --- defect 1: relationship lazy-load crashed the whole parse path -------


async def test_source_lookup_does_not_lazy_load_relationship(env):
    """Reject side: a *missing* source must return False. The old code raised
    MissingGreenlet while scanning `profile.sources` instead — before the None
    check — so this fails loudly if the lazy access comes back. Pass side below."""
    sessions, seed = env
    await seed()
    async with sessions() as db:
        svc = ProfileService(db)
        assert await svc.parse_stored_source("prof_p", "psrc_missing") is False


async def test_existing_source_reaches_storage_and_settles_failed(env):
    """Pass side of the same lookup: an existing source gets past loading and
    settles to FAILED when storage fails (the pre-existing terminal path)."""
    sessions, seed = env
    await seed()
    async with sessions() as db:
        svc = ProfileService(db)
        assert await svc.parse_stored_source("prof_p", "psrc_p") is False
    row = await _row(sessions)
    assert row.parse_status == ParseStatus.FAILED
    assert row.parse_status != ParseStatus.PROCESSING  # not left claimable


# --- defect 2: deterministic crash left a poison row ----------------------


async def test_crash_settles_row_to_failed(env, monkeypatch):
    """Reject side: a crash must not leave the row claimable. The dispatcher's
    candidate query excludes FAILED, so a settled row is never re-raised."""
    sessions, seed = env
    # Seeded with a live foreign lease the claim would SKIP (the row is not ours
    # yet); the dispatcher path needs a claimable row, so queue it fresh instead.
    await seed(parse_status=ParseStatus.PENDING)

    async def boom(self, profile_id, source_id, *, claim_token=None):
        raise RuntimeError("deterministic poison crash")

    monkeypatch.setattr(ProfileService, "parse_stored_source", boom)
    await tasks_module.parse_profile_source("prof_p", "psrc_p")

    row = await _row(sessions)
    assert row.parse_status == ParseStatus.FAILED
    assert row.parse_claim_token is None
    assert row.parse_phase == "failed"


async def test_crash_update_does_not_stomp_a_foreign_claim(env, monkeypatch):
    """Guard side: the terminal write is claim-token-guarded. If our lease expired
    and another worker re-claimed the row, our crash must not mark *their* claim
    FAILED."""
    sessions, seed = env
    await seed(
        parse_status=ParseStatus.PROCESSING,
        token="tok-other",
        lease=datetime.now(UTC) + timedelta(hours=1),
    )

    async def boom(self, profile_id, source_id, *, claim_token=None):
        raise RuntimeError("stale worker crash after lease loss")

    monkeypatch.setattr(ProfileService, "parse_stored_source", boom)
    # Pretend this worker claimed earlier (tok-1) and lost the lease; the row is
    # now held by tok-other, which is exactly the seeded state.
    monkeypatch.setattr(
        tasks_module, "claim_profile_parse", lambda profile_id, source_id: _returns("tok-1")
    )
    await tasks_module.parse_profile_source("prof_p", "psrc_p")

    row = await _row(sessions)
    assert row.parse_status == ParseStatus.PROCESSING
    assert row.parse_claim_token == "tok-other"


async def _returns(value):
    return value


async def test_pending_row_is_still_dispatched(env, monkeypatch):
    """Pass side of the terminal state: settling one poison row must not stop the
    queue. A fresh PENDING row still gets claimed and dispatched."""
    sessions, seed = env
    await seed()
    dispatched: list[tuple[str, str]] = []

    async def fake_parse(profile_id, source_id):
        dispatched.append((profile_id, source_id))

    monkeypatch.setattr(tasks_module, "parse_profile_source", fake_parse)
    await tasks_module.recover_stale_profile_parses()
    await asyncio.sleep(0)
    assert ("prof_p", "psrc_p") in dispatched


async def test_expired_lease_row_is_still_reclaimable(env):
    """Pass side of the token guard: real process death never reaches the crash
    handler, so its row must survive for re-claim exactly as before."""
    sessions, seed = env
    await seed(
        parse_status=ParseStatus.PROCESSING,
        token="tok-dead",
        lease=datetime.now(UTC) - timedelta(seconds=1),
    )
    token = await tasks_module.claim_profile_parse("prof_p", "psrc_p")
    assert token is not None and token != "tok-dead"
    row = await _row(sessions)
    assert row.parse_status == ParseStatus.PROCESSING
    assert row.parse_claim_token == token
