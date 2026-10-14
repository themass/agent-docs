from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from jobcome.schemas.job import ParseFromUrlRequest
from jobcome.services.jd_fetch_service import FetchedPage, JdFetchService
from jobcome.services.job_service import JobService


@pytest.mark.asyncio
async def test_url_authorizes_before_network(monkeypatch):
    service = object.__new__(JobService)
    service._profiles = SimpleNamespace(get=AsyncMock(side_effect=PermissionError))
    fetch = AsyncMock()
    monkeypatch.setattr(JdFetchService, "fetch", fetch)
    with pytest.raises(PermissionError):
        await service.parse_url(
            "other", actor=None, body=ParseFromUrlRequest(url="https://example.com")
        )
    fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_url_provenance_server_produced(monkeypatch):
    service = object.__new__(JobService)
    service._profiles = SimpleNamespace(get=AsyncMock())
    service.parse_jd = AsyncMock()
    page = FetchedPage(
        "https://example.com",
        "https://example.com/final",
        "now",
        "text/html",
        "JD",
        "public job description long enough",
        "digest",
        method="browser",
    )
    fetch = AsyncMock(return_value=page)
    monkeypatch.setattr(JdFetchService, "fetch", fetch)
    await service.parse_url(
        "own", actor=None, body=ParseFromUrlRequest(url="https://example.com", render=True)
    )
    fetch.assert_awaited_once_with("https://example.com", render=True)
    kwargs = service.parse_jd.call_args.kwargs
    assert kwargs["body"].source_url == page.final_url
    assert kwargs["provenance"]["untrusted_content"] is True
    assert "text" not in kwargs["provenance"]


@pytest.mark.asyncio
async def test_mcp_fetch_authorizes_and_is_read_only(monkeypatch):
    from jobcome.mcp import handlers

    guard = AsyncMock(side_effect=PermissionError)
    fetch = AsyncMock()
    monkeypatch.setattr(handlers, "require_owned_profile", guard)
    monkeypatch.setattr(JdFetchService, "fetch", fetch)
    with pytest.raises(PermissionError):
        await handlers.job_fetch(SimpleNamespace(), url="https://example.com")
    fetch.assert_not_awaited()
