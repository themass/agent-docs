"""Offline public-fetch security contracts: never contact real services."""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from jobcome.exceptions import AppError
from jobcome.services import jd_fetch_service as fetch


@pytest.mark.parametrize('url', [
    'http://127.0.0.1/', 'http://169.254.169.254/', 'http://10.1.2.3/',
    'http://[::1]/', 'file:///etc/passwd', 'http://localhost/',
    'https://user:password@example.com/', 'http://example.com:8080/',
    'http://example.internal/', 'https://example.com/\nheader',
])
def test_reject_unsafe_url(url):
    with pytest.raises(AppError):
        fetch.public_url(url)


def test_public_url_strips_fragment():
    assert fetch.public_url('https://example.com/jobs#secret') == 'https://example.com/jobs'


@pytest.mark.asyncio
async def test_dns_mixed_public_private_rejected(monkeypatch):
    resolver = AsyncMock(return_value=[
        (2, 1, 6, '', ('93.184.216.34', 443)),
        (2, 1, 6, '', ('127.0.0.1', 443)),
    ])
    monkeypatch.setattr(fetch.asyncio.get_running_loop(), 'getaddrinfo', resolver)
    with pytest.raises(AppError):
        await fetch.resolve_public('example.com', 443)


@pytest.mark.asyncio
async def test_tcp_dials_validated_literal_not_hostname(monkeypatch):
    monkeypatch.setattr(fetch, 'resolve_public', AsyncMock(return_value=['93.184.216.34']))
    backend = fetch.PublicNetworkBackend()
    backend._backend = AsyncMock()
    await backend.connect_tcp('example.com', 443, timeout=1)
    assert backend._backend.connect_tcp.call_args.args == ('93.184.216.34', 443)


class Response:
    def __init__(self, status=200, headers=None, chunks=None):
        self.status = status
        self.headers = headers or [(b'content-type', b'text/html')]
        self.chunks = chunks if chunks is not None else [b'<p>Public job description with sufficient content.</p>']
    async def aiter_stream(self):
        for chunk in self.chunks:
            yield chunk


class Pool:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        pass
    @asynccontextmanager
    async def stream(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        yield next(self.responses)


@pytest.mark.asyncio
async def test_private_redirect_never_requested(monkeypatch):
    pool = Pool([Response(302, [(b'location', b'http://127.0.0.1/admin')])])
    service = fetch.JdFetchService()
    monkeypatch.setattr(service, '_pool', lambda: pool)
    with pytest.raises(AppError):
        await service.fetch('https://example.com/job')
    assert len(pool.calls) == 1


@pytest.mark.asyncio
async def test_stream_limit_fails_not_truncates(monkeypatch):
    pool = Pool([Response(chunks=[b'a' * 300_000, b'b' * 300_000])])
    service = fetch.JdFetchService()
    monkeypatch.setattr(service, '_pool', lambda: pool)
    with pytest.raises(AppError) as error:
        await service.fetch('https://example.com/job')
    assert error.value.code == 'fetch_too_large'


@pytest.mark.asyncio
async def test_public_fetch_provenance_and_no_credentials(monkeypatch):
    pool = Pool([Response()])
    service = fetch.JdFetchService()
    monkeypatch.setattr(service, '_pool', lambda: pool)
    page = await service.fetch('https://example.com/job')
    assert page.source_url == page.final_url == 'https://example.com/job'
    assert page.fetched_at and len(page.sha256) == 64
    assert page.untrusted_content
    assert 'Public job description' in page.text
    method, _, kwargs = pool.calls[0]
    assert method == 'GET'
    assert set(kwargs['headers']) == {'User-Agent', 'Accept-Encoding'}
