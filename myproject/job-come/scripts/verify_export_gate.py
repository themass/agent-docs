#!/usr/bin/env python3
r"""Can the user always get their own resume out of the product?

Step 4's only job is handing over a file. The pre-export reviewer used to decide whether
that happened: `can_export == false` disabled every download button, and the server
raised `reviewer_failed` on top of it. That made one model call a single point of
failure for the product's core deliverable. Three different situations all ended with
the user holding nothing:

- the reviewer found something (sometimes wrongly -- merging two highlights legitimately
  breaks attribution, and the audit reports it as an unsupported claim);
- the gateway was unreachable, so there was no verdict at all;
- the request simply never came back, leaving a spinner and disabled buttons.

Only the first is a statement about the resume, and even that one belongs to the user to
judge. So the check is now advisory: findings must be *read* (one click) and everything
else must not stand in the way at all.

This script asserts that, because it cannot be read off the code: `downloadable`
combines four pieces of state and the regression is silent -- a disabled button looks
like a considered decision.

Usage:
    python scripts/verify_export_gate.py --base http://127.0.0.1:3000
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import importlib.util
import json
import sys
from pathlib import Path

from lib.bootstrap import ensure_project_env

ensure_project_env()

from playwright.async_api import async_playwright, expect  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "verify_resume_steps", str(Path(__file__).with_name("verify_resume_steps.py"))
)
assert _SPEC and _SPEC.loader
_VRS = importlib.util.module_from_spec(_SPEC)
sys.modules["verify_resume_steps"] = _VRS
_SPEC.loader.exec_module(_VRS)

# Reviewed, and it found something that would block under the old contract.
REVIEW_FAILED = {
    **copy.deepcopy(_VRS.REVIEW),
    "status": "failed",
    "notes": "有 1 处数字在档案里找不到依据",
    "reviewed": True,
    "blocking_issue_count": 1,
    "issues": [
        {
            "severity": "error",
            "field": "experience_blocks[0].bullets[0]",
            "message": "「发布耗时降低 70%」在档案里找不到依据。",
            "code": "unsupported_claim",
        },
    ],
}

# No verdict. The issue list carries internal diagnostics, which is exactly why they
# must not be rendered as findings about the resume.
REVIEW_UNAVAILABLE = {
    **copy.deepcopy(_VRS.REVIEW),
    "status": "unavailable",
    "notes": "自动质检服务暂时不可用，本次没有核对简历内容。",
    "reviewed": False,
    "blocking_issue_count": 0,
    "issues": [
        {
            "severity": "warning",
            "code": "reviewer_unavailable",
            "message": "Reviewer call failed: RuntimeError",
        },
    ],
}


async def _open_export_step(page, base: str) -> None:
    """Walk to step 4 the way a user does."""
    await page.goto(f"{base}/resume-agent")
    await page.wait_for_load_state("networkidle")
    await page.get_by_role("button", name="优化预览").first.click()
    await page.wait_for_load_state("networkidle")
    await page.get_by_role("button", name="内容定稿，去导出").click()
    await page.wait_for_load_state("networkidle")
    await expect(page.get_by_role("heading", name="导出前质检")).to_be_visible()


async def _context(p, base: str, *, review, hold: asyncio.Event | None = None):
    """A browser context whose `/export/review` returns `review` (or hangs on `hold`)."""
    browser = await p.chromium.launch()
    context = await browser.new_context(
        viewport={"width": 1600, "height": 1000},
        service_workers="block",
    )

    async def route_api(route):
        url = route.request.url
        if "/export/review" in url:
            if hold is not None:
                await hold.wait()
            await route.fulfill(content_type="text/event-stream", body=(
                f"data: {json.dumps({'type': 'result', 'data': review})}\n\n"
            ))
            return
        payload = _VRS._route_payload(url, route.request.method)
        if "/elevate/preview/stream" in url:
            await route.fulfill(content_type="text/event-stream", body=(
                f"data: {json.dumps({'type': 'result', 'data': payload})}\n\n"
            ))
        else:
            await route.fulfill(json=payload)

    await context.route("**/api/v1/**", route_api)

    async def block_external(route):
        if "/health/" in route.request.url:
            await route.fulfill(
                json={
                    "llm_enabled": True,
                    "llm_api_key_set": True,
                    "llm_vision_api_key_set": True,
                    "routing_path": "fixture",
                }
            )
        elif route.request.url.startswith(base):
            await route.fallback()
        else:
            await route.abort()

    await context.route("**/*", block_external)
    return browser, context


async def _pdf_enabled(page) -> bool:
    return await page.get_by_role("button", name="生成 PDF").is_enabled()


async def _case_findings(p, base: str) -> list[str]:
    """Reviewed and rejected: read the findings, then the download is yours."""
    notes: list[str] = []
    browser, context = await _context(p, base, review=REVIEW_FAILED)
    try:
        page = await context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await _open_export_step(page, base)

        await expect(page.get_by_text("发现 1 处建议先确认的问题")).to_be_visible()
        await expect(
            page.get_by_text("在档案里找不到依据", exact=False).first
        ).to_be_visible()
        # 「必须修改」 was a promise we do not keep: nothing is required here.
        assert await page.get_by_text("必须修改", exact=False).count() == 0, (
            "the findings are still presented as mandatory"
        )

        assert not await _pdf_enabled(page), (
            "blocking findings were never shown to the user before the download opened"
        )
        # Going back is the recommended route, so it must be the prominent one.
        await expect(page.get_by_role("button", name="回到优化预览修改")).to_be_visible()

        await page.get_by_role("button", name="我已了解，仍要下载").click()
        await page.wait_for_timeout(200)
        assert await _pdf_enabled(page), (
            "the user acknowledged the findings and still cannot download their resume"
        )
        for label in ("生成 Word", "生成 网页版"):
            assert await page.get_by_role("button", name=label).is_enabled(), (
                f"{label} stayed disabled after acknowledgement"
            )

        assert not errors, f"page errors: {errors}"
        notes.append("findings: shown -> acknowledged -> all three formats enabled")
    finally:
        await browser.close()
    return notes


async def _case_unavailable(p, base: str) -> list[str]:
    """No verdict: nothing to acknowledge, nothing blocked, no accusation."""
    notes: list[str] = []
    browser, context = await _context(p, base, review=REVIEW_UNAVAILABLE)
    try:
        page = await context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await _open_export_step(page, base)

        # Wait for the verdict to land first. Before it does, the page is in the
        # "check running" state, which `_case_never_returns` covers separately; what
        # matters here is what happens once "no verdict" is the answer.
        await expect(page.get_by_text("这次没有完成检查，不影响下载")).to_be_visible()
        assert await _pdf_enabled(page), (
            "the reviewer was unavailable and the download was withheld; the user "
            "cannot fix our gateway"
        )
        # An outage must not read as a judgement on the resume.
        for forbidden in ("建议先确认", "必须修改", "有问题需要先处理"):
            assert await page.get_by_text(forbidden, exact=False).count() == 0, (
                f"an unavailable reviewer rendered as {forbidden!r}"
            )
        # Internal diagnostics are not user-facing content.
        assert await page.get_by_text("RuntimeError", exact=False).count() == 0, (
            "an internal error string was rendered as a resume finding"
        )

        assert not errors, f"page errors: {errors}"
        notes.append("unavailable: download open, framed as 'not checked', no leakage")
    finally:
        await browser.close()
    return notes


async def _case_never_returns(p, base: str) -> list[str]:
    """A request that hangs must not hold the file hostage either.

    The reviewer chain is three endpoints at 60s each, so this is minutes of spinner in
    the real product -- the state the user reported. Waiting has to be optional.
    """
    notes: list[str] = []
    hold = asyncio.Event()
    browser, context = await _context(p, base, review=REVIEW_UNAVAILABLE, hold=hold)
    try:
        page = await context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(f"{base}/resume-agent")
        await page.wait_for_load_state("domcontentloaded")
        await page.get_by_role("button", name="优化预览").first.click()
        await page.get_by_role("button", name="内容定稿，去导出").click()
        await expect(page.get_by_role("progressbar", name="导出前质检进度")).to_be_visible()
        await expect(page.get_by_text("已完成 0/4 项", exact=False)).to_be_visible()

        assert not await _pdf_enabled(page), (
            "the download opened while the check was still running, so the result "
            "could never be read in time to matter"
        )
        skip = page.get_by_role("button", name="不等了，直接下载")
        await expect(skip).to_be_visible()
        await skip.click()
        await page.wait_for_timeout(200)
        assert await _pdf_enabled(page), (
            "the user chose not to wait and is still stuck behind the spinner"
        )

        hold.set()
        await page.wait_for_timeout(600)
        # Skip aborts the old request: its late result must be discarded.
        await expect(page.get_by_text("这次没有完成检查，不影响下载")).not_to_be_visible()
        await expect(page.get_by_role("progressbar", name="导出前质检进度")).not_to_be_visible()
        assert await _pdf_enabled(page), "the late result re-locked the download"

        assert not errors, f"page errors: {errors}"
        notes.append("hanging check: skippable, and the late result does not re-lock")
    finally:
        await browser.close()
    return notes


async def verify(base: str) -> int:
    async with async_playwright() as p:
        notes: list[str] = []
        notes += await _case_findings(p, base)
        notes += await _case_unavailable(p, base)
        notes += await _case_never_returns(p, base)
    print("PASS: the reviewer informs the export, it never withholds it")
    for note in notes:
        print(f"  {note}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:3000")
    args = parser.parse_args()
    sys.exit(asyncio.run(verify(args.base)))
