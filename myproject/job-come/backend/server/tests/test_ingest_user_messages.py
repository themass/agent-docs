"""Ingest warnings shown to users must not leak LLM vendor errors."""

from __future__ import annotations

import pytest

from jc.services.ingest_user_messages import USER_LLM_PARSE_UNAVAILABLE
from jc.services.profile_ingest_service import ProfileIngestService
from jc.services.profile_structurer import ProfileStructurer


@pytest.mark.asyncio
async def test_llm_failure_user_warning_omits_model_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "jc.services.profile_ingest_service.settings.jc_llm_enabled",
        True,
    )

    async def _boom(self, **kwargs: object) -> None:
        raise RuntimeError(
            "All models failed for scenario ingest_fast: openai/foo: ServiceUnavailableError"
        )

    monkeypatch.setattr(ProfileStructurer, "structure", _boom)

    service = ProfileIngestService()
    result = await service.parse(
        file_name="resume.pdf",
        content_type="application/pdf",
        raw_bytes=b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
    )

    assert result.mode == "mock_fallback"
    assert result.warning == USER_LLM_PARSE_UNAVAILABLE
    assert "ingest_fast" not in (result.warning or "")
    assert "ServiceUnavailable" not in (result.warning or "")
    assert "openai/" not in (result.warning or "")
