"""Deterministic preview/confirmation/stream regression; no real model calls."""
from __future__ import annotations

import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agentkit.web.auth import UserActor

from jc.models.profile import Profile
from jc.models.resume import ResumeDraft
from jc.schemas.profile_payload import ProfilePayload
from jc.services.approved_resume_text import confirmed_fields, preserve_confirmed
from jc.services.preview_progress import report, stream_preview
from jc.services.profile_patch_service import propose_patch
from jc.services.resume_draft_builder import ResumeDraftBuilder
from jc.services.resume_elevator import ResumeElevator
from jc.services.resume_service import ResumeService
from test_profile_confirmations import env, click, scope  # noqa: F401

TEXT = "负责 QQ 浏览器关键服务与 CI/CD 工具开发，将交付周期从 25 天缩短至 8 天。"
BASE = {"contact": {"name": "测试"}, "meta": {"source_locale": "zh-CN"},
        "experiences": [{"id": "exp_tencent", "company": "腾讯", "title": "技术负责人",
                         "start_date": "2020-05", "highlights": ["原来的内容", "保留的另一条"]}]}


def test_confirmed_fields_use_applied_values_not_obsolete_proposals():
    p = ProfilePayload.model_validate(BASE)
    p.experiences[0].highlights[0] = TEXT
    patch = {"experiences[0].highlights[0]": TEXT}
    assert confirmed_fields(p, [patch]) == {"experiences/exp_tencent": ["highlights"]}
    p.experiences[0].highlights[0] = "后来手动修改"
    assert confirmed_fields(p, [patch]) == {}


def test_confirmed_nested_array_and_summary_are_supported_without_source_mutation():
    p = ProfilePayload.model_validate(BASE)
    p.meta.approved_resume_fields = confirmed_fields(p, [{"experiences": BASE["experiences"]}])
    sections = {"locale": "zh-CN", "experience_blocks": [
        {"id": "exp_tencent", "company": "腾讯", "bullets": ["再次被模型改写"]}]}
    original = copy.deepcopy(sections)
    out = preserve_confirmed(sections, p)
    assert out["experience_blocks"][0]["bullets"] == p.experiences[0].highlights
    assert sections == original
    english = dict(sections, locale="en-US")
    assert preserve_confirmed(english, p) == english


@pytest.mark.asyncio
async def test_click_persists_exact_text_and_generated_preview_and_draft_keep_it(env, monkeypatch):
    from jc.services import resume_elevator as mod
    async with env.sessions() as db:
        p = await db.get(Profile, "prof_owned")
        p.payload = BASE
        await db.commit()
        proposal = await propose_patch(scope(db), {"experiences[0].highlights[0]": TEXT})
    response = await click(env, proposal["confirm_id"])
    assert response.status_code == 200, response.text
    model_sections = {"header": {"name": "测试"}, "experience_blocks": [
        {"id": "exp_tencent", "company": "腾讯", "title": "技术负责人", "bullets": ["模型把它改掉了"]}]}
    router = SimpleNamespace(acompletion=AsyncMock(return_value=model_sections))
    monkeypatch.setattr(mod, "get_llm_router", lambda: router)
    monkeypatch.setattr(mod.settings, "jc_llm_enabled", True)
    # This fixture is a minimal draft, so the repair pass would legitimately fire on it.
    # Off here: the subject is that a confirmed sentence survives generation verbatim,
    # and a second writer call would make the single-call assertion below measure the
    # repair instead. Repair acceptance has its own tests.
    monkeypatch.setattr(mod.settings, "jc_preview_repair_enabled", False)
    async with env.sessions() as db:
        svc = ResumeService(db)
        result = await svc.preview("prof_owned", actor=UserActor(user_id="usr_owner", session_id="auth_test"),
                                   elevation_level="standard", locale="zh-CN", force=True)
        assert TEXT in result.html
        assert result.draft.sections["experience_blocks"][0]["bullets"] == [TEXT, "保留的另一条"]
        saved = await db.get(ResumeDraft, result.draft.id)
        assert saved.sections["experience_blocks"][0]["bullets"] == [TEXT, "保留的另一条"]
        assert (await db.get(Profile, "prof_owned")).payload["experiences"][0]["highlights"][0] == TEXT
        assert result.draft.profile_version == response.json()["version"]
    router.acompletion.assert_awaited_once()


