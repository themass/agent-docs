"""Fetch public job posting URL → plain text (Scout-lite, no browser)."""

from __future__ import annotations

import re

import httpx

from jobcome.exceptions import AppError


class JdFetchService:
    _MAX_BYTES = 500_000
    _TIMEOUT = 20.0

    async def fetch_text(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            raise AppError("Invalid URL", code="invalid_url")
        try:
            async with httpx.AsyncClient(
                timeout=self._TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": "JobCome/1.0 (+https://job.sspacee.com)"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AppError(f"Failed to fetch URL: {exc}", code="fetch_failed") from exc

        raw = response.content[: self._MAX_BYTES]
        content_type = response.headers.get("content-type", "")
        if "html" in content_type or raw.lstrip().startswith(b"<"):
            return self._html_to_text(raw.decode("utf-8", errors="ignore"))
        return raw.decode("utf-8", errors="ignore")[:50_000]

    @staticmethod
    def _html_to_text(html: str) -> str:
        html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
        html = re.sub(r"(?is)<br\s*/?>", "\n", html)
        html = re.sub(r"(?is)</p>", "\n\n", html)
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()[:50_000]
