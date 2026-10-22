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
from jc.services.profile_patch_service import propose_patch
from jc.services.resume_draft_builder import ResumeDraftBuilder
from jc.services.resume_elevator import ResumeElevator
from jc.services.resume_service import ResumeService
from test_profile_confirmations import click, env, scope  # noqa: F401

TEXT = "负责 QQ 浏览器关键服务与 CI/CD 工具开发，将交付周期从 25 天缩短至 8 天。"
BASE = {"contact": {"name": "测试"}, "meta": {"source_locale": "zh-CN"},
        "experiences": [{"id": "exp_tencent", "company": "腾讯", "title": "技术负责人",
                         "start_date": "2020-05", "highlights": ["原来的内容", "保留的另一条"]}]}






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

    # No live writer: this test is about the cache decision, and a real gateway call
    # would make it depend on whether that gateway is up. The deterministic builder
    # sets no `generation` key, which is also the "writer switched off" case asserted
    # below.
    from jc.services import resume_elevator as elevator_mod
    monkeypatch.setattr(elevator_mod.settings, "jc_llm_enabled", False)

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




