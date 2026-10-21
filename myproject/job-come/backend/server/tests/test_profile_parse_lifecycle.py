"""Failure is persisted as FAILED, never as a successful placeholder profile."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from jc.models.enums import ParseStatus
from jc.services.profile_ingest_service import IngestValidationError
from jc.services.profile_service import ProfileService


@pytest.mark.asyncio
async def test_pipeline_failure_marks_source_failed_without_overwriting_profile():
    svc = object.__new__(ProfileService)
    source = SimpleNamespace(
        id="s",
        file_name="resume.pdf",
        storage_key="key",
        content_type="application/pdf",
        parse_status=ParseStatus.PROCESSING,
    )
    profile = SimpleNamespace(sources=[source], payload={"contact": {"name": "原有姓名"}})
    svc._profiles = SimpleNamespace(get_by_id=AsyncMock(return_value=profile))
    svc._storage = SimpleNamespace(get_object_bytes=Mock(return_value=b"pdf"))
    svc._db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    svc._commit_parse_phase = AsyncMock()
    svc._apply_payload = Mock()
    svc._ingest = SimpleNamespace(
        parse=AsyncMock(side_effect=IngestValidationError("解析等待超时，未生成档案。"))
    )
    ok = await svc.parse_stored_source("p", "s")
    assert not ok
    assert source.parse_status == ParseStatus.FAILED
    assert source.parse_phase == "failed"
    assert "超时" in source.parse_error
    assert profile.payload["contact"]["name"] == "原有姓名"
    svc._apply_payload.assert_not_called()
    svc._db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [ParseStatus.FAILED, ParseStatus.PROCESSING])
async def test_empty_or_inflight_profile_cannot_be_confirmed(status):
    from jc.exceptions import ConflictError
    from jc.models.enums import ProfileStatus

    svc = object.__new__(ProfileService)
    profile = SimpleNamespace(
        sources=[SimpleNamespace(parse_status=status)],
        payload={},
        status=ProfileStatus.DRAFT,
        version=1,
    )
    svc._require_profile = AsyncMock(return_value=profile)
    svc._assert_owner = Mock()
    svc._db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    with pytest.raises(ConflictError):
        await svc.confirm("p", actor=object())
    assert profile.status == ProfileStatus.DRAFT
    assert profile.version == 1
    svc._db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_replacement_does_not_block_confirming_preserved_facts():
    from jc.models.enums import ProfileStatus

    svc = object.__new__(ProfileService)
    profile = SimpleNamespace(
        id="p",
        sources=[SimpleNamespace(parse_status=ParseStatus.FAILED)],
        payload={"contact": {"name": "原有姓名"}},
        status=ProfileStatus.DRAFT,
        version=1,
    )
    svc._require_profile = AsyncMock(return_value=profile)
    svc._assert_owner = Mock()
    svc._db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    result = await svc.confirm("p", actor=object())
    assert result.status == ProfileStatus.CONFIRMED
    assert profile.payload["contact"]["name"] == "原有姓名"

@pytest.mark.asyncio
async def test_success_applies_payload_and_marks_source_done_after_commit():
    from jc.models.enums import ProfileStatus
    from jc.schemas.profile_payload import ProfilePayload
    from jc.services.ingest_result import IngestResult

    svc = object.__new__(ProfileService)
    source = SimpleNamespace(
        id="s", file_name="resume.pdf", storage_key="key", content_type="application/pdf",
        parse_status=ParseStatus.PROCESSING, parse_phase="processing", parse_error=None,
    )
    profile = SimpleNamespace(
        id="p", sources=[source], payload={"contact": {"name": "old"}}, version=1,
        locale="zh-CN", status=ProfileStatus.DRAFT, contact_name=None, summary_text=None,
    )
    payload = ProfilePayload.model_validate({
        "contact": {"name": "new candidate"},
        "summary": "real summary",
    })
    svc._profiles = SimpleNamespace(get_by_id=AsyncMock(return_value=profile))
    svc._storage = SimpleNamespace(get_object_bytes=Mock(return_value=b"pdf"))
    svc._db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    svc._commit_parse_phase = AsyncMock()
    def apply_payload(profile_obj, value):
        profile_obj.payload = value.model_dump(mode="json")

    svc._apply_payload = Mock(side_effect=apply_payload)
    svc._ingest = SimpleNamespace(parse=AsyncMock(return_value=IngestResult(
        payload=payload, mode="llm_text_pdf", extraction_source="native_text")))

    assert await svc.parse_stored_source("p", "s") is True
    assert source.parse_status == ParseStatus.DONE
    assert profile.version == 2
    assert profile.payload["contact"]["name"] == "new candidate"
    svc._apply_payload.assert_called_once()
    svc._db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_upload_body_reader_stops_at_limit_plus_one_byte():
    from jc.api.profile_router import read_limited_upload
    from jc.services.profile_ingest_service import MAX_UPLOAD_BYTES, IngestValidationError

    class OversizedUpload:
        def __init__(self):
            self.remaining = MAX_UPLOAD_BYTES + 100
            self.read_bytes = 0

        async def read(self, size):
            count = min(size, self.remaining)
            self.remaining -= count
            self.read_bytes += count
            return b"x" * count

    upload = OversizedUpload()
    with pytest.raises(IngestValidationError, match="15 MB"):
        await read_limited_upload(upload)
    assert upload.read_bytes == MAX_UPLOAD_BYTES + 1
