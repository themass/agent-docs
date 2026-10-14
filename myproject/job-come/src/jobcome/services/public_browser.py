"""Read-only dynamic public pages; all browser networking is relayed through safe GET.

Not a general browser tool: no login, uploads, cookies, click, evaluate input or POST.
The dead proxy is defense-in-depth for requests not intercepted by Playwright.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime

from jobcome.exceptions import AppError


async def render_public_page(url, fetcher):
    from playwright.async_api import async_playwright

    from jobcome.services.jd_fetch_service import FetchedPage, public_url

    source = public_url(url)
    errors = []
    requests = 0
    total_bytes = 0
    semaphore = asyncio.Semaphore(4)
    try:
        async with asyncio.timeout(35), async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                proxy={"server": "http://127.0.0.1:9", "bypass": "<-loopback>"},
            )
            try:
                context = await browser.new_context(service_workers="block", accept_downloads=False)

                async def relay(route):
                    nonlocal requests, total_bytes
                    request = route.request
                    requests += 1
                    if requests > 40:
                        errors.append(AppError("动态读取请求数量超过上限", code="fetch_too_large"))
                        await route.abort()
                        return
                    if request.method != "GET" or request.resource_type not in {
                        "document",
                        "script",
                        "stylesheet",
                        "xhr",
                        "fetch",
                    }:
                        await route.abort()
                        return
                    try:
                        async with semaphore:
                            final, content_type, body = await fetcher.fetch_bytes(request.url)
                            total_bytes += len(body)
                            if total_bytes > 3_000_000:
                                raise AppError("动态页面超过总量上限", code="fetch_too_large")
                            # A main-document redirect must preserve the final document base URL.
                            if request.is_navigation_request() and final != request.url:
                                await route.fulfill(
                                    status=302, headers={"location": final}, body=""
                                )
                            else:
                                await route.fulfill(
                                    status=200, content_type=content_type or "text/plain", body=body
                                )
                    except AppError as exc:
                        errors.append(exc)
                        await route.abort()

                await context.route("**/*", relay)

                async def close_websocket(ws):
                    await ws.close()

                await context.route_web_socket("**/*", close_websocket)
                page = await context.new_page()
                page.on("popup", lambda popup: asyncio.create_task(popup.close()))
                await page.goto(source, wait_until="networkidle", timeout=30_000)
                text = (await page.locator("body").inner_text())[:50_000]
                if len(text.strip()) < 20:
                    raise AppError("动态页面无有效正文，请粘贴 JD。", code="fetch_empty")
                if errors:
                    raise errors[0]  # Do not silently return incomplete/security-blocked content.
                return FetchedPage(
                    source,
                    public_url(page.url),
                    datetime.now(UTC).isoformat(),
                    "text/html",
                    (await page.title())[:300],
                    text,
                    hashlib.sha256(text.encode()).hexdigest(),
                    method="browser",
                )
            finally:
                await browser.close()
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            "动态页面读取失败，请粘贴正文；不绕过登录或验证码。", code="browser_failed"
        ) from exc
