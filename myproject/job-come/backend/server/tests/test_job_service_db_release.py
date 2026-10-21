"""Slow JD/fit model calls must not hold a pooled MySQL connection."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

_RAW_JD = "后端工程师，要求 Python、FastAPI、MySQL，三年以上经验，负责核心服务研发。"


def _service(**overrides):
    from jc.services.job_service import JobService

    service = object.__new__(JobService)
    service._profiles = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(payload={"contact": {}}, version=1))
    )
    service._jobs = SimpleNamespace(get_by_id=AsyncMock(), create=AsyncMock(), save=AsyncMock())
    service._applications = SimpleNamespace(upsert_evaluated=AsyncMock())
    service._db = SimpleNamespace(rollback=AsyncMock(), commit=AsyncMock())
    for key, value in overrides.items():
        setattr(service, key, value)
    return service


@pytest.mark.asyncio
async def test_parse_jd_releases_db_connection_before_parse():
    from jc.schemas.job import JDParseResult, JobParseRequest

    events: list[str] = []

    async def rollback():
        events.append("rollback")

    async def parse(*, raw_text):
        events.append("parse")
        assert raw_text == _RAW_JD
        return JDParseResult(company="某公司", role_title="后端工程师")

    service = _service(_jd=SimpleNamespace(parse=parse))
    service._db.rollback = rollback

    await service.parse_jd(
        "prof_1",
        actor=SimpleNamespace(),
        body=JobParseRequest(raw_text=_RAW_JD, save=False),
    )

    assert events == ["rollback", "parse"]


@pytest.mark.asyncio
async def test_fit_score_releases_connection_and_reloads_job():
    from jc.schemas.job import FitScoreRequest

    events: list[str] = []

    async def rollback():
        events.append("rollback")

    async def parse(*, raw_text):
        events.append("parse")
        assert raw_text == "后端工程师岗位描述"
        return SimpleNamespace(role_title="后端工程师")

    async def score(*, profile, jd):
        events.append("score")
        from jc.schemas.job import FitScoreResponse

        return FitScoreResponse(
            job_id=None, score=78, recommendation="caution", gaps=[], blockers=[],
            summary="匹配度良好", elevate_hints=[], dimensions={},
        )

    def job_row():
        return SimpleNamespace(
            id="job_1",
            profile_id="prof_1",
            raw_text="后端工程师岗位描述",
            requirements={"role_title": ""},
        )

    stale = job_row()
    fresh = job_row()

    service = _service(
        _jd=SimpleNamespace(parse=parse),
        _fit=SimpleNamespace(score=score),
    )
    service._db.rollback = rollback
    service._jobs.get_by_id = AsyncMock(side_effect=[stale, fresh])

    await service.fit_score(
        "prof_1", actor=SimpleNamespace(), body=FitScoreRequest(job_id="job_1")
    )

    # Connection released before both model calls, and the row written is the re-loaded one.
    assert events == ["rollback", "parse", "score"]
    assert fresh.fit_score == 78
    assert fresh.fit_report["evidence_profile_version"] == 1
    assert not hasattr(stale, "fit_score")
