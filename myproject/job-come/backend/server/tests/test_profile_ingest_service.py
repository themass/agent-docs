"""Profile ingest tests."""

import pytest

from jc.services.profile_ingest_service import IngestValidationError, ProfileIngestService


def test_validate_rejects_unknown_extension() -> None:
    service = ProfileIngestService()
    with pytest.raises(IngestValidationError):
        service.validate_upload("resume.exe", "application/octet-stream", 100)


@pytest.mark.asyncio
async def test_parse_pdf_mock_fallback() -> None:
    service = ProfileIngestService()
    result = await service.parse(
        file_name="zhang_san.pdf",
        content_type="application/pdf",
        raw_bytes=b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
    )
    assert result.payload.contact.name
    assert result.mode == "mock_fallback"
    assert result.warning


@pytest.mark.asyncio
async def test_docx_retries_local_markdown_route_after_invalid_llm_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blank/non-JSON primary model result must not exhaust a normal DOCX upload."""
    from jc.config import settings
    from jc.schemas.profile_payload import ProfileContact, ProfilePayload

    class Extractor:
        def classify(self, file_name: str, content_type: str | None) -> str:
            return "docx"

        def extract(self, **kwargs: object) -> str:
            return "Route A Word text"

        async def extract_markdown_route_b_with_timeout(self, **kwargs: object) -> str:
            return "# Route B Markdown\nCandidate experience"

        def docx_embedded_images(self, raw_bytes: bytes) -> list[tuple[bytes, str]]:
            return []

    class Structurer:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def structure(self, *, text: str, source_file: str) -> ProfilePayload:
            self.calls.append(text)
            if text.startswith("Route A"):
                raise RuntimeError("empty_model_response")
            return ProfilePayload(contact=ProfileContact(name="候选人"))

    monkeypatch.setattr(settings, "jc_llm_enabled", True)
    service = ProfileIngestService()
    service._extractor = Extractor()  # type: ignore[assignment]
    structurer = Structurer()
    service._structurer = structurer  # type: ignore[assignment]
    phases: list[str] = []

    async def on_phase(phase: str) -> None:
        phases.append(phase)

    result = await service.parse(
        file_name="resume.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        raw_bytes=b"uploaded-docx",
        on_phase=on_phase,
    )

    assert result.mode == "llm_markitdown_docx"
    assert result.extraction_source == "markitdown"
    assert result.payload.contact.name == "候选人"
    assert structurer.calls == ["Route A Word text", "# Route B Markdown\nCandidate experience"]
    assert "llm_markitdown_docx" in phases


@pytest.mark.asyncio
async def test_pdf_route_b_runs_when_text_route_fails_even_if_vision_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jc.config import settings
    from jc.schemas.profile_payload import ProfileContact, ProfilePayload

    class Extractor:
        def classify(self, file_name: str, content_type: str | None) -> str:
            return "pdf"

        def extract(self, **kwargs: object) -> str:
            return "PDF native text"

        async def extract_markdown_route_b_with_timeout(self, **kwargs: object) -> str:
            return "PDF markdown fallback"

        def pdf_page_images(self, *args: object, **kwargs: object) -> list[tuple[bytes, str]]:
            return []

    class Structurer:
        async def structure(self, *, text: str, source_file: str) -> ProfilePayload:
            if text == "PDF native text":
                raise RuntimeError("invalid_json_response")
            return ProfilePayload(contact=ProfileContact(name="PDF 候选人"))

    class Vision:
        async def extract_pdf(self, **kwargs: object) -> ProfilePayload:
            raise RuntimeError("vision unavailable")

    monkeypatch.setattr(settings, "jc_llm_enabled", True)
    service = ProfileIngestService()
    service._extractor = Extractor()  # type: ignore[assignment]
    service._structurer = Structurer()  # type: ignore[assignment]
    service._vision = Vision()  # type: ignore[assignment]

    result = await service.parse(
        file_name="resume.pdf",
        content_type="application/pdf",
        raw_bytes=b"uploaded-pdf",
    )

    assert result.mode == "llm_markitdown_pdf"
    assert result.extraction_source == "markitdown"
    assert result.payload.contact.name == "PDF 候选人"