def test_confirmed_title_and_scope_survive_a_writer_that_normalizes_them():
    """A confirmed identity field is the user's wording, not display text.

    The writer returning a canonical job title is the same silent overwrite the
    highlight locks exist to prevent: the archive keeps the edit, the document does not.
    """
    source = copy.deepcopy(BASE)
    source["experiences"][0].update(title="技术负责人｜带 7 人团队", scope="带 7 人团队，负责交付链路")
    p = ProfilePayload.model_validate(source)
    patch = {
        "experiences[0].title": "技术负责人｜带 7 人团队",
        "experiences[0].scope": "带 7 人团队，负责交付链路",
    }
    assert confirmed_fields(p, [patch]) == {"experiences/exp_tencent": ["scope", "title"]}
    p.meta.approved_resume_fields = confirmed_fields(p, [patch])
    out = preserve_confirmed(
        {"locale": "zh-CN", "experience_blocks": [
            {"id": "exp_tencent", "company": "腾讯", "title": "技术负责人",
             "scope_line": None, "bullets": []}]},
        p,
    )
    assert out["experience_blocks"][0]["title"] == "技术负责人｜带 7 人团队"
    assert out["experience_blocks"][0]["scope_line"] == "带 7 人团队，负责交付链路"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scope,written,expected",
    [
        # A user-authored scope survives a writer that returned null: `null` means "the
        # source carries no scope fact", and when the user typed one it plainly does.
        # That line is the only place team size lives.
        ("带 7 人团队，负责交付链路", None, "带 7 人团队，负责交付链路"),
        # A line the writer actually wrote is never overwritten.
        ("带 7 人团队，负责交付链路", "带 7 人团队，负责订单与结算两条主链路",
         "带 7 人团队，负责订单与结算两条主链路"),
        # With no stated scope the line stays empty rather than restating the heading.
        # `在{company}担任{title}` sits under a heading that already says exactly that:
        # it occupies the one line a reader uses to size the role while adding no fact.
        (None, None, None),
    ],
)
async def test_the_scope_line_is_restored_only_from_what_the_user_stated(
    monkeypatch, scope, written, expected
):
    from jc.services import resume_elevator as mod
    source = copy.deepcopy(BASE)
    source["experiences"][0]["scope"] = scope
    model_sections = {"header": {"name": "测试"}, "experience_blocks": [
        {"id": "exp_tencent", "company": "腾讯", "title": "技术负责人",
         "scope_line": written, "bullets": ["原来的内容", "保留的另一条"]}]}
    monkeypatch.setattr(mod, "get_llm_router", lambda: SimpleNamespace(
        acompletion=AsyncMock(return_value=model_sections)))
    monkeypatch.setattr(mod.settings, "jc_llm_enabled", True)
    monkeypatch.setattr(mod.settings, "jc_preview_repair_enabled", False)
    payload = ProfilePayload.model_validate(source)
    sections, _ = await ResumeElevator().build_sections(payload, elevation_level="standard")
    assert sections["experience_blocks"][0]["scope_line"] == expected
    if scope is None:
        # The deterministic builder must agree: it is where the tautology came from.
        builder, _ = ResumeDraftBuilder().build(payload, elevation_level="conservative")
        assert builder["experience_blocks"][0]["scope_line"] is None


