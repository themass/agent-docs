#!/usr/bin/env python3
"""Real-browser UI contract check against a local built frontend, mocked API only."""

import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright, expect


async def verify(base, output):
    errors, requests = [], []
    failed = False
    job = {
        "id": "job_fixture",
        "profile_id": "profile_fixture",
        "company": "示例互联网公司",
        "title": "产品经理",
        "source_url": "https://example.com/job",
        "requirements": {},
        "fit_score": None,
        "fit_recommendation": None,
        "fit_gaps": [],
        "fit_blockers": [],
        "provenance": {
            "final_url": "https://example.com/job",
            "fetched_at": "2026-10-13T12:00:00Z",
            "method": "browser",
            "untrusted_content": True,
        },
    }
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            context = await browser.new_context(service_workers="block")

            async def route_api(route):
                url = route.request.url
                requests.append(
                    {
                        "path": url.split("/api/v1")[-1],
                        "method": route.request.method,
                        "body": route.request.post_data_json if route.request.post_data else None,
                    }
                )
                if url.endswith("/auth/context"):
                    payload = {
                        "actor": "user",
                        "user": {
                            "id": "fixture",
                            "email": "test@example.com",
                            "email_verified": True,
                            "display_name": "Test",
                        },
                        "capabilities": [],
                        "active_profile_id": "profile_fixture",
                        "merge_conflict": None,
                    }
                elif "/agent/sessions" in url:
                    payload = {"sessions": []}
                elif "/resume-tracks" in url:
                    payload = {
                        "source_locale": "zh-CN",
                        "tracks": {
                            "zh-CN": {"status": "missing"},
                            "en-US": {"status": "missing"},
                            "zh-en": {"status": "missing"},
                        },
                    }
                elif url.endswith("/notifications"):
                    payload = {"items": [], "unread_count": 0}
                elif url.endswith("/profiles"):
                    payload = {"profiles": [], "active_profile_id": "profile_fixture"}
                elif "/campaign/profiles/" in url:
                    payload = {
                        "profile_id": "profile_fixture",
                        "phase": "warmup",
                        "progress": {},
                        "warmup_job_ids": [],
                        "target_job_ids": [],
                        "fit_calibration": {"sample_size": 0, "bands": {}},
                    }
                elif "/bank" in url:
                    payload = {"questions": [], "total": 0}
                elif url.endswith("/interviews"):
                    payload = {"interviews": []}
                elif (
                    "/profiles/profile_fixture" in url
                    and "/jobs/" not in url
                    and "/coach/" not in url
                ):
                    payload = {
                        "id": "profile_fixture",
                        "status": "confirmed",
                        "version": 1,
                        "locale": "zh-CN",
                        "sources": [],
                        "payload": {
                            "contact": {"name": "示例用户"},
                            "summary": "产品经理",
                            "experiences": [],
                            "education": [],
                            "skills": [],
                            "projects": [],
                            "meta": {},
                        },
                    }
                elif url.endswith("/parse-url"):
                    if failed:
                        await route.fulfill(
                            status=400, json={"code": "unsafe_url", "message": "不允许访问私网地址"}
                        )
                        return
                    payload = job
                elif url.endswith("/fit"):
                    payload = {
                        "job_id": job["id"],
                        "score": 85,
                        "recommendation": "go",
                        "gaps": [],
                        "blockers": [],
                        "summary": "技能与目标匹配",
                    }
                else:
                    payload = []
                await route.fulfill(json=payload)

            await context.route("**/api/v1/**", route_api)

            # Block anything other than local frontend and fixture API.
            async def block_external(route):
                if "/health/" in route.request.url:
                    await route.fulfill(
                        json={
                            "llm_enabled": False,
                            "llm_api_key_set": False,
                            "llm_vision_api_key_set": False,
                            "routing_path": "fixture",
                        }
                    )
                elif route.request.url.startswith(base):
                    await route.fallback()
                else:
                    await route.abort()

            await context.route("**/*", block_external)
            page = await context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error) + " " + error.stack))
            await page.goto(base + "/jobs")
            await page.wait_for_load_state("networkidle")
            assert not errors, errors
            await page.get_by_placeholder("https://").fill("https://example.com/job")
            await page.get_by_role("checkbox").check()
            button = page.get_by_role("button", name="抓取 JD 并计算匹配")
            await button.click()
            await expect(page.get_by_text("来源：", exact=False)).to_be_visible()
            await expect(page.get_by_text("技能与目标匹配")).to_be_visible()
            parse = next(r for r in requests if r["path"].endswith("/parse-url"))
            assert parse["body"] == {"url": "https://example.com/job", "render": True, "save": True}
            await expect(button).to_be_enabled()
            output.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(output / "jobs-success.png"), full_page=True)
            failed = True
            await button.click()
            await expect(page.get_by_text("不允许访问私网地址", exact=False)).to_be_visible()
            await expect(button).to_be_enabled()
            # Other newly shipped screens must at least hydrate and show their real heading.
            screens = {}
            for path in [
                "/interviews",
                "bank",
                "applications",
                "campaign",
                "resume-agent",
                "coach-agent",
            ]:
                await page.goto(base + "/" + path.lstrip("/"))
                await page.wait_for_load_state("networkidle")
                screens[path] = await page.locator("h1").all_text_contents()
                assert not errors, (path, errors, requests[-8:])
                assert screens[path], path
            assert not errors, errors
            report = {
                "status": "passed",
                "scope": "real Chromium + built frontend; mocked API, not live Agent/DB/LLM",
                "checks": [
                    "dynamic request contract",
                    "fit result",
                    "source provenance",
                    "error recovery",
                    "screen hydration",
                ],
                "screens": screens,
                "page_errors": errors,
                "requests": requests,
            }
            (output / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            )
            print("PASS: runtime UI checks, no page errors")
        finally:
            await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:3107")
    parser.add_argument("--output", type=Path, default=Path("/tmp/jc-ui-evidence"))
    args = parser.parse_args()
    asyncio.run(verify(args.base, args.output))
