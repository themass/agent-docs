"""Ingest strategy selection and bounded execution; no live model/storage calls."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from jc.config import settings
from jc.schemas.profile_payload import ProfileContact, ProfilePayload
from jc.services.profile_ingest_service import IngestValidationError, ProfileIngestService
from jc.services.profile_structurer import ProfileStructureError

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


def test_validate_rejects_unknown_extension():
    with pytest.raises(IngestValidationError):
        ProfileIngestService().validate_upload("resume.exe", None, 100)


@pytest.mark.asyncio
async def test_llm_disabled_keeps_explicit_degraded_contract(pipeline, monkeypatch):
    monkeypatch.setattr(settings, "jc_llm_enabled", False)
    result = await parse(pipeline)
    assert result.mode == "mock_fallback"
    assert result.warning
    pipeline._structurer.structure.assert_not_awaited()


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        TimeoutError(),
        ProfileStructureError("llm_call_failed"),
        ProfileStructureError("invalid_json_response"),
    ],
)
async def test_model_failure_never_triggers_document_route_fallback(pipeline, error):
    pipeline._structurer.structure.side_effect = error
    with pytest.raises((IngestValidationError, ProfileStructureError)):
        await parse(pipeline)
    pipeline._structurer.structure.assert_awaited_once()
    pipeline._vision.extract_pdf.assert_not_awaited()
    pipeline._extractor.extract_markdown_route_b_with_timeout.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["pdf", "docx"])
async def test_local_repair_precedes_the_only_paid_structure_call(pipeline, kind):
    pipeline._extractor.classify.return_value = kind
    pipeline._extractor.extract.return_value = "乱码\ufffd"
    pipeline._extractor.extract_markdown_route_b_with_timeout.return_value = TEXT
    result = await parse(pipeline)
    assert result.mode == f"llm_markitdown_{kind}"
    assert result.extraction_source == "markitdown"
    pipeline._structurer.structure.assert_awaited_once_with(text=TEXT, source_file="resume.pdf")
    pipeline._vision.extract_pdf.assert_not_awaited()


@pytest.mark.asyncio
async def test_scan_or_mixed_pdf_goes_directly_to_vision_without_restructuring(pipeline):
    pipeline._extractor.has_scanned_pdf_pages.return_value = True
    result = await parse(pipeline)
    assert result.mode == "vision_pdf"
    pipeline._vision.extract_pdf.assert_awaited_once()
    pipeline._structurer.structure.assert_not_awaited()
    pipeline._extractor.extract_markdown_route_b_with_timeout.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_text_pdf_falls_back_locally_then_vision(pipeline):
    pipeline._extractor.extract.return_value = ""
    result = await parse(pipeline)
    assert result.mode == "vision_pdf"
    pipeline._structurer.structure.assert_not_awaited()


@pytest.mark.asyncio
async def test_image_uses_only_vision(pipeline):
    pipeline._extractor.classify.return_value = "image"
    pipeline._extractor.extract.return_value = ""
    result = await parse(pipeline)
    assert result.mode == "vision_image"
    pipeline._vision.extract.assert_awaited_once()
    pipeline._structurer.structure.assert_not_awaited()


@pytest.mark.asyncio
async def test_whole_budget_cancels_producer_and_does_not_try_ocr(pipeline, monkeypatch):
    monkeypatch.setattr(settings, "jc_ingest_timeout_seconds", 0.02)
    stopped = asyncio.Event()

    async def hang(**kwargs):
        try:
            await asyncio.sleep(10)
        finally:
            stopped.set()

    pipeline._structurer.structure.side_effect = hang
    with pytest.raises(IngestValidationError, match="超时"):
        await asyncio.wait_for(parse(pipeline), 1)
    assert stopped.is_set()
    pipeline._vision.extract_pdf.assert_not_awaited()


@pytest.mark.asyncio
async def test_caller_cancellation_propagates(pipeline):
    pipeline._structurer.structure.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await parse(pipeline)
    pipeline._vision.extract_pdf.assert_not_awaited()


@pytest.mark.asyncio
async def test_native_extraction_is_off_event_loop(pipeline):
    import threading

    entered, release = threading.Event(), threading.Event()

    def blocking_extract(**kwargs):
        entered.set()
        if not release.wait(2):
            raise AssertionError("event loop was blocked by native extraction")
        return TEXT

    pipeline._extractor.extract.side_effect = blocking_extract
    task = asyncio.create_task(parse(pipeline))
    try:
        async with asyncio.timeout(1):
            while not entered.is_set():
                await asyncio.sleep(0.001)
        # This line can only run while extract() is blocked if it runs off-loop.
        release.set()
        assert (await task).mode == "llm_text_pdf"
    finally:
        release.set()
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_readable_pdf_timeout_is_not_misreported_as_bad_file(pipeline):
    pipeline._structurer.structure.side_effect = ProfileStructureError("llm_timeout")
    with pytest.raises(IngestValidationError, match="模型服务响应超时") as caught:
        await parse(pipeline)
    assert "无需修改文件格式" in str(caught.value)
    pipeline._vision.extract_pdf.assert_not_awaited()
    pipeline._extractor.extract_markdown_route_b_with_timeout.assert_not_awaited()
