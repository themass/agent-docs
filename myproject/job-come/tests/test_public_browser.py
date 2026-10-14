"""Real Chromium, all page bytes are offline fixtures; no internet or shared state."""

import pytest

from jobcome.exceptions import AppError
from jobcome.services.jd_fetch_service import public_url
from jobcome.services.public_browser import render_public_page


class FixtureFetcher:
    def __init__(self, script):
        self.script = script
        self.urls = []

    async def fetch_bytes(self, url):
        public_url(url)
        self.urls.append(url)
        if url.endswith("/app.js"):
            return url, "application/javascript", self.script.encode()
        return (
            url,
            "text/html",
            (
                b"<html><head><title>Public JD</title></head><body>"
                b'<div id="jd">Loading</div><script src="/app.js"></script></body></html>'
            ),
        )


@pytest.mark.asyncio
async def test_dynamic_public_body_is_rendered():
    fixture = FixtureFetcher(
        'document.querySelector("#jd").textContent="Product manager for internet '
        'knowledge workers, research and planning";'
    )
    result = await render_public_page("https://example.com/job", fixture)
    assert "Product manager" in result.text
    assert result.method == "browser"
    assert result.untrusted_content is True
    assert fixture.urls == ["https://example.com/job", "https://example.com/app.js"]


@pytest.mark.asyncio
async def test_private_dynamic_fetch_fails_closed():
    fixture = FixtureFetcher(
        'document.querySelector("#jd").textContent="Valid text must not hide blocked request";'
        'fetch("http://127.0.0.1/secret");'
    )
    with pytest.raises(AppError) as exc:
        await render_public_page("https://example.com/job", fixture)
    assert exc.value.code == "unsafe_url"


@pytest.mark.asyncio
async def test_post_never_reaches_fetcher():
    fixture = FixtureFetcher(
        'document.querySelector("#jd").textContent="Public job description, no submission";'
        'fetch("/submit", {method:"POST",body:"secret"}).catch(()=>{});'
    )
    await render_public_page("https://example.com/job", fixture)
    assert not any("/submit" in url for url in fixture.urls)
