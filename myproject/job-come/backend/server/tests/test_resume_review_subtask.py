"""The export review: the reviewer is a subtask that records its verdict through tools.

These tests cover the rules around the reviewer (what a verdict must say, what it blocks, what an
unreadable or missing verdict means) and the flow end to end: the service starts the subtask, the
run reads the draft and writes its verdict, and the service reads that verdict back and merges it.
The run is a fake that calls the tools the way the agent does.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.agent import subtask
from jc.authz.scope import RunScope
from jc.db.base import Base
from jc.mcp.handlers import dispatch_tool
from jc.models.enums import ReviewerStatus
from jc.models.profile import Profile
from jc.models.resume import ResumeDraft
from jc.models.user import User
from jc.services import resume_reviewer
from jc.services.resume_reviewer import (
    ReviewerResult,
    aggregate_status,
    blocking_issues,
    build_review_input,
    review_tracks,
    verdict_result,
)
from jc.services.resume_service import ResumeService

SOURCE = {"experiences": [{"title": "后端工程师", "highlights": ["拆分结算表"]}]}
MAIN = {"summary": "后端", "experience_blocks": [{"bullets": ["拆分结算表"]}]}


# ---- the verdict contract and the rule that blocks export -------------------------------------

def test_a_warning_never_blocks_and_an_error_always_does():
    assert blocking_issues([{"severity": "warning", "message": "x"}]) is False
    assert blocking_issues([{"severity": "error", "message": "x"}]) is True
    assert blocking_issues([{"message": "no severity"}]) is True, "unknown severity fails closed"


def test_a_readable_verdict_keeps_its_status_and_summary():
    result = verdict_result({"status": "passed", "issues": [], "summary": "ok"})
    assert result.status == ReviewerStatus.PASSED and result.notes == "ok" and result.available


def test_a_passed_verdict_with_a_blocking_issue_is_failed():
    result = verdict_result({"status": "passed", "issues": [{"severity": "error", "message": "x"}]})
    assert result.status == ReviewerStatus.FAILED


@pytest.mark.parametrize("bad", [
    None, "passed", {"status": "maybe", "issues": []}, {"status": "passed"},
    {"status": "passed", "issues": ["not a dict"]},
])
def test_an_unreadable_verdict_is_no_verdict_not_a_failure(bad):
    result = verdict_result(bad)
    assert result.available is False
    assert result.status == ReviewerStatus.PENDING


def test_no_verdict_on_any_track_leaves_the_draft_pending_not_failed():
    passed = ReviewerResult(status=ReviewerStatus.PASSED, notes=None, issues=[])
    unknown = verdict_result(None)
    assert aggregate_status({"zh": passed, "en": unknown}) == ReviewerStatus.PENDING
    assert aggregate_status({"zh": passed, "en": ReviewerResult(
        status=ReviewerStatus.FAILED, notes=None, issues=[])}) == ReviewerStatus.FAILED
    assert aggregate_status({"zh": passed, "en": passed}) == ReviewerStatus.PASSED


def test_a_stored_verdict_reads_back_as_the_same_result():
    original = ReviewerResult(
        status=ReviewerStatus.FAILED, notes="n", issues=[{"severity": "error"}],
    )
    assert ReviewerResult.from_dict(original.as_dict()) == original


# ---- tracks and the input the reviewer is given ------------------------------------------------

def test_a_bilingual_draft_has_two_tracks_and_a_single_draft_has_one(monkeypatch):
    bilingual = {
        "zh_sections": {"role_family": "backend"}, "en_sections": {"role_family": "backend"},
    }
    assert set(review_tracks("zh-en", bilingual, SOURCE)) == {"zh", "en"}
    assert set(review_tracks("zh-CN", MAIN, SOURCE)) == {"main"}


def test_a_track_without_a_source_profile_is_unavailable_and_never_reviewed(monkeypatch):
    monkeypatch.setattr(resume_reviewer.settings, "jc_llm_enabled", True)
    text, blocked = build_review_input(MAIN, None, "general")
    assert text is None and blocked is not None and blocked.available is False


def test_the_reviewer_is_not_asked_when_the_llm_is_off(monkeypatch):
    monkeypatch.setattr(resume_reviewer.settings, "jc_llm_enabled", False)
    text, blocked = build_review_input(MAIN, SOURCE, "general")
    assert text is None and blocked.issues[0]["code"] == "llm_disabled"


def test_the_reviewer_input_carries_the_playbook_and_no_render_data(monkeypatch):
    monkeypatch.setattr(resume_reviewer.settings, "jc_llm_enabled", True)
    sections = {**MAIN, "contact": {"photo_data_uri": "data:image/png;base64,AAA"}}
    text, blocked = build_review_input(sections, SOURCE, "backend")
    assert blocked is None
    assert "role_playbook" in text and "photo_data_uri" not in text


# ---- the flow: the service starts the subtask, the run writes, the service reads back ----------

class ReviewerRun:
    """One run of the resume-reviewer subtask, calling its tools on its own database session."""

    def __init__(self, maker, *, verdicts: dict[str, Any] | None) -> None:
        self.maker = maker
        self.verdicts = verdicts
        self.runs: list[dict[str, Any]] = []

    async def run_once(self, *, skill, metadata, context, db=None) -> str:
        self.runs.append({"skill": skill, "metadata": metadata, "context": context})
        if self.verdicts is None:
            return ""
        draft_id = metadata.extra["draft_id"]
        async with self.maker() as s:
            scope = RunScope(db=s, user_id=metadata.user_id, profile_id=metadata.profile_id)
            read = await dispatch_tool(scope, "jc_resume_review_read", {"draft_id": draft_id})
            assert set(read["tracks"]) == set(self.verdicts), "the run must see every track"
            async with self.maker() as s2:
                scope2 = RunScope(db=s2, user_id=metadata.user_id, profile_id=metadata.profile_id)
                await dispatch_tool(scope2, "jc_resume_review_write",
                                    {"draft_id": draft_id, "verdicts": self.verdicts})
        return ""


class ReviewerFactory:
    def __init__(self, run: ReviewerRun) -> None:
        self.run = run

    def __call__(self, db=None):
        return self.run


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/review.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await session.flush()
        session.add(Profile(id="p1", user_id="u1", owner_kind="user", payload=SOURCE, version=1))
        await session.commit()
    yield factory
    await engine.dispose()


async def _draft(maker, *, locale: str, sections: dict[str, Any]) -> str:
    async with maker() as s:
        s.add(ResumeDraft(id="d1", profile_id="p1", profile_version=1, locale=locale,
                          template_id="zh-one-page", sections=sections,
                          created_at=datetime.now(UTC)))
        await s.commit()
    return "d1"


def _on(monkeypatch, run: ReviewerRun) -> None:
    monkeypatch.setattr(resume_reviewer.settings, "jc_llm_enabled", True)
    monkeypatch.setattr(subtask, "get_deerflow_client", ReviewerFactory(run))


async def _review(maker, draft_id: str) -> dict[str, Any]:
    async with maker() as s:
        draft = await s.get(ResumeDraft, draft_id)
        return await ResumeService(s)._review_draft(draft)


@pytest.mark.asyncio
async def test_a_passed_verdict_from_the_run_passes_the_export(maker, monkeypatch):
    draft_id = await _draft(maker, locale="zh-CN", sections=MAIN)
    run = ReviewerRun(maker, verdicts={"main": {"status": "passed", "issues": [], "summary": "好"}})
    _on(monkeypatch, run)
    payload = await _review(maker, draft_id)
    assert payload["status"] == "passed" and payload["reviewed"] is True
    assert payload["blocking_issue_count"] == 0
    assert run.runs[0]["skill"] == "resume-reviewer"
    assert run.runs[0]["metadata"].extra == {"draft_id": draft_id}


@pytest.mark.asyncio
async def test_a_failed_verdict_blocks_the_export_and_is_stored_on_the_draft(maker, monkeypatch):
    draft_id = await _draft(maker, locale="zh-CN", sections=MAIN)
    issue = {"severity": "error", "field": "experience_blocks[0].bullets[0]", "message": "不实"}
    _on(monkeypatch, ReviewerRun(maker, verdicts={"main": {"status": "failed", "issues": [issue]}}))
    payload = await _review(maker, draft_id)
    assert payload["status"] == "failed" and payload["reviewed"] is True
    assert payload["blocking_issue_count"] == 1
    async with maker() as s:
        stored = (
            await s.execute(select(ResumeDraft).where(ResumeDraft.id == draft_id))
        ).scalar_one()
    assert stored.reviewer_status == "failed"
    assert stored.reviewer_verdicts["main"]["status"] == "failed"


@pytest.mark.asyncio
async def test_a_run_that_writes_no_verdict_is_unavailable_and_blocks_nothing(maker, monkeypatch):
    draft_id = await _draft(maker, locale="zh-CN", sections=MAIN)
    _on(monkeypatch, ReviewerRun(maker, verdicts=None))
    payload = await _review(maker, draft_id)
    assert payload["status"] == "unavailable" and payload["reviewed"] is False
    assert payload["blocking_issue_count"] == 0
    assert any(i["code"] == "reviewer_no_verdict" for i in payload["issues"])


@pytest.mark.asyncio
async def test_a_bilingual_draft_needs_a_verdict_for_each_track(maker, monkeypatch):
    sections = {
        "zh_sections": MAIN, "en_sections": MAIN, "track": "bilingual", "role_family": "backend",
    }
    draft_id = await _draft(maker, locale="zh-en", sections=sections)
    run = ReviewerRun(maker, verdicts={
        "zh": {"status": "passed", "issues": []},
        "en": {"status": "failed", "issues": [{"severity": "error", "message": "x"}]},
    })
    _on(monkeypatch, run)
    payload = await _review(maker, draft_id)
    assert payload["status"] == "failed" and payload["reviewed"] is True


@pytest.mark.asyncio
async def test_a_write_that_leaves_a_track_out_is_refused(maker, monkeypatch):
    sections = {
        "zh_sections": MAIN, "en_sections": MAIN, "track": "bilingual", "role_family": "backend",
    }
    draft_id = await _draft(maker, locale="zh-en", sections=sections)
    async with maker() as s:
        scope = RunScope(db=s, user_id="u1", profile_id="p1")
        with pytest.raises(ValueError, match="cover exactly"):
            await dispatch_tool(scope, "jc_resume_review_write",
                                {"draft_id": draft_id, "verdicts": {"zh": {"status": "passed",
                                                                          "issues": []}}})


@pytest.mark.asyncio
async def test_a_draft_outside_the_profile_is_not_readable_by_the_reviewer(maker):
    await _draft(maker, locale="zh-CN", sections=MAIN)
    async with maker() as s:
        scope = RunScope(db=s, user_id="u2", profile_id="p2")
        with pytest.raises((PermissionError, LookupError, ValueError)):
            await dispatch_tool(scope, "jc_resume_review_read", {"draft_id": "d1"})
