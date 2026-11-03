"""Resume versions: grouping by profile, ownership, viewing a version, and deleting one."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401 — registers every table on Base.metadata
from jc.db.base import Base
from jc.exceptions import AppError
from jc.models.job import Job
from jc.models.profile import Profile
from jc.models.resume import ExportJob, ResumeDraft
from jc.models.user import User
from jc.services import resume_version_service as rvs
from jc.services.profile_service import ProfileService
from jc.services.resume_version_service import ResumeVersionService
from test_export_lifecycle import FIXTURE_SECTIONS


class FakeStorage:
    def __init__(self, fail_on: str | None = None) -> None:
        self.deleted: list[str] = []
        self.fail_on = fail_on

    def delete_object(self, key: str) -> None:
        if key == self.fail_on:
            raise OSError("storage unavailable")
        self.deleted.append(key)


@pytest.fixture
async def sessions(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/versions.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def storage(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr(rvs, "get_storage_backend", lambda: fake)
    return fake


async def _seed(sessions):
    async with sessions() as db:
        for uid in ("alice", "bob"):
            db.add(User(id=uid, email=f"{uid}@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(Profile(id="p_alice_1", user_id="alice", owner_kind="user",
                       payload={"contact": {"name": "Fixture"}, "summary": "Text"}, version=1))
        db.add(Profile(id="p_alice_2", user_id="alice", owner_kind="user",
                       payload={"contact": {"name": "Second"}}, version=1))
        db.add(Profile(id="p_bob", user_id="bob", owner_kind="user",
                       payload={"contact": {"name": "Bob"}}, version=1))
        db.add(Job(id="job_1", profile_id="p_alice_1", company="Acme", title="Backend Engineer",
                   raw_text="jd", requirements={}))
        await db.flush()
        db.add(ResumeDraft(id="rdft_a", profile_id="p_alice_1", profile_version=1, job_id="job_1",
                           elevation_level="elevated", locale="zh-CN", template_id="zh-one-page",
                           sections=FIXTURE_SECTIONS, reviewer_status="passed"))
        db.add(ResumeDraft(id="rdft_b", profile_id="p_alice_1", profile_version=1, job_id=None,
                           elevation_level="standard", locale="zh-CN", template_id="zh-one-page",
                           sections=FIXTURE_SECTIONS, reviewer_status="failed"))
        db.add(ResumeDraft(id="rdft_c", profile_id="p_alice_2", profile_version=1, job_id=None,
                           elevation_level="elevated", locale="en-US", template_id="zh-one-page",
                           sections=FIXTURE_SECTIONS, reviewer_status="pending"))
        db.add(ResumeDraft(id="rdft_bob", profile_id="p_bob", profile_version=1, job_id=None,
                           elevation_level="elevated", locale="zh-CN", template_id="zh-one-page",
                           sections=FIXTURE_SECTIONS, reviewer_status="passed"))
        await db.flush()
        now = datetime.now(UTC)
        db.add(ExportJob(id="expj_1", user_id="alice", profile_id="p_alice_1", resume_draft_id="rdft_a",
                         format="pdf", locale="zh-CN", status="done", storage_key="p_alice_1/export/a.pdf",
                         completed_at=now))
        db.add(ExportJob(id="expj_2", user_id="alice", profile_id="p_alice_1", resume_draft_id="rdft_a",
                         format="docx", locale="zh-CN", status="processing"))
        await db.commit()


def _service(db) -> ResumeVersionService:
    return ResumeVersionService(db, ProfileService(db))


@pytest.mark.asyncio
async def test_lists_versions_grouped_by_profile_with_jobs_and_downloads(sessions, storage):
    await _seed(sessions)
    async with sessions() as db:
        data = await _service(db).list_grouped(actor=UserActor(user_id="alice", session_id="s"))

    groups = {g["profile_id"]: g for g in data["groups"]}
    assert set(groups) == {"p_alice_1", "p_alice_2"}, "bob's profile must not appear"
    assert len(groups["p_alice_1"]["versions"]) == 2
    assert len(groups["p_alice_2"]["versions"]) == 1

    a = next(v for v in groups["p_alice_1"]["versions"] if v["id"] == "rdft_a")
    assert a["job"] == {"id": "job_1", "title": "Backend Engineer", "company": "Acme"}
    assert a["reviewer_status"] == "passed"
    by_format = {e["format"]: e for e in a["exports"]}
    assert by_format["pdf"]["download_url"], "a finished export must be downloadable"
    assert by_format["docx"]["download_url"] is None, "a processing export has no file yet"

    b = next(v for v in groups["p_alice_1"]["versions"] if v["id"] == "rdft_b")
    assert b["job"] is None, "a generic version has no job"


@pytest.mark.asyncio
async def test_another_user_cannot_see_view_or_delete_a_version(sessions, storage):
    await _seed(sessions)
    async with sessions() as db:
        bob = await _service(db).list_grouped(actor=UserActor(user_id="bob", session_id="s"))
        assert [g["profile_id"] for g in bob["groups"]] == ["p_bob"]
    async with sessions() as db:
        with pytest.raises(AppError):
            await _service(db).render_html("rdft_a", actor=UserActor(user_id="bob", session_id="s"))
    async with sessions() as db:
        with pytest.raises(AppError):
            await _service(db).delete("rdft_a", actor=UserActor(user_id="bob", session_id="s"))
    assert storage.deleted == [], "a refused delete must not touch stored files"


@pytest.mark.asyncio
async def test_view_renders_the_saved_content_without_a_model(sessions, storage):
    await _seed(sessions)
    async with sessions() as db:
        html = await _service(db).render_html("rdft_a", actor=UserActor(user_id="alice", session_id="s"))
    assert "<html" in html.lower()
    assert "Python, FastAPI, MySQL, Redis" in html, "the saved sections must be what gets rendered"


@pytest.mark.asyncio
async def test_delete_removes_the_version_its_exports_and_their_files(sessions, storage):
    await _seed(sessions)
    async with sessions() as db:
        await _service(db).delete("rdft_a", actor=UserActor(user_id="alice", session_id="s"))
    assert storage.deleted == ["p_alice_1/export/a.pdf"]
    async with sessions() as db:
        assert await db.get(ResumeDraft, "rdft_a") is None
        assert await db.get(ExportJob, "expj_1") is None
        assert await db.get(ExportJob, "expj_2") is None
        assert await db.get(ResumeDraft, "rdft_b") is not None, "other versions are untouched"


@pytest.mark.asyncio
async def test_a_failed_file_delete_keeps_the_version_so_it_can_be_retried(sessions, monkeypatch):
    await _seed(sessions)
    failing = FakeStorage(fail_on="p_alice_1/export/a.pdf")
    monkeypatch.setattr(rvs, "get_storage_backend", lambda: failing)
    async with sessions() as db:
        with pytest.raises(OSError):
            await _service(db).delete("rdft_a", actor=UserActor(user_id="alice", session_id="s"))
    async with sessions() as db:
        assert await db.get(ResumeDraft, "rdft_a") is not None, (
            "the version must stay listed while its stored resume is still present"
        )