@pytest.mark.asyncio
async def test_writer_attempt_budget_leaves_room_for_the_fallback_models(monkeypatch):
    """A slow primary must not consume the whole chain's budget.

    `routing.yaml` gives each writer endpoint 180s while the total budget is 90s, so
    without a per-attempt share the first model alone exhausts the deadline and the
    two fallbacks are never asked — a three-model chain behaving as a one-model chain
    precisely when the primary is unhealthy.
    """
    from jc.services import resume_elevator as mod
    seen = {}

    async def capture(*args, **kwargs):
        seen.update(kwargs)
        return {"header": {"name": "测试"}, "experience_blocks": [
            {"id": "exp_tencent", "company": "腾讯", "title": "技术负责人",
             "bullets": ["原来的内容", "保留的另一条"]}]}

    monkeypatch.setattr(mod, "get_llm_router", lambda: SimpleNamespace(
        acompletion=capture, chain_for=lambda _: [object()] * 3))
    monkeypatch.setattr(mod.settings, "jc_llm_enabled", True)
    monkeypatch.setattr(mod.settings, "jc_preview_writer_timeout_seconds", 90)
    # The repair pass has its own budget and would overwrite `seen` with it.
    monkeypatch.setattr(mod.settings, "jc_preview_repair_enabled", False)
    await ResumeElevator().build_sections(
        ProfilePayload.model_validate(BASE), elevation_level="standard")
    assert seen["timeout_seconds"] == pytest.approx(90 / 3.5)
    assert seen["timeout_seconds"] * 3 < 90


@pytest.mark.asyncio
async def test_writer_chain_timeout_has_visible_source_layout_fallback(monkeypatch):
    from jc.services import resume_elevator as mod
    stopped = asyncio.Event()
    async def hang(*args, **kwargs):
        try:
            await asyncio.sleep(10)
        finally:
            stopped.set()
    monkeypatch.setattr(mod, "get_llm_router", lambda: SimpleNamespace(acompletion=hang))
    monkeypatch.setattr(mod.settings, "jc_llm_enabled", True)
    monkeypatch.setattr(mod.settings, "jc_preview_writer_timeout_seconds", 0.01)
    p = ProfilePayload.model_validate(BASE)
    p.meta.approved_resume_fields = {"experiences/exp_tencent": ["highlights"]}
    sections, _ = await ResumeElevator().build_sections(p, elevation_level="standard")
    assert stopped.is_set()
    assert sections["generation"]["mode"] == "source_layout"
    assert "AI 写作未完成" in sections["generation"]["warning"]
    assert sections["experience_blocks"][0]["bullets"] == BASE["experiences"][0]["highlights"]
    # The fallback warning promises source wording, even for unconfirmed bullets.
    p.meta.approved_resume_fields = {}
    p.experiences[0].highlights = ["参与系统升级相关工作"]
    fallback, _ = await ResumeElevator().build_sections(p, elevation_level="elevated")
    assert fallback["experience_blocks"][0]["bullets"] == ["参与系统升级相关工作"]


def decode(chunks):
    return [json.loads(chunk.decode().split("data: ")[1]) for chunk in chunks if chunk.startswith(b"data:")]


@pytest.mark.asyncio
async def test_real_progress_and_heartbeat_do_not_mark_waiting_steps_done():
    async def preview(*args, **kwargs):
        report("read", done=True)
        report("generate")
        await asyncio.sleep(.025)
        report("generate", done=True)
        return SimpleNamespace(model_dump=lambda **kw: {"html": "ready"})
    svc = SimpleNamespace(preview=preview, _db=SimpleNamespace(rollback=AsyncMock()))
    chunks = [c async for c in stream_preview(svc, "p", heartbeat_seconds=.005)]
    assert any(c.startswith(b": heartbeat") for c in chunks)
    events = decode(chunks)
    assert [e for e in events if e["type"] == "progress"] == [
        {"type": "progress", "stage": "read", "status": "done", "message": None},
        {"type": "progress", "stage": "generate", "status": "running", "message": None},
        {"type": "progress", "stage": "generate", "status": "done", "message": None}]
    assert events[-1] == {"type": "result", "data": {"html": "ready"}}


