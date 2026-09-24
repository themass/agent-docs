"""Regression fixture smoke tests."""

import json
from pathlib import Path

import pytest

from jobcome.coach.feedback import DIMENSION_KEYS, normalize_coach_feedback
from jobcome.services.jd_parser_service import JdParserService
from jobcome.services.profile_ingest_service import ProfileIngestService

_ASSETS = Path(__file__).resolve().parent / "regression_assets"
_RESUMES = _ASSETS / "resumes"
_JDS = _ASSETS / "jds"
_MOCK = _ASSETS / "mock"


def _list_resumes() -> list[Path]:
    return sorted(_RESUMES.glob("*.txt"))


def _list_jds() -> list[Path]:
    return sorted(_JDS.glob("jd_*.txt"))


def test_regression_fixture_inventory() -> None:
    assert len(_list_resumes()) >= 5
    assert len(_list_jds()) >= 10


@pytest.mark.asyncio
async def test_all_jd_fixtures_heuristic_parse() -> None:
    for path in _list_jds():
        text = path.read_text(encoding="utf-8")
        result = JdParserService._heuristic_parse(text)
        assert result.role_title, f"missing title for {path.name}"


@pytest.mark.asyncio
async def test_all_resume_fixtures_ingest_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "jobcome.services.profile_ingest_service.settings.job_come_llm_enabled",
        False,
    )
    service = ProfileIngestService()
    for path in _list_resumes():
        raw = path.read_bytes()
        payload = await service.parse(
            file_name=path.name,
            content_type="text/plain",
            raw_bytes=raw,
        )
        p = payload.payload
        assert p.contact.name or p.experiences, path.name


def test_jd_fixture_files_not_empty() -> None:
    for path in _list_jds():
        assert len(path.read_text(encoding="utf-8").strip()) > 50, path.name


def test_mock_golden_behavioral_star() -> None:
    path = _MOCK / "golden_behavioral_star.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    feedback = normalize_coach_feedback(data["coach_feedback"])
    assert feedback["score"] >= data["min_score"]
    dims = feedback["dimensions"]
    for key in data["required_dimension_keys"]:
        assert key in dims
        assert key in DIMENSION_KEYS
    assert data["expected_tool"] == "jobcome_answer_save_attempt"
