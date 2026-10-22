"""Real SQL/render/quality regression; no live model or object-store writes."""
from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.db.base import Base
from jc.models.profile import Profile
from jc.models.resume import ExportJob, ResumeDraft
from jc.models.user import User
from jc.schemas.resume import ExportRequest
from jc.services.profile_service import ProfileService
from jc.services.resume_render_engine import ResumeRenderEngine
from jc.services.resume_service import ResumeService
from jc.stores.resume_store import ResumeStore

# Inlined when the per-format export tests were removed; this is the one fixture
# the lifecycle flow still needs.
FIXTURE_SECTIONS = {
    "locale": "zh-CN",
    "header": {
        "name": "张三",
        "headline": "高级后端工程师",
        "contact_line": "zhangsan@example.com · 13800138000",
    },
    "summary": "5年后端开发经验，熟悉 Python、FastAPI、MySQL、Redis。",
    "experience_blocks": [
        {
            "company": "某互联网公司",
            "title": "高级后端工程师",
            "date_range": "2020-01 – 至今",
            "bullets": ["主导订单服务重构，接口 P99 降低 30%"],
        }
    ],
    "education_blocks": [
        {
            "school": "某大学",
            "degree_line": "计算机科学 · 本科",
            "date_range": "2016 – 2020",
        }
    ],
    "skills_block": {"title": "技能", "content": "Python, FastAPI, MySQL, Redis"},
    # Projects carry multiple bullets, exactly like experience. Keeping this fixture non-empty
    # means every export gate (PDF/HTML/DOCX, text retention, ATS markup) actually exercises the
    # 项目经历 section instead of silently skipping it.
    "project_blocks": [
        {
            "name": "统一配置中心",
            "role": "负责人",
            "date_range": "2021-03 – 2023-08",
            "description": "面向全集团的配置下发平台",
            "bullets": [
                "主导配置中心建设，接入 120+ 服务",
                "推动配置变更事故下降 70%",
            ],
        }
    ],
    "section_order": ["summary", "experience", "projects", "education", "skills"],
}


@pytest.fixture
async def env(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/exports.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=True)
    async with sessions() as db:
        db.add(User(id="u", email="fixture@example.test", password_hash="test"))
        await db.flush()
        db.add(Profile(id="p", user_id="u", owner_kind="user", payload={
            "contact": {"name": "Fixture"}, "summary": "Original text",
        }, version=1))
        await db.flush()
        db.add(ResumeDraft(id="d", profile_id="p", profile_version=1,
            elevation_level="elevated", locale="zh-CN", template_id="zh-one-page",
            sections=FIXTURE_SECTIONS, reviewer_status="failed", reviewer_notes="Keep findings"))
        await db.commit()
    yield SimpleNamespace(sessions=sessions)
    await engine.dispose()


async def run_export(env, monkeypatch, fmt="docx", fault=None, verdict="failed"):
    uploaded = []
    loop_thread = threading.get_ident()
    async with env.sessions() as db:
        draft = await db.get(ResumeDraft, "d")
        draft.reviewer_status = verdict
        await db.commit()
        svc = object.__new__(ResumeService)
        svc._db = db
        svc._profiles = ProfileService(db)
        svc._resumes = ResumeStore(db)
        svc._renderer = ResumeRenderEngine()
        svc._review_draft = AsyncMock(side_effect=AssertionError("No paid calls during exports"))
        original_docx = svc._renderer.render_docx

        def render_docx(sections):
            assert threading.get_ident() != loop_thread
            assert not db.in_transaction(), "DB connection held during rendering"
            return original_docx(sections)
        svc._renderer.render_docx = render_docx

        def put(key, content, **kwargs):
            assert not db.in_transaction(), "DB connection held during upload"
            assert threading.get_ident() != loop_thread
            if fault == "upload":
                raise OSError("private internal storage error")
            uploaded.append((key, content))
        svc._storage = SimpleNamespace(put_object=put)
        if fault == "render":
            def bad_render(_):
                raise ValueError("bad render")
            svc._renderer.render_docx = bad_render
        if fault == "persist":
            async def bad_flush(job, **kwargs):
                # Real IntegrityError makes the session require rollback.
                db.add(ExportJob(id=job.id, user_id="u", profile_id="p", format=fmt))
                await db.flush()
            svc._resumes.mark_export_done = bad_flush
        def sign(key):
            if fault == "download_url":
                raise RuntimeError("private signer error")
            return f"/fixture/{key}"
        monkeypatch.setattr("jc.services.resume_service.download_url_for_key", sign)
        result = await svc.export("p", actor=UserActor(user_id="u", session_id="s"),
                                  body=ExportRequest(draft_id="d", format=fmt))
        svc._review_draft.assert_not_awaited()
    async with env.sessions() as db:
        job = await db.get(ExportJob, result.id)
        draft = await db.get(ResumeDraft, "d")
        assert job.status == result.status
        assert draft.reviewer_status == verdict and draft.reviewer_notes == "Keep findings"
        if fault:
            assert job.status == "failed"
            assert job.error_message.startswith(f"[{fault}]")
            assert "private" not in result.error_message
            assert result.id in result.error_message
            assert result.download_url is None
        else:
            assert job.status == "done" and job.storage_key and result.download_url
            assert uploaded
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", ["html", "docx", "pdf"])
async def test_export_three_real_formats(env, monkeypatch, fmt):
    await run_export(env, monkeypatch, fmt)




@pytest.mark.asyncio
@pytest.mark.parametrize("verdict", ["passed", "failed", "pending"])
async def test_export_preserves_every_review_verdict(env, monkeypatch, verdict):
    await run_export(env, monkeypatch, verdict=verdict)






