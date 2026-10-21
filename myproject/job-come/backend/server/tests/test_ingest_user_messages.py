"""Ingest warnings shown to users must not leak LLM vendor errors."""

from __future__ import annotations

import pytest

from jc.services.profile_ingest_service import IngestValidationError, ProfileIngestService
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
    with pytest.raises(IngestValidationError) as caught:
        await service.parse(
            file_name="resume.txt",
            content_type="text/plain",
            raw_bytes=("候选人工作经历与教育背景，负责订单平台研发和性能优化。" * 4).encode(),
        )
    warning = str(caught.value)
    assert "未完成" in warning
    assert "ingest_fast" not in warning
    assert "ServiceUnavailable" not in warning
    assert "openai/" not in warning
