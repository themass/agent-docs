"""Profile ingest tests."""

import pytest

from jobcome.services.profile_ingest_service import IngestValidationError, ProfileIngestService


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
