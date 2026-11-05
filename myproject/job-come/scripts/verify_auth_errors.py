#!/usr/bin/env python3
"""Does a failed sign-in tell the user something they can act on?

Why this script exists
----------------------
A user reported 「登录和发密码都报错」 with a form showing 「请求失败」. That copy was the
fallback for *an unparseable response body*, which only happens when the request never
reached our API at all -- a dev server whose rewrites were not live. Four characters with
no direction sent them through several rounds of retyping a password that was never the
problem.

Two separate defects were behind it, and neither is visible by reading the happy path:

1. `「请求失败」` named the symptom and not the situation, and it appeared for the one
   cause the user cannot diagnose: our service was unreachable.
2. The server's own messages were English strings written for logs
   (`Invalid email or password`). `looksTechnical` lets them through -- plain prose
   carries no URLs, no stack frames, no status codes -- so they rendered verbatim on a
   Chinese-language form.

Both are silent: an error box containing *something* looks like it is working. So the
assertions here are about the text a user actually reads.

Usage (frontend must already serve a production build):
    python scripts/verify_auth_errors.py --base http://127.0.0.1:3000
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys

from lib.bootstrap import ensure_project_env

ensure_project_env()

from playwright.async_api import async_playwright, expect  # noqa: E402

#: Latin letters with essentially no CJK. The server has user-facing Chinese copy now, so
#: anything matching this on a form is an internal string that escaped.
_LATIN_PROSE = re.compile(r"^[^\u4e00-\u9fff]{12,}$")

GUEST_CONTEXT = {
    "actor": "guest",
    "user": None,
    "capabilities": ["view"],
    "active_profile_id": None,
    "merge_conflict": None,
}


async def _context(p, base: str, *, routes: dict[str, tuple[int, object]]):
    """A browser whose listed API paths answer with a fixed status and body.

    `body` of `None` means "reply with something that is not our JSON envelope" --
    the shape a proxy or a dev server with dead rewrites produces, and the case the
    original bug report was actually in.
    """
    browser = await p.chromium.launch()
    ctx = await browser.new_context(viewport={"width": 1280, "height": 900})

    async def handler(route):
        url = route.request.url
        for path, (status, body) in routes.items():
            if path in url:
                if body is None:
                    await route.fulfill(
                        status=status,
                        content_type="text/html",
                        body="<html><body>404 This page could not be found.</body></html>",
                    )
                else:
                    await route.fulfill(status=status, json=body)
                return
        if "/auth/context" in url:
            await route.fulfill(json=GUEST_CONTEXT)
            return
        await route.fulfill(json={})

    await ctx.route("**/api/v1/**", handler)

    async def external(route):
        if route.request.url.startswith(base):
            await route.fallback()
        else:
            await route.abort()

    await ctx.route("**/*", external)
    return browser, ctx


async def _shown(page) -> list[str]:
    """Every alert/status line on the form, as the user reads it."""
    raw = await page.locator(".notice, [role=alert]").all_inner_texts()
    return [" ".join(t.split()) for t in raw if t.strip()]


async def _submit_login(page, base: str) -> None:
    await page.goto(f"{base}/auth/login")
    await page.wait_for_load_state("networkidle")
    await page.get_by_label("邮箱").fill("someone@example.com")
    await page.get_by_label("密码").fill("whatever-password")
    await page.get_by_role("button", name="登录", exact=True).click()
    await page.wait_for_timeout(600)


async def _case_wrong_password(p, base: str) -> list[str]:
    """A refused sign-in must say so in the user's language."""
    browser, ctx = await _context(
        p,
        base,
        routes={
            "/auth/login": (
                401,
                {"code": "invalid_credentials", "message": "邮箱或密码不正确，请重新输入。"},
            )
        },
    )
    try:
        page = await ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await _submit_login(page, base)

        shown = await _shown(page)
        assert shown, "a refused sign-in showed the user nothing at all"
        joined = " ".join(shown)
        assert "密码不正确" in joined, f"the reason was not stated: {shown}"
        # The old build rendered the server's log string straight onto the form.
        assert "Invalid email or password" not in joined, (
            "an English internal message reached the login form"
        )
        for line in shown:
            assert not _LATIN_PROSE.match(line), f"untranslated copy on the form: {line!r}"
        assert not errors, f"page errors: {errors}"
        return [f"wrong password: {shown[0]}"]
    finally:
        await browser.close()


