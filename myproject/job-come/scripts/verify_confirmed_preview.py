#!/usr/bin/env python3
"""Confirm a path edit while previewing: refresh source AND the visible draft.

All API calls are isolated fixtures; no database writes or paid model calls.
"""

from __future__ import annotations

import asyncio
import copy
import importlib.util
import json
import os
import sys
from pathlib import Path

from lib.bootstrap import ensure_project_env

ensure_project_env()
from playwright.async_api import async_playwright, expect

spec = importlib.util.spec_from_file_location(
    "preview_fixtures", Path(__file__).with_name("verify_resume_steps.py")
)
fixtures = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fixtures
spec.loader.exec_module(fixtures)

NEW_TEXT = "牵头已确认的搜索服务改造，完成关键模块交付。"


async def run():
    base = os.environ.get("UI_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
    profile = copy.deepcopy(fixtures.PROFILE)
    rows, previews, errors = [], [], []
    approved = False
    confirm = {
        "type": "confirm",
        "confirm_id": "cf_paths",
        "profile_id": fixtures.PROFILE_ID,
        "patch": {"experiences[0].highlights[0]": NEW_TEXT},
        "preview": {
            "version_before": profile["version"],
            "patch_keys": ["experiences[0].highlights[0]"],
        },
    }
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            context = await browser.new_context(
                viewport={"width": 1600, "height": 950}, service_workers="block"
            )

            async def api(route):
                nonlocal approved
                url, method = route.request.url, route.request.method
                if "/elevate/preview" in url:
                    result = copy.deepcopy(fixtures._route_payload(url.replace("/preview/stream", "/preview"), method))
                    result["draft"]["id"] = "draft_new" if approved else "draft_old"
                    previews.append(result["draft"]["id"])
                    if approved:
                        result["draft"]["sections"]["experience_blocks"][0]["bullets"][
                            0
                        ] = NEW_TEXT
                    if "/preview/stream" in url:
                        events = [
                            {"type": "progress", "stage": "read", "status": "done"},
                            {"type": "progress", "stage": "generate", "status": "running"},
                            {"type": "progress", "stage": "generate", "status": "done"},
                            {"type": "result", "data": result},
                        ]
                        await route.fulfill(content_type="text/event-stream", body="".join(
                            f"data: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events
                        ))
                    else:
                        await route.fulfill(json=result)
                elif "/agent/sessions/" in url and url.endswith("/confirm"):
                    assert route.request.post_data_json == {
                        "confirm_id": "cf_paths",
                        "approved": True,
                    }
                    approved = True
                    profile["version"] += 1
                    profile["payload"]["experiences"][0]["highlights"][0] = NEW_TEXT
                    rows.append(
                        {
                            "id": "applied",
                            "role": "assistant",
                            "event_type": "confirm_applied",
                            "payload": {"confirm_id": "cf_paths", "status": "applied"},
                        }
                    )
                    await route.fulfill(
                        json={
                            "status": "applied",
                            "confirm_id": "cf_paths",
                            "profile_id": fixtures.PROFILE_ID,
                            "version": profile["version"],
                        }
                    )
                elif "/agent/sessions/" in url and url.endswith("/messages"):
                    if method == "POST":
                        rows[:] = [
                            {
                                "id": "proposal",
                                "role": "assistant",
                                "event_type": "confirm",
                                "payload": confirm,
                            }
                        ]
                        events = [
                            confirm,
                            {"type": "token", "content": "请确认这条修改。"},
                            {"type": "done"},
                        ]
                        await route.fulfill(
                            headers={"Content-Type": "text/event-stream"},
                            body="".join(
                                f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                                for event in events
                            ),
                        )
                    else:
                        await route.fulfill(
                            json={"session_id": "preview_session", "messages": rows}
                        )
                elif "/agent/sessions" in url:
                    await route.fulfill(
                        json={"id": "preview_session", "kind": "resume"}
                        if method == "POST"
                        else {"sessions": []}
                    )
                elif url.endswith("/profiles/" + fixtures.PROFILE_ID):
                    await route.fulfill(json=profile)
                else:
                    await route.fulfill(json=fixtures._route_payload(url, method))

            await context.route("**/api/v1/**", api)

            async def boundary(route):
                if "/health/" in route.request.url:
                    await route.fulfill(
                        json={"llm_enabled": True, "llm_api_key_set": True}
                    )
                elif route.request.url.startswith(base):
                    await route.fallback()
                else:
                    await route.abort()

            await context.route("**/*", boundary)
            page = await context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            await page.goto(base + "/resume-agent", timeout=90000)
            await page.get_by_role("button", name="优化预览", exact=True).first.click()
            await expect(
                page.locator('[data-path="experiences[0].highlights[0]"]').first
            ).to_be_visible()
            assert previews and previews[-1] == "draft_old"
            await page.locator("textarea").first.fill("把这条修改到简历上")
            await page.locator("textarea").first.press("Enter")
            await page.get_by_role("button", name="确认", exact=True).click()
            bullet = page.locator('[data-path="experiences[0].highlights[0]"]').first
            await expect(bullet).to_contain_text(NEW_TEXT, timeout=15000)
            assert approved and "draft_new" in previews
            await expect(
                page.get_by_role("button", name="确认", exact=True)
            ).to_have_count(0)
            assert not errors, errors
            print(
                "PASS: path-shaped confirmation -> profile version refresh -> preview refetch -> changed bullet visible without reload"
            )
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
