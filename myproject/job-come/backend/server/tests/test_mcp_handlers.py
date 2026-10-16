"""MCP handler unit tests."""

from __future__ import annotations

import pytest

from jc.mcp.registry import SKILL_TOOLS, tools_for_skill
from jc.services.patch_confirm_service import create_pending, pop_pending


def test_apply_pipeline_tool_registered() -> None:
    names = {t["function"]["name"] for t in tools_for_skill("apply-pipeline")}
    assert "jc_apply_pipeline" in names
    assert "jc_fit_score" in names
    assert "jc_resume_review" in names


def test_resume_reviewer_skill_has_review_tool() -> None:
    assert "jc_resume_review" in SKILL_TOOLS["resume-reviewer"]
    assert "jc_resume_review" in SKILL_TOOLS["resume-writer"]


def test_coach_mock_has_answer_save_attempt() -> None:
    assert "jc_answer_save_attempt" in SKILL_TOOLS["coach-mock"]
    assert "jc_question_upsert" in SKILL_TOOLS["coach-mock"]


@pytest.mark.asyncio
async def test_patch_confirm_roundtrip(monkeypatch) -> None:
    from jc.services import patch_confirm_service

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
