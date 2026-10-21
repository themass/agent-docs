#!/usr/bin/env python3
"""Browser regression for burst-token typing, formatting and visible patch confirmation.

Uses the running frontend with intercepted API fixtures. No model calls, database
writes or existing browser profile. Run: python scripts/verify_agent_reply.py
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

spec = importlib.util.spec_from_file_location("resume_fixtures", Path(__file__).with_name("verify_resume_steps.py"))
assert spec and spec.loader
fixtures = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fixtures
spec.loader.exec_module(fixtures)

REPLY = "## 修改建议\n\n已按已有事实整理，**没有新增指标**。\n\n1. 主导订单服务改造，明确负责范围与交付动作。 2. 搭建统一配置中心，说明协作方式与实际贡献。 3. 参与容量保障，保留档案已有的业务指标。\n\n请确认后保存，未确认前不会写入简历。"
PATCH_TEXT = "牵头订单链路改造，明确负责范围与交付动作。"


async def run(base: str, reduced_motion: bool = False) -> None:
    profile = copy.deepcopy(fixtures.PROFILE)
    rows = []
    confirmations = []
    errors = []
    applied = False

    def row(id_, role, kind, content=None, payload=None):
        return dict(id=id_, session_id="sess_reply", role=role, event_type=kind,
                    content=content, payload=payload, created_at="2026-10-19T12:00:00+08:00")

    confirm = dict(type="confirm", confirm_id="cf_reply", profile_id=fixtures.PROFILE_ID,
                   patch={"experiences": [{**profile["payload"]["experiences"][0], "highlights": [PATCH_TEXT]}]},
                   preview={"patch_keys": ["experiences"], "version_before": profile["version"]})

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            context = await browser.new_context(viewport={"width": 1600, "height": 950}, service_workers="block",
                                                reduced_motion="reduce" if reduced_motion else "no-preference")

            async def api(route):
                nonlocal applied
                url, method = route.request.url, route.request.method
                if "/agent/sessions/" in url and url.endswith("/confirm"):
                    data = route.request.post_data_json
                    confirmations.append(data)
                    assert data == {"confirm_id": "cf_reply", "approved": True}, data
                    applied = True
                    profile["payload"]["experiences"] = confirm["patch"]["experiences"]
                    profile["version"] += 1
                    # Preserve the real proposal: history must reconcile its terminal
                    # status rather than making a pending button reappear on reload.
                    rows.append(row("applied_reply", "assistant", "confirm_applied", payload={
                        "confirm_id": "cf_reply", "profile_id": fixtures.PROFILE_ID,
                        "version": profile["version"], "status": "applied"}))
                    await route.fulfill(json={"status": "applied", "confirm_id": "cf_reply",
                                             "profile_id": fixtures.PROFILE_ID, "version": profile["version"]})
                    return
                if "/agent/sessions/" in url and url.endswith("/messages"):
                    if method == "POST":
                        message = route.request.post_data_json["content"]
                        rows[:] = [row("u_reply", "user", "message", message),
                                   row("cf_reply", "assistant", "confirm", payload=confirm),
                                   row("a_reply", "assistant", "message", REPLY)]
                        # All tokens AND done arrive in the same HTTP body. This is
                        # the worst-case batching that used to bypass the typing UI.
                        events = [dict(type="token", content=REPLY), confirm, dict(type="done")]
                        await route.fulfill(headers={"Content-Type": "text/event-stream"},
                                            body="".join(f"data: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events))
                    else:
                        await route.fulfill(json={"session_id": "sess_reply", "messages": rows})
                    return
                if "/agent/sessions" in url:
                    await route.fulfill(json={"id": "sess_reply", "kind": "resume"} if method == "POST" else {"sessions": []})
                    return
                if url.endswith(f"/profiles/{fixtures.PROFILE_ID}"):
                    await route.fulfill(json=profile)
                    return
                await route.fulfill(json=fixtures._route_payload(url, method))

            await context.route("**/api/v1/**", api)
            async def boundary(route):
                if "/health/" in route.request.url:
                    await route.fulfill(json={"llm_enabled": True, "llm_api_key_set": True, "llm_vision_api_key_set": True})
                elif route.request.url.startswith(base):
                    await route.fallback()
                else:
                    await route.abort()
            await context.route("**/*", boundary)
            page = await context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            # Capture DOM lengths every frame, before the burst response can arrive.
            await page.add_init_script("""window.replySamples=[];
              function sample(){const e=document.querySelector('[data-assistant-reply]');
                if(e) window.replySamples.push({n:e.textContent.length,typing:e.dataset.typing});
                requestAnimationFrame(sample);} requestAnimationFrame(sample);""")
            await page.goto(f"{base}/resume-agent", timeout=90000)
            await page.wait_for_load_state("networkidle")
            await page.locator("textarea").first.fill("请修改到简历上")
            await page.locator("textarea").first.press("Enter")
            reply = page.locator("[data-assistant-reply]").last
            await expect(reply).to_have_attribute("data-typing", "false", timeout=15000)
            await expect(reply.locator("h3")).to_have_text("修改建议")
            await expect(reply.locator("ol > li")).to_have_count(3)
            await expect(reply.locator("strong")).to_have_text("没有新增指标")
            samples = await page.evaluate("window.replySamples")
            lengths = sorted(set(s["n"] for s in samples))
            if not reduced_motion:
                assert len(lengths) >= 4, f"no progressive output: {lengths}"
                assert lengths[-1] > lengths[0] + 20, lengths
            assert not await page.get_by_text("已完成", exact=False).count(), "successful activity disclosure returned"
            await expect(page.get_by_text("这条修改还没有保存到简历", exact=False)).to_be_visible()
            await page.get_by_role("button", name="确认", exact=True).click()
            await expect(page.get_by_text(PATCH_TEXT, exact=True).first).to_be_visible()
            assert applied and len(confirmations) == 1
            await expect(page.get_by_role("button", name="确认", exact=True)).to_have_count(0)
            # Replay server history: content must appear immediately, with no animation.
            await page.reload()
            await expect(page.locator("[data-assistant-reply]").last).to_have_attribute("data-typing", "false")
            await expect(page.locator("[data-assistant-reply] ol > li")).to_have_count(3)
            await expect(page.get_by_role("button", name="确认", exact=True)).to_have_count(0)
            assert not errors, errors
            print(f"PASS ({'reduced motion' if reduced_motion else 'normal motion'}): {len(lengths)} distinct text lengths; Markdown heading/list/bold; visible confirm; profile refreshed; history not replayed")
        finally:
            await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:3000")
    base = parser.parse_args().base
    asyncio.run(run(base))
    asyncio.run(run(base, reduced_motion=True))
