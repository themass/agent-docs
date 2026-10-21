"""Real review orchestration and SSE; isolated fakes, no DB or model charges."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from jc.schemas.profile_payload import ProfilePayload
from jc.services.resume_service import JobHints, ResumeService


def service_fixture(reviewed=True):
    draft = SimpleNamespace(id="d", profile_id="p", locale="zh-CN", sections={}, job_id=None,
                            reviewer_status=None, reviewer_notes=None)
    svc = object.__new__(ResumeService)
    svc._db = SimpleNamespace(rollback=AsyncMock(), commit=AsyncMock())
    svc._profiles = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(payload=ProfilePayload())))
    svc._job_hints = AsyncMock(return_value=JobHints())
    svc._resumes = SimpleNamespace(get_draft_by_id=AsyncMock(return_value=draft))
    svc._review_draft = AsyncMock(return_value={
        "reviewed": reviewed, "status": "passed" if reviewed else "unavailable",
        "notes": "ok", "issues": [], "can_export": True,
    })
    return svc


async def events_of(stream):
    return [json.loads(chunk.decode()[6:]) async for chunk in stream if chunk.startswith(b"data:")]


@pytest.mark.asyncio
@pytest.mark.parametrize("reviewed", [True, False])
async def test_review_stream_reports_actual_stages_and_honest_verdict(reviewed):
    svc = service_fixture(reviewed)
    stream = await svc.review_events("p", actor=SimpleNamespace(user_id="u"), draft_id="d")
    events = await events_of(stream)
    assert [(e["stage"], e["status"]) for e in events if e["type"] == "progress"] == [
        ("read", "running"), ("read", "done"), ("rules", "running"), ("rules", "done"),
        ("model", "running"), ("model", "done" if reviewed else "unavailable"),
        ("save", "running"), ("save", "done"),
    ]
    assert events[-1]["type"] == "result"
    assert events[-1]["data"]["reviewed"] is reviewed
    svc._db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_review_disconnect_awaits_producer_before_session_close():
    svc = service_fixture()
    entered, stopped = asyncio.Event(), asyncio.Event()

    async def slow(draft):
        entered.set()
        try:
            await asyncio.sleep(10)
        finally:
            stopped.set()

    svc._review_draft = slow
    stream = await svc.review_events("p", actor=SimpleNamespace(user_id="u"), draft_id="d")
    await anext(stream)
    await entered.wait()
    await stream.aclose()
    assert stopped.is_set()
    svc._db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_review_permission_failure_occurs_before_streaming():
    svc = service_fixture()
    svc._profiles.get.side_effect = PermissionError("denied")
    with pytest.raises(PermissionError):
        await svc.review_events("p", actor=SimpleNamespace(user_id="u"), draft_id="d")
    svc._review_draft.assert_not_awaited()


@pytest.mark.asyncio
async def test_review_stream_route_is_sse_with_final_result():
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from agentkit.web.auth import UserActor
    from jc.api.deps import get_resume_service, require_user
    from jc.api.profile_router import router

    svc = service_fixture()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_resume_service] = lambda: svc
    app.dependency_overrides[require_user] = lambda: UserActor(user_id="u", session_id="s")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/profiles/p/export/review/stream?draft_id=d")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    assert '"type": "result"' in response.text
    assert '"stage": "save", "status": "done"' in response.text


@pytest.mark.asyncio
async def test_review_releases_connection_and_timeout_still_finishes_stream(monkeypatch):
    from jc.config import settings

    svc = service_fixture()
    del svc._review_draft  # Exercise the real total-deadline and rule fallback.
    monkeypatch.setattr(settings, "jc_export_review_timeout_seconds", 0.01)
    monkeypatch.setattr("jc.stores.profile_store.ProfileStore", lambda db: SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(payload={"contact": {}}))))
    entered = False

    async def slow(**kwargs):
        nonlocal entered
        entered = True
        # Preflight and model snapshot both release their read-only transaction.
        assert svc._db.rollback.await_count == 2
        await asyncio.sleep(10)

    svc._reviewer = SimpleNamespace(review=slow)
    stream = await svc.review_events("p", actor=SimpleNamespace(user_id="u"), draft_id="d")
    events = await asyncio.wait_for(events_of(stream), 1)
    assert entered
    assert {"stage": "model", "status": "unavailable"}.items() <= events[-4].items()
    assert events[-1]["data"]["status"] == "unavailable"
    assert events[-1]["data"]["can_export"] is True
    svc._db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_bilingual_review_failure_cancels_sibling_call():
    svc = service_fixture()
    entered, stopped = asyncio.Event(), asyncio.Event()

    async def review(*, sections, **kwargs):
        if sections.get("locale") == "zh-CN":
            await entered.wait()
            raise RuntimeError("unexpected reviewer failure")
        entered.set()
        try:
            await asyncio.sleep(10)
        finally:
            stopped.set()

    svc._reviewer = SimpleNamespace(review=review)
    with pytest.raises(ExceptionGroup):
        await svc._review_snapshot("zh-en", {
            "zh_sections": {"locale": "zh-CN"}, "en_sections": {"locale": "en-US"},
        }, {"contact": {}}, "general")
    assert stopped.is_set()