@pytest.mark.asyncio
async def test_request_deadline_cancels_task_and_rolls_back():
    stopped = asyncio.Event()
    async def preview(*args, **kwargs):
        try:
            await asyncio.sleep(10)
        finally:
            stopped.set()
    svc = SimpleNamespace(preview=preview, _db=SimpleNamespace(rollback=AsyncMock()))
    events = decode([c async for c in stream_preview(svc, "p", timeout_seconds=.01)])
    assert stopped.is_set()
    assert events[-1]["code"] == "preview_timeout"
    svc._db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_disconnect_cancels_task_before_session_cleanup():
    stopped = asyncio.Event()
    entered = asyncio.Event()
    async def preview(*args, **kwargs):
        entered.set()
        try:
            await asyncio.sleep(10)
        finally:
            stopped.set()
    svc = SimpleNamespace(preview=preview)
    stream = stream_preview(svc, "p")
    await anext(stream)
    await entered.wait()
    await stream.aclose()
    assert stopped.is_set()


@pytest.mark.asyncio
async def test_broken_rollback_still_returns_terminal_error():
    async def preview(*args, **kwargs):
        raise RuntimeError("private internal DB failure")
    svc = SimpleNamespace(preview=preview, _db=SimpleNamespace(rollback=AsyncMock(side_effect=RuntimeError("socket gone"))))
    events = decode([c async for c in stream_preview(svc, "p")])
    assert events[-1]["type"] == "error"
    assert "private" not in events[-1]["message"]


