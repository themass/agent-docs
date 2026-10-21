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
from test_export_pdf import FIXTURE_SECTIONS


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
@pytest.mark.parametrize("fault", ["render", "upload", "download_url", "persist"])
async def test_export_failure_survives_rollback(env, monkeypatch, fault):
    await run_export(env, monkeypatch, fault=fault)


@pytest.mark.asyncio
@pytest.mark.parametrize("verdict", ["passed", "failed", "pending"])
async def test_export_preserves_every_review_verdict(env, monkeypatch, verdict):
    await run_export(env, monkeypatch, verdict=verdict)


@pytest.mark.asyncio
async def test_pdf_render_failure_never_uploads_html(env, monkeypatch):
    def bad_pdf(self, html):
        raise RuntimeError("PDF unavailable")
    monkeypatch.setattr(ResumeRenderEngine, "render_pdf", bad_pdf)
    await run_export(env, monkeypatch, fmt="pdf", fault="render")


@pytest.mark.asyncio
async def test_review_explicit_missing_draft_never_falls_back(env):
    from jc.exceptions import NotFoundError
    async with env.sessions() as db:
        svc = ResumeService(db)
        with pytest.raises(NotFoundError, match="没找到"):
            await svc.review_for_export("p", actor=UserActor(user_id="u", session_id="s"),
                                        draft_id="missing")


def test_message_columns_support_large_utf8_replies_and_confirmations():
    from sqlalchemy.dialects import mysql

    from jc.models.agent_message import AgentMessage
    for name in ("content", "payload_json"):
        column_type = AgentMessage.__table__.c[name].type.compile(dialect=mysql.dialect())
        assert str(column_type) == "LONGTEXT"
