#!/usr/bin/env python3
"""Chat tool-result -> crop -> avatar upload. Isolated fixtures, no real writes/model."""

from __future__ import annotations
import asyncio
import copy
import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from lib.bootstrap import ensure_project_env

ensure_project_env()
from PIL import Image
from playwright.async_api import async_playwright, expect

spec = importlib.util.spec_from_file_location(
    "photo_fixtures", Path(__file__).with_name("verify_resume_steps.py")
)
fixtures = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fixtures
spec.loader.exec_module(fixtures)


async def run():
    base = os.environ.get("UI_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
    profile = copy.deepcopy(fixtures.PROFILE)
    rows = []
    uploads = []
    reads = []
    errors = []
    buf = io.BytesIO()
    Image.new("RGB", (900, 600), "#47aabc").save(buf, format="JPEG")
    photo = buf.getvalue()
    action = {
        "status": "photo_crop_required",
        "session_id": "session_photo",
        "profile_id": fixtures.PROFILE_ID,
        "message_id": "message_photo",
        "attachment_index": 0,
        "name": "chat-photo.jpg",
    }
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            context = await browser.new_context(
                viewport={"width": 1440, "height": 1000}, service_workers="block"
            )

            async def api(route):
                url, method = route.request.url, route.request.method
                if "/messages/message_photo/images/0" in url:
                    reads.append(url)
                    await route.fulfill(body=photo, content_type="image/jpeg")
                elif "/photo?" in url and method == "PUT":
                    uploads.append(url)
                    assert "enabled=false" in url, (
                        "must default to hidden until user chooses visibility"
                    )
                    profile["payload"]["contact"]["photo"] = {
                        "storage_key": "crop.jpg",
                        "enabled": False,
                        "download_url": base + "/fixture-photo.jpg",
                    }
                    profile["version"] += 1
                    await route.fulfill(json=profile)
                elif "/agent/sessions/" in url and url.endswith("/messages"):
                    if method == "POST":
                        result = json.dumps(action, ensure_ascii=False)
                        rows[:] = [
                            {
                                "id": "message_photo",
                                "session_id": "session_photo",
                                "role": "user",
                                "event_type": "message",
                                "content": "把聊天图片设为简历头像",
                                "created_at": "2026-10-19T08:00:00Z",
                                "payload": {},
                            },
                            {
                                "id": "tool_photo",
                                "session_id": "session_photo",
                                "role": "assistant",
                                "event_type": "tool_result",
                                "content": None,
                                "created_at": "2026-10-19T08:00:01Z",
                                "payload": {
                                    "name": "jc_profile_photo_set",
                                    "result": result,
                                },
                            },
                        ]
                        events = [
                            {
                                "type": "tool_result",
                                "name": "jc_profile_photo_set",
                                "result": result,
                            },
                            {
                                "type": "token",
                                "content": "请点击裁剪并设置头像，调整后保存。目前尚未保存。",
                            },
                            {"type": "done"},
                        ]
                        await route.fulfill(
                            headers={"Content-Type": "text/event-stream"},
                            body="".join(
                                f"data: {json.dumps(e, ensure_ascii=False)}\n\n"
                                for e in events
                            ),
                        )
                    else:
                        await route.fulfill(
                            json={"session_id": "session_photo", "messages": rows}
                        )
                elif "/agent/sessions" in url:
                    await route.fulfill(
                        json={"id": "session_photo", "kind": "resume"}
                        if method == "POST"
                        else {"sessions": []}
                    )
                elif url.endswith("/profiles/" + fixtures.PROFILE_ID):
                    await route.fulfill(json=profile)
                else:
                    await route.fulfill(json=fixtures._route_payload(url, method))

            await context.route("**/api/v1/**", api)

            async def boundary(route):
                url = route.request.url
                if "/health/" in url:
                    await route.fulfill(
                        json={"llm_enabled": True, "llm_api_key_set": True}
                    )
                elif url.endswith("/fixture-photo.jpg"):
                    await route.fulfill(body=photo, content_type="image/jpeg")
                elif url.startswith(base):
                    await route.fallback()
                else:
                    await route.abort()

            await context.route("**/*", boundary)
            page = await context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            await page.goto(base + "/resume-agent", timeout=90000)
            await page.wait_for_load_state("networkidle")
            await page.locator("textarea").first.fill("把聊天图片设为简历头像")
            await page.locator("textarea").first.press("Enter")
            button = page.get_by_role("button", name="裁剪并设置头像", exact=True)
            await expect(button).to_be_enabled(timeout=15000)
            assert not uploads
            await button.click()
            dialog = page.get_by_role("dialog", name="裁剪简历照片")
            await expect(dialog.locator("img")).to_be_visible()
            await expect(dialog.get_by_role("checkbox")).not_to_be_checked()
            await dialog.get_by_role("button", name="取消", exact=True).click()
            assert not uploads
            await button.click()
            await expect(dialog.locator("img")).to_be_visible()
            await dialog.get_by_role("button", name="保存照片", exact=True).click()
            await expect(dialog).not_to_be_visible()
            await expect(button).to_have_count(0)
            await expect(page.get_by_alt_text("简历照片").first).to_be_visible()
            assert len(uploads) == 1 and len(reads) == 2 and not errors, (
                uploads,
                reads,
                errors,
            )
            print(
                "PASS: structured MCP result -> owned-image read -> crop; cancel does not write; default hidden; explicit save uploads once and refreshes profile"
            )
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