@pytest.mark.asyncio
async def test_http_stream_contract_and_ownership_before_headers(env, monkeypatch):
    import httpx
    from fastapi import FastAPI
    from jc.api.profile_router import router
    from jc.api.deps import get_actor, get_resume_service
    from jc.api.auth_router import register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_actor] = lambda: UserActor(user_id="usr_owner", session_id="auth")
    async def service():
        async with env.sessions() as db:
            yield ResumeService(db)
    app.dependency_overrides[get_resume_service] = service
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
        missing = await client.get("/api/v1/profiles/missing/elevate/preview/stream")
        # The existing global AppError handler intentionally maps domain errors to 400.
        assert missing.status_code == 400
        assert missing.json()["code"] == "profile_not_found"
        # Use local deterministic writer only, never invoke paid APIs. The endpoint must
        # still emit the real progress stream and a terminal result for an owned profile.
        from jc.services import resume_elevator as elevator_mod
        monkeypatch.setattr(elevator_mod.settings, "jc_llm_enabled", False)
        response = await client.get(
            "/api/v1/profiles/prof_owned/elevate/preview/stream",
            params={"elevation_level": "standard", "force": "true"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = [json.loads(line[6:]) for line in response.text.splitlines()
                  if line.startswith("data: ")]
        assert [e["stage"] for e in events if e["type"] == "progress"] == [
            "read", "read", "generate", "generate", "save", "save", "render", "render", "audit", "audit"
        ]
        assert events[-1]["type"] == "result"


@pytest.mark.asyncio
async def test_cache_preview_repairs_legacy_rewritten_text_in_storage(env, monkeypatch):
    from jc.services import resume_elevator as mod
    monkeypatch.setattr(mod.settings, "jc_llm_enabled", False)
    async with env.sessions() as db:
        p = await db.get(Profile, "prof_owned")
        p.payload = BASE
        await db.commit()
        proposal = await propose_patch(scope(db), {"experiences[0].highlights[0]": TEXT})
    assert (await click(env, proposal["confirm_id"])).status_code == 200
    actor = UserActor(user_id="usr_owner", session_id="auth")
    async with env.sessions() as db:
        svc = ResumeService(db)
        first = await svc.preview("prof_owned", actor=actor, elevation_level="standard")
        row = await db.get(ResumeDraft, first.draft.id)
        old = copy.deepcopy(row.sections)
        old["experience_blocks"][0]["bullets"] = ["旧写手覆盖了已确认的文字"]
        row.sections = old
        await db.commit()
    async with env.sessions() as db:
        svc = ResumeService(db)
        svc._elevator.build_sections = AsyncMock(side_effect=AssertionError("cached preview must not call model"))
        result = await svc.preview("prof_owned", actor=actor, elevation_level="standard")
        assert TEXT in result.html
        row = await db.get(ResumeDraft, result.draft.id)
        assert row.sections["experience_blocks"][0]["bullets"] == [TEXT, "保留的另一条"]


def test_bilingual_cached_preview_repairs_source_without_overwriting_translation():
    p = ProfilePayload.model_validate(BASE)
    p.experiences[0].highlights[0] = TEXT
    p.meta.approved_resume_fields = {"experiences/exp_tencent": ["highlights"]}
    sections = {"track": "bilingual", "zh_sections": {
        "locale": "zh-CN", "experience_blocks": [{"id": "exp_tencent", "bullets": ["旧中文"]}]},
        "en_sections": {"locale": "en-US", "experience_blocks": [
            {"id": "exp_tencent", "bullets": ["Approved translation"]}]}}
    svc = object.__new__(ResumeService)
    result = svc._normalize_sections(sections, p, locale="bilingual")
    assert result["zh_sections"]["experience_blocks"][0]["bullets"] == [TEXT, "保留的另一条"]
    assert result["en_sections"]["experience_blocks"][0]["bullets"] == ["Approved translation"]
    assert sections["zh_sections"]["experience_blocks"][0]["bullets"] == ["旧中文"]


@pytest.mark.asyncio
async def test_profile_changed_while_writer_runs_rejects_stale_draft(env):
    from sqlalchemy import func, select
    from jc.exceptions import ConflictError

    async def writer(*args, **kwargs):
        async with env.sessions() as other:
            row = await other.get(Profile, "prof_owned")
            row.version += 1
            row.payload = {"contact": {"name": "更新后的姓名"}}
            await other.commit()
        return {"experience_blocks": []}, []

    async with env.sessions() as db:
        svc = ResumeService(db)
        svc._elevator.build_sections = writer
        with pytest.raises(ConflictError) as error:
            await svc.preview("prof_owned", actor=UserActor(user_id="usr_owner", session_id="auth"),
                              elevation_level="standard", force=True)
        assert error.value.code == "preview_profile_changed"
        assert await db.scalar(select(func.count()).select_from(ResumeDraft)) == 0


@pytest.mark.asyncio
async def test_preview_logs_stage_wait_and_completion_without_resume_payload(caplog):
    import logging
    async def preview(*args, **kwargs):
        report("generate", message="PRIVATE_RESUME_TEXT")
        await asyncio.sleep(.025)
        return SimpleNamespace(model_dump=lambda **kw: {"html": "PRIVATE_HTML"})
    svc = SimpleNamespace(preview=preview)
    with caplog.at_level(logging.INFO, logger="jc.services.preview_progress"):
        events = decode([c async for c in stream_preview(svc, "fixture", heartbeat_seconds=.01)])
    assert events[-1]["type"] == "result"
    assert "event=started" in caplog.text
    assert "event=stage" in caplog.text and "stage=generate" in caplog.text
    assert "event=waiting" in caplog.text
    assert "event=finished" in caplog.text and "status=success" in caplog.text
    assert "run_id=" in caplog.text and "elapsed_ms=" in caplog.text
    assert "PRIVATE_RESUME_TEXT" not in caplog.text and "PRIVATE_HTML" not in caplog.text


@pytest.mark.asyncio
async def test_anyio_disconnect_waits_for_async_producer_cleanup():
    """Starlette disconnect cancels an AnyIO scope, not just one asyncio await."""
    import anyio
    entered = asyncio.Event()
    stopped = asyncio.Event()
    cleanup_interrupted = asyncio.Event()

    async def preview(*args, **kwargs):
        entered.set()
        try:
            await asyncio.sleep(60)
        finally:
            try:
                # Represents driver's asynchronous connection-acquisition cleanup.
                await asyncio.sleep(.02)
                stopped.set()
            except asyncio.CancelledError:
                cleanup_interrupted.set()
                raise

    stream = stream_preview(SimpleNamespace(preview=preview), "p")
    await anext(stream)
    await entered.wait()
    with anyio.CancelScope() as scope:
        scope.cancel()
        await stream.aclose()
    await asyncio.sleep(.03)
    assert stopped.is_set(), "Dependency cleanup must not race the DB producer"
    assert not cleanup_interrupted.is_set()


@pytest.mark.asyncio
async def test_streaming_response_disconnect_finishes_producer_before_db_dependency():
    from fastapi import Depends, FastAPI
    from jc.api.sse import ClosingStreamingResponse as StreamingResponse

    entered = asyncio.Event()
    stopped = asyncio.Event()
    order = []
    app = FastAPI()

    async def db_dependency():
        try:
            yield object()
        finally:
            order.append("session_close")
            assert stopped.is_set(), "session closed while producer still owns its connection"

    @app.get("/preview")
    async def preview_route(db=Depends(db_dependency)):
        async def preview(*args, **kwargs):
            entered.set()
            try:
                await asyncio.sleep(60)
            finally:
                await asyncio.sleep(.02)
                order.append("producer_stopped")
                stopped.set()
        return StreamingResponse(stream_preview(SimpleNamespace(preview=preview), "p"))

    async def receive():
        await entered.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        pass

    await app({"type": "http", "asgi": {"version": "3.0", "spec_version": "2.0"},
               "method": "GET", "scheme": "http", "path": "/preview", "raw_path": b"/preview",
               "query_string": b"", "headers": [], "server": ("test", 80), "client": ("test", 1),
               "root_path": "", "http_version": "1.1"}, receive, send)
    assert order == ["producer_stopped", "session_close"]


@pytest.mark.asyncio
async def test_unchanged_preview_reuses_draft_force_and_profile_change_regenerate(env, monkeypatch, caplog):
    import logging
    from jc.services import resume_elevator as mod
    monkeypatch.setattr(mod.settings, "jc_llm_enabled", False)
    actor = UserActor(user_id="usr_owner", session_id="auth")
    async with env.sessions() as db:
        svc = ResumeService(db)
        writer = AsyncMock(wraps=svc._elevator.build_sections)
        svc._elevator.build_sections = writer
        with caplog.at_level(logging.INFO, logger="jc.services.resume_service"):
            first = await svc.preview("prof_owned", actor=actor, elevation_level="standard")
            again = await svc.preview("prof_owned", actor=actor, elevation_level="standard")
        assert again.draft.id == first.draft.id
        assert writer.await_count == 1
        assert "reason=hit" in caplog.text
        forced = await svc.preview("prof_owned", actor=actor, elevation_level="standard", force=True)
        assert forced.draft.id != first.draft.id
        p = await db.get(Profile, "prof_owned")
        p.version += 1
        await db.commit()
        changed = await svc.preview("prof_owned", actor=actor, elevation_level="standard")
        assert changed.draft.id != forced.draft.id
        assert writer.await_count == 3


@pytest.mark.asyncio
async def test_a_writer_failure_is_never_served_from_cache(env, monkeypatch):
    """`source_layout` is a record that the writer was down, not a draft of this profile.

    Caching it means one transient gateway failure makes the profile's own wording the
    permanent "optimized" resume: the user reopens the preview, gets the identical
    unoptimized document, and concludes the optimizer does nothing. `structure_guarded`
    is excluded — there the writer did run, so a retry costs a call without being more
    likely to succeed. A draft generated with the writer switched off carries no
    `generation` key at all and must stay cacheable, or such a deployment would
    regenerate on every preview forever.
    """
    from jc.services.resume_service import ResumeService

    failed = SimpleNamespace(
        sections={"generation": {"mode": "source_layout"}, "role_family": "backend"},
        profile_version=1, template_id="zh-one-page", job_id=None,
    )
    assert ResumeService._writer_failed(failed.sections) is True
    assert ResumeService._writer_failed({"generation": {"mode": "structure_guarded"}}) is False
    assert ResumeService._writer_failed({"role_family": "backend"}) is False

    actor = UserActor(user_id="usr_owner", session_id="auth")
    async with env.sessions() as db:
        svc = ResumeService(db)
        # A real stored draft: the staleness check must reject it even though the
        # profile version matches exactly.
        fresh = await svc.preview("prof_owned", actor=actor, elevation_level="standard")
        stored = await db.get(ResumeDraft, fresh.draft.id)
        assert await svc._is_stale_for_profile(
            stored, profile_id="prof_owned", actor=actor
        ) is False
        stored.sections = {**stored.sections, "generation": {"mode": "source_layout"}}
        await db.commit()
        assert await svc._is_stale_for_profile(
            stored, profile_id="prof_owned", actor=actor
        ) is True


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", ["zh-CN", "en-US", "bilingual"])
async def test_job_preview_cache_is_scoped_and_job_hint_changes_invalidate(env, monkeypatch, locale):
    from jc.models.job import Job
    from jc.services.resume_service import JobHints
    from jc.services import resume_elevator as mod
    monkeypatch.setattr(mod.settings, "jc_llm_enabled", False)
    actor = UserActor(user_id="usr_owner", session_id="auth")
    async with env.sessions() as db:
        db.add(Job(id="job_cache", profile_id="prof_owned", title="工程师", company="测试", raw_text="测试岗位"))
        await db.commit()
        svc = ResumeService(db)
        svc._job_hints = AsyncMock(return_value=JobHints(title="工程师"))
        generic = await svc.preview("prof_owned", actor=actor, elevation_level="standard", locale=locale)
        targeted = await svc.preview("prof_owned", actor=actor, elevation_level="standard", job_id="job_cache", locale=locale)
        assert targeted.draft.id != generic.draft.id
        svc._elevator.build_sections = AsyncMock(side_effect=AssertionError("unchanged cache must not write"))
        same = await svc.preview("prof_owned", actor=actor, elevation_level="standard", job_id="job_cache", locale=locale)
        generic_again = await svc.preview("prof_owned", actor=actor, elevation_level="standard", locale=locale)
        assert same.draft.id == targeted.draft.id
        assert generic_again.draft.id == generic.draft.id
        svc._job_hints.return_value = JobHints(title="工程师", keywords=["新增岗位要求"])
        draft_id = targeted.draft.sections["zh_draft_id"] if locale == "bilingual" else targeted.draft.id
        row = await db.get(ResumeDraft, draft_id)
        assert await svc._is_stale_for_profile(row, profile_id="prof_owned", actor=actor)


@pytest.mark.asyncio
async def test_send_failure_closes_preview_iterator_before_session_cleanup():
    from fastapi import Depends, FastAPI
    from starlette.requests import ClientDisconnect
    from jc.api.sse import ClosingStreamingResponse as StreamingResponse

    entered = asyncio.Event()
    stopped = asyncio.Event()
    app = FastAPI()
    order = []

    async def dependency():
        try:
            yield object()
        finally:
            order.append("session_close")
            assert stopped.is_set(), "send failure abandoned the producer"

    @app.get("/preview")
    async def route(db=Depends(dependency)):
        async def preview(*args, **kwargs):
            entered.set()
            try:
                await asyncio.sleep(60)
            finally:
                await asyncio.sleep(.01)
                stopped.set()
                order.append("producer_stopped")
        return StreamingResponse(stream_preview(SimpleNamespace(preview=preview), "p"))

    async def receive():
        await asyncio.sleep(60)

    async def send(message):
        if message["type"] == "http.response.body":
            await entered.wait()
            raise OSError("socket disconnected during write")

    try:
        with pytest.raises(ClientDisconnect):
            await app({"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
                       "method": "GET", "scheme": "http", "path": "/preview", "raw_path": b"/preview",
                       "query_string": b"", "headers": [], "server": ("test", 80), "client": ("test", 1),
                       "root_path": "", "http_version": "1.1"}, receive, send)
        assert order == ["producer_stopped", "session_close"]
    finally:
        # Avoid leaving the producer alive when demonstrating the pre-fix failure.
        for task in asyncio.all_tasks():
            if task.get_coro().__qualname__.endswith("stream_preview.<locals>.produce"):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