async def _case_english_leak(p, base: str) -> list[str]:
    """An English message with no error code must still not reach the user.

    The service copy is Chinese now, but this is the regression that actually happened,
    and it happened because nothing stopped plain English prose. A code-only map would
    leave any endpoint we have not catalogued free to leak again.
    """
    browser, ctx = await _context(
        p,
        base,
        routes={"/auth/login": (400, {"message": "Session user not found"})},
    )
    try:
        page = await ctx.new_page()
        await _submit_login(page, base)
        shown = await _shown(page)
        assert shown, "an error with no code showed the user nothing"
        joined = " ".join(shown)
        assert "Session user not found" not in joined, (
            "English prose with no code was rendered verbatim"
        )
        assert re.search(r"[\u4e00-\u9fff]", joined), f"no Chinese copy shown: {shown}"
        return [f"english leak: {shown[0]}"]
    finally:
        await browser.close()


async def _case_unreachable(p, base: str) -> list[str]:
    """The reported bug: the request never arrived, so say that, not 「请求失败」."""
    browser, ctx = await _context(p, base, routes={"/auth/login": (404, None)})
    try:
        page = await ctx.new_page()
        await _submit_login(page, base)
        shown = await _shown(page)
        assert shown, "an unreachable API showed the user nothing"
        joined = " ".join(shown)
        assert "请求失败" not in joined, (
            "the directionless fallback is back; it names the symptom, not the situation"
        )
        assert "没能连上服务" in joined, (
            f"an unreachable service was not described as such: {shown}"
        )
        # Nothing about the password: it was never checked.
        assert "密码不正确" not in joined, (
            "a request that never arrived was blamed on the user's credentials"
        )
        return [f"unreachable: {shown[0]}"]
    finally:
        await browser.close()


async def _case_forgot_password(p, base: str) -> list[str]:
    """Success and failure must not share one box."""
    notes: list[str] = []
    browser, ctx = await _context(
        p,
        base,
        routes={
            "/auth/forgot-password": (
                200,
                {"message": "若该邮箱已注册，我们已发送重置密码邮件，请查收。链接 1 小时内有效。"},
            )
        },
    )
    try:
        page = await ctx.new_page()
        await page.goto(f"{base}/auth/forgot-password")
        await page.wait_for_load_state("networkidle")
        await page.get_by_label("邮箱").fill("someone@example.com")
        await page.get_by_role("button", name="发送重置邮件").click()
        await page.wait_for_timeout(600)

        await expect(page.locator(".notice-success")).to_be_visible()
        assert await page.locator(".notice-danger").count() == 0, (
            "a successful send also rendered an error box"
        )
        # The validity window comes from the server because it is configurable.
        await expect(page.get_by_text("1 小时内有效")).to_be_visible()
        # Resending has to be possible: the first mail may never arrive.
        await expect(page.get_by_role("button", name="重新发送")).to_be_visible()
        notes.append("forgot password: success is a success box, resend offered")
    finally:
        await browser.close()

    # And a real failure must not be dressed as success.
    browser, ctx = await _context(
        p,
        base,
        routes={
            "/auth/forgot-password": (
                400,
                {
                    "code": "email_not_configured",
                    "message": "邮件服务还没配置好，暂时发不出重置邮件，请联系我们。",
                },
            )
        },
    )
    try:
        page = await ctx.new_page()
        await page.goto(f"{base}/auth/forgot-password")
        await page.wait_for_load_state("networkidle")
        await page.get_by_label("邮箱").fill("someone@example.com")
        await page.get_by_role("button", name="发送重置邮件").click()
        await page.wait_for_timeout(600)

        await expect(page.locator(".notice-danger")).to_be_visible()
        assert await page.locator(".notice-success").count() == 0, (
            "a failed send told the user to go check their inbox"
        )
        shown = " ".join(await _shown(page))
        assert "邮件服务" in shown, f"the reason was not stated: {shown}"
        notes.append("forgot password: a failed send is not dressed as sent")
    finally:
        await browser.close()
    return notes


async def verify(base: str) -> int:
    notes: list[str] = []
    async with async_playwright() as p:
        notes += await _case_wrong_password(p, base)
        notes += await _case_english_leak(p, base)
        notes += await _case_unreachable(p, base)
        notes += await _case_forgot_password(p, base)
    print("PASS: auth failures are explained in the user's language")
    for n in notes:
        print(f"  {n}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:3000")
    args = ap.parse_args()
    sys.exit(asyncio.run(verify(args.base)))
