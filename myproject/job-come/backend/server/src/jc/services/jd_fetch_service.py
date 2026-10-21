"""Bounded public GET fetch; DNS is validated and pinned at the TCP boundary."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import re
import socket
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from html import unescape
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpcore
from httpcore._backends.anyio import AnyIOBackend

from jc.domain.jd_integrity import inspect_jd_text
from jc.exceptions import AppError


def public_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        if (
            len(url) > 2048
            or parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or parts.port not in {None, 80, 443}
            or "\\" in url
            or any(ord(c) <= 32 or ord(c) == 127 for c in url)
        ):
            raise ValueError()
        host = parts.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        if (
            "%" in host
            or host == "localhost"
            or host.endswith((".localhost", ".local", ".internal"))
        ):
            raise ValueError()
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            if "." not in host:
                raise ValueError()
        else:
            if not is_public_ip(str(ip)):
                raise ValueError()
        return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))
    except (ValueError, UnicodeError) as exc:
        raise AppError(
            "只允许公开 HTTP(S) 地址、80/443 端口且不含登录凭据。", code="unsafe_url"
        ) from exc


def is_public_ip(value: str) -> bool:
    ip = ipaddress.ip_address(value)
    return ip.is_global and not (
        ip.is_multicast or ip.is_reserved or ip.is_unspecified or ip.is_loopback
    )


async def resolve_public(host: str, port: int) -> list[str]:
    records = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(row[4][0] for row in records))
    # Fail the whole mixed answer rather than trying a public address first.
    if not addresses or not all(is_public_ip(ip) for ip in addresses):
        raise AppError("目标解析到非公开地址，已拒绝。", code="unsafe_url")
    return addresses


class PublicNetworkBackend(httpcore.AsyncNetworkBackend):
    """Preserve original Host/SNI while dialing a validated literal IP (no second DNS)."""

    def __init__(self) -> None:
        self._backend = AnyIOBackend()

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        addresses = await resolve_public(host, port)
        return await self._backend.connect_tcp(
            addresses[0],
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(self, *args, **kwargs):
        raise AppError("这个链接地址不被支持，请改用公开网页地址。", code="unsafe_url")

    async def sleep(self, seconds):
        await self._backend.sleep(seconds)


@dataclass(frozen=True)
class FetchedPage:
    source_url: str
    final_url: str
    fetched_at: str
    content_type: str
    title: str
    text: str
    sha256: str
    method: str = "http"
    untrusted_content: bool = True
    integrity: dict | None = None

    def as_dict(self) -> dict:
        return asdict(self)


class JdFetchService:
    _MAX_BYTES = 500_000
    _TIMEOUT = 20.0
    _MAX_REDIRECTS = 4

    def _pool(self):
        return httpcore.AsyncConnectionPool(network_backend=PublicNetworkBackend(), retries=0)

    async def fetch_bytes(self, url: str) -> tuple[str, str, bytes]:
        """GET only; no proxy env, cookies, caller headers, credentials or body."""
        current = public_url(url)
        try:
            async with asyncio.timeout(self._TIMEOUT), self._pool() as pool:
                for step in range(self._MAX_REDIRECTS + 1):
                    async with pool.stream(
                        "GET",
                        current,
                        headers={
                            "User-Agent": "JC/1.0",
                            "Accept-Encoding": "identity",
                        },
                        extensions={
                            "timeout": {
                                key: self._TIMEOUT for key in ("connect", "read", "write", "pool")
                            }
                        },
                    ) as response:
                        headers = {
                            k.decode().lower(): v.decode("latin1") for k, v in response.headers
                        }
                        if response.status in {301, 302, 303, 307, 308}:
                            if step == self._MAX_REDIRECTS or not headers.get("location"):
                                raise AppError("重定向次数过多或缺少目标。", code="fetch_failed")
                            current = public_url(urljoin(current, headers["location"]))
                            continue
                        if response.status < 200 or response.status >= 300:
                            raise AppError(
                                f"职位页面 HTTP {response.status}，请粘贴正文。",
                                code="fetch_failed",
                            )
                        if headers.get("content-encoding", "identity").lower() != "identity":
                            raise AppError("不接受压缩响应，请粘贴正文。", code="fetch_failed")
                        body = bytearray()
                        async for chunk in response.aiter_stream():
                            if len(body) + len(chunk) > self._MAX_BYTES:
                                raise AppError(
                                    "网页超过 500KB 上限，请粘贴正文。", code="fetch_too_large"
                                )
                            body.extend(chunk)
                        return current, headers.get("content-type", ""), bytes(body)
        except (
            httpcore.NetworkError,
            httpcore.TimeoutException,
            httpcore.ProtocolError,
            TimeoutError,
            OSError,
        ) as exc:
            raise AppError("抓取失败或超时，请粘贴正文。", code="fetch_failed") from exc
        raise AppError("抓取失败", code="fetch_failed")

    async def fetch(self, url: str, *, render: bool = False) -> FetchedPage:
        source = public_url(url)
        if render:
            from jc.services.public_browser import render_public_page

            return await render_public_page(source, self)
        final_url, content_type, raw = await self.fetch_bytes(source)
        if content_type and not any(
            kind in content_type.lower() for kind in ("text/", "application/xhtml")
        ):
            raise AppError(
                "只接受网页或纯文本；请使用简历上传入口处理文档。", code="fetch_content_type"
            )
        html = raw.decode("utf-8", errors="replace")
        title = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
        text = (
            self._html_to_text(html)
            if "html" in content_type or html.lstrip().startswith("<")
            else html[:50_000]
        )
        if len(text.strip()) < 20:
            raise AppError("网页正文不足，请使用动态读取或粘贴 JD。", code="fetch_empty")
        return FetchedPage(
            source,
            final_url,
            datetime.now(UTC).isoformat(),
            content_type,
            unescape(title.group(1)).strip()[:300] if title else "",
            text,
            hashlib.sha256(raw).hexdigest(),
            integrity=inspect_jd_text(html),
        )

    async def fetch_text(self, url: str) -> str:
        return (await self.fetch(url)).text

    @staticmethod
    def _html_to_text(html: str) -> str:
        html = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", html)
        html = re.sub(r"(?is)<br\s*/?>|</(?:p|div|li|h[1-6])>", "\n", html)
        text = unescape(re.sub(r"<[^>]+>", " ", html))
        text = re.sub(r"[ \t]+", " ", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()[:50_000]
