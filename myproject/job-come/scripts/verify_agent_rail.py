#!/usr/bin/env python3
"""Does collapsing 舟卡 give the document its space back without losing the run?

The agent sidebar is ~440px of the studio. On the review and export steps the user is
reading the document, not talking to the assistant, so the rail collapses to a 44px
strip. The part that needs a test is not the width -- it is what collapsing does to an
*in-flight* run.

`useAgentSession` aborts its request on unmount and owns the SSE stream. If the sidebar
were unmounted on collapse, collapsing would silently cancel a run the user started and
throw away the streamed reply. Nothing about the UI would look broken; the answer would
just never arrive. So the panel is hidden rather than unmounted, and that is asserted
here against a real stream rather than trusted to a code comment.

Usage:
    python scripts/verify_agent_rail.py --base http://127.0.0.1:3000
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import sys
from pathlib import Path

from lib.bootstrap import ensure_project_env

ensure_project_env()

from playwright.async_api import async_playwright  # noqa: E402

# Reuse the API fixtures so this script and the step verifier cannot drift apart.
_SPEC = importlib.util.spec_from_file_location(
    "verify_resume_steps", str(Path(__file__).with_name("verify_resume_steps.py"))
)
assert _SPEC and _SPEC.loader
_VRS = importlib.util.module_from_spec(_SPEC)
sys.modules["verify_resume_steps"] = _VRS
_SPEC.loader.exec_module(_VRS)

COLLAPSE_LABEL = "收起舟卡，把空间让给简历"
REPLY_TEXT = "改完了"

_STATE_PROBE = """() => {
  const rail = document.querySelector('.agent-rail-collapsed');
  const sidebar = Array.from(document.querySelectorAll('aside'))
    .find((e) => e.style.width);
  const box = (e) => (e ? Math.round(e.getBoundingClientRect().width) : null);
  // The document pane is the split's own left <section>, reached through the sidebar
  // so it cannot be confused with a nested scroll area.
  const doc = sidebar
    ? sidebar.parentElement.querySelector(':scope > section')
    : null;
  const label = rail ? rail.querySelector('.agent-rail-label') : null;
  return {
    railPresent: !!rail,
    railWidth: box(rail),
    // Mounted but not painted is the whole point: see the module docstring.
    sidebarMounted: !!sidebar,
    sidebarWidth: box(sidebar),
    // The composer is inside the sidebar, so finding it proves the subtree is alive.
    composerAlive: !!document.querySelector('textarea'),
    // Not <main>: it spans the whole shell and is the same width either way.
    docWidth: box(doc),
    separators: document.querySelectorAll('[role=separator]').length,
    label: label ? label.textContent.trim() : null,
    aria: rail ? rail.getAttribute('aria-label') : null,
    cueRunning: !!(rail && rail.querySelector('.animate-nudge-x')),
    labelFits: label && rail
      ? label.getBoundingClientRect().width <= rail.getBoundingClientRect().width
      : null,
  };
}"""


async def verify(base: str) -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            context = await browser.new_context(
                viewport={"width": 1600, "height": 950},
                device_scale_factor=2,
                service_workers="block",
            )
            # Held until we have collapsed, so the run is genuinely still in flight.
            release = asyncio.Event()

            async def route_api(route):
                url = route.request.url
                method = route.request.method
                if "/agent/sessions/" in url and url.endswith("/messages") \
                        and method == "POST":
                    await release.wait()
                    await route.fulfill(
                        status=200,
                        headers={"Content-Type": "text/event-stream"},
                        body=(
                            'data: {"type":"token","content":"'
                            + REPLY_TEXT
                            + '"}\n\n'
                            'data: {"type":"done"}\n\n'
                        ),
                    )
                    return
                if "/agent/sessions" in url and method == "POST":
                    await route.fulfill(json={"id": "sess_fixture", "kind": "resume"})
                    return
                # `sendMessage` reconciles with the server after the stream ends
                # (`listAgentMessages`), so the reply must exist there too, in the
                # real shape (`AgentMessageRecord[]`) -- not the catch-all session-list
                # fixture below, which `"/agent/sessions" in url` would otherwise also
                # match and hand back `{"sessions": []}` for a path that actually wants
                # `{"session_id", "messages"}`. Mismatched shape throws inside
                # `recordsToDisplayItems`, which silently drops the just-arrived reply
                # from `assistantCount` and is what originally made the unread badge
                # look broken when the UI code was not.
                if (
                    "/agent/sessions/" in url
                    and url.endswith("/messages")
                    and method == "GET"
                ):
                    await route.fulfill(
                        json={
                            "session_id": "sess_fixture",
                            "messages": [
                                {
                                    "id": "msg_user",
                                    "session_id": "sess_fixture",
                                    "role": "user",
                                    "event_type": "message",
                                    "content": "把华为那段写具体一点",
                                    "payload": None,
                                    "created_at": "2026-01-01T00:00:00Z",
                                },
                                {
                                    "id": "msg_assistant",
                                    "session_id": "sess_fixture",
                                    "role": "assistant",
                                    "event_type": "message",
                                    "content": REPLY_TEXT,
                                    "payload": None,
                                    "created_at": "2026-01-01T00:00:01Z",
                                },
                            ],
                        }
                    )
                    return
                await route.fulfill(json=_VRS._route_payload(url, method))

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
            page = await context.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            await page.goto(f"{base}/resume-agent")
            await page.wait_for_load_state("networkidle")

            expanded = await page.evaluate(_STATE_PROBE)
            assert not expanded["railPresent"], "the rail should start expanded"
            assert expanded["sidebarWidth"] and expanded["sidebarWidth"] > 300, (
                f"the expanded sidebar is only {expanded['sidebarWidth']}px"
            )
            assert expanded["separators"] == 1, "the expanded panel needs its drag handle"

            # Start a run, then collapse mid-flight.
            composer = page.locator("textarea").first
            await composer.fill("把华为那段写具体一点")
            await composer.press("Enter")
            await page.wait_for_timeout(300)
            await page.get_by_role("button", name=COLLAPSE_LABEL).first.click()
            await page.wait_for_timeout(400)

            busy = await page.evaluate(_STATE_PROBE)
            assert busy["railPresent"], "collapsing did not produce the rail"
            assert busy["railWidth"] <= 48, (
                f"the collapsed rail is {busy['railWidth']}px; it is meant to be a strip"
            )
            assert busy["labelFits"], (
                "the vertical label is wider than the strip, so the strip cannot stay "
                "narrow -- check that it still uses `writing-mode`, not `rotate()`"
            )
            # The invariant this script exists for.
            assert busy["sidebarMounted"] and busy["composerAlive"], (
                "the sidebar was unmounted on collapse, which aborts the in-flight run "
                "and discards the streamed reply"
            )
            assert busy["sidebarWidth"] == 0, (
                "the sidebar is still taking layout space while collapsed, so the "
                "document gained nothing"
            )
            assert busy["separators"] == 0, (
                "a resize handle is still present next to a 44px strip, which is a "
                "false affordance"
            )
            assert busy["docWidth"] > expanded["docWidth"], (
                f"the document is {busy['docWidth']}px collapsed vs "
                f"{expanded['docWidth']}px expanded; collapsing must give space back"
            )
            # A run in flight is its own reason to reopen, so the idle cue stands down.
            assert not busy["cueRunning"], (
                "the attention cue is animating next to a busy indicator; they compete"
            )
            assert "正在处理" in (busy["label"] or ""), (
                f"the collapsed strip does not say a run is going: {busy['label']!r}"
            )

            # Let the reply land while still collapsed.
            release.set()
            await page.wait_for_timeout(1200)
            unread = await page.evaluate(_STATE_PROBE)
            assert "新回复" in (unread["label"] or ""), (
                f"a reply arrived while collapsed and the strip does not say so: "
                f"{unread['label']!r}"
            )
            assert "1 条新回复" in (unread["aria"] or ""), (
                f"the unread count is not in the accessible name: {unread['aria']!r}"
            )

            # Reopen: the streamed reply must still be in the thread.
            await page.locator(".agent-rail-collapsed").first.click()
            await page.wait_for_timeout(500)
            survived = await page.evaluate(
                "(t) => document.body.innerText.includes(t)", REPLY_TEXT
            )
            assert survived, (
                "the reply that streamed while collapsed is not in the reopened thread"
            )

            # Collapsing after reading must clear the badge, or it means nothing.
            await page.get_by_role("button", name=COLLAPSE_LABEL).first.click()
            await page.wait_for_timeout(400)
            read = await page.evaluate(_STATE_PROBE)
            assert "新回复" not in (read["label"] or ""), (
                f"the unread badge survived being read: {read['label']!r}"
            )

            assert not errors, f"page errors: {errors}"
            print("PASS: 舟卡 collapses to a strip without losing the run")
            print(
                f"  document {expanded['docWidth']}px expanded -> "
                f"{busy['docWidth']}px collapsed "
                f"(+{busy['docWidth'] - expanded['docWidth']}px)"
            )
            print(f"  collapsed strip {busy['railWidth']}px, sidebar stays mounted")
            print("  states: 正在处理 -> 有新回复 -> read, badge cleared")
            return 0
        finally:
            await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:3000")
    args = parser.parse_args()
    sys.exit(asyncio.run(verify(args.base)))
