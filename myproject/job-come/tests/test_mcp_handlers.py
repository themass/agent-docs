"""MCP handler unit tests."""

from __future__ import annotations

import pytest

from jobcome.mcp.registry import SKILL_TOOLS, tools_for_skill
from jobcome.services.patch_confirm_service import create_pending, pop_pending


def test_apply_pipeline_tool_registered() -> None:
    names = {t["function"]["name"] for t in tools_for_skill("apply-pipeline")}
    assert "jobcome_apply_pipeline" in names
    assert "jobcome_fit_score" in names
    assert "jobcome_resume_review" in names


def test_resume_reviewer_skill_has_review_tool() -> None:
    assert "jobcome_resume_review" in SKILL_TOOLS["resume-reviewer"]
    assert "jobcome_resume_review" in SKILL_TOOLS["resume-writer"]


def test_coach_mock_has_answer_save_attempt() -> None:
    assert "jobcome_answer_save_attempt" in SKILL_TOOLS["coach-mock"]
    assert "jobcome_question_upsert" in SKILL_TOOLS["coach-mock"]


@pytest.mark.asyncio
async def test_patch_confirm_roundtrip(monkeypatch) -> None:
    from jobcome.services import patch_confirm_service

    class FakeRedis:
        def __init__(self):
            self.data = {}
        async def set(self, key, value, **kwargs):
            self.data[key] = value
        async def get(self, key):
            return self.data.get(key)
        async def delete(self, key):
            return self.data.pop(key, None)
        async def getdel(self, key):
            return self.data.pop(key, None)

    redis = FakeRedis()
    monkeypatch.setattr(patch_confirm_service, "get_redis", lambda: redis)
    pending = await create_pending(
        session_id="agsn_test",
        user_id="usr_test",
        profile_id="prof_test",
        patch={"summary": "x"},
        preview={"patch_keys": ["summary"]},
    )
    loaded = await pop_pending(pending.confirm_id)
    assert loaded is not None
    assert loaded.patch["summary"] == "x"
    assert await pop_pending(pending.confirm_id) is None
