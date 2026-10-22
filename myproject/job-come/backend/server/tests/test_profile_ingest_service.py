"""Ingest strategy selection and bounded execution; no live model/storage calls."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from jc.config import settings
from jc.schemas.profile_payload import ProfileContact, ProfilePayload
from jc.services.profile_ingest_service import ProfileIngestService

TEXT = "候选人简历，2018年开始从事软件开发，负责订单平台研发、接口设计、性能优化和团队协作。" * 3


@pytest.fixture
def pipeline(monkeypatch):
    monkeypatch.setattr(settings, "jc_llm_enabled", True)
    svc = ProfileIngestService()
    payload = ProfilePayload(contact=ProfileContact(name="候选人"))
    svc._extractor = SimpleNamespace(
        classify=Mock(return_value="pdf"),
        extract=Mock(return_value=TEXT),
        has_scanned_pdf_pages=Mock(return_value=False),
        extract_markdown_route_b_with_timeout=AsyncMock(return_value=""),
        docx_embedded_images=Mock(return_value=[]),
    )
    svc._structurer = SimpleNamespace(structure=AsyncMock(return_value=payload))
    svc._vision = SimpleNamespace(
        extract_pdf=AsyncMock(return_value=payload),
        extract=AsyncMock(return_value=payload),
        extract_embedded_images=AsyncMock(return_value=payload),
    )
    return svc


async def parse(svc, **kwargs):
    return await svc.parse(
        file_name="resume.pdf", content_type="application/pdf", raw_bytes=b"pdf", **kwargs
    )






@pytest.mark.asyncio
async def test_readable_pdf_uses_one_text_call_even_if_payload_is_sparse(pipeline):
    phases = []

    async def phase(name):
        phases.append(name)

    result = await parse(pipeline, on_phase=phase)
    assert result.mode == "llm_text_pdf"
    assert result.warning  # Sparse output is editable, not a reason for another OCR run.
    pipeline._structurer.structure.assert_awaited_once()
    pipeline._vision.extract_pdf.assert_not_awaited()
    pipeline._extractor.extract_markdown_route_b_with_timeout.assert_not_awaited()
    assert phases == ["classify", "extract_text", "inspect_document", "llm_text_pdf", "pick_best"]


















