#!/usr/bin/env python3
r"""Concurrent users, mid-stream cancel, and restart recovery against a live API.

This is the one V1 acceptance item that had no script at all. The other three
(dynamic browser, document parsing, export regression) already had partial or full
coverage; this one was a genuine gap because it needs several real users hitting a
real running process at the same time, which no existing script attempted.

Three independent checks, each answering a question that only matters once ADR-004's
identity-passing fix (authz_attributes, not env vars / a process-wide lock) is live:

1. **Cross-user isolation** — N distinct logged-in users each send one agent message
   at roughly the same instant. If any user's request is silently queued behind
   another user's run (the old `_HARNESS_RUN_LOCK` symptom), that user's
   wall-clock latency will be visibly inflated relative to a solo baseline. This
   script measures a solo baseline latency first, then re-measures the same request
   under concurrency; a solo-to-concurrent latency ratio much above 1.5x for any
   user is reported as a likely serialization regression, not proof by itself, but
   the right first signal to check by hand if it fires.
2. **Mid-stream cancel leaves no dangling state** — start a long-ish agent turn,
   cancel it after a couple seconds (same technique as `agent_e2e.sh`, run against a
   *second*, otherwise-idle session to isolate the cancel from the concurrency
   check), then confirm a fresh message on the *same* session completes normally
   afterward (i.e. cancelling user A's turn must not wedge that session).
3. **Restart recovery** — this script does NOT restart the server itself (it has no
   business managing your process manager); it creates a session and sends one
   message, then pauses and asks you to restart the API process, then on resume
   confirms the session and its message history are still readable afterward and
   that a brand new message on that same session still completes. This is the one
   manual step in an otherwise unattended script.

Usage:
    export JC_E2E_BASE=http://127.0.0.1:8000/api/v1
    python scripts/verify_concurrency_resilience.py --users 5
    # add --skip-restart to run only checks 1 and 2 unattended
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from lib.bootstrap import ensure_project_env

PROJECT_ROOT = ensure_project_env()
SERVER_ROOT = PROJECT_ROOT / "backend" / "server"

import httpx  # noqa: E402

RESUME_FIXTURE = SERVER_ROOT / "tests/regression_assets/resumes/sample_backend_zh.txt"
PROMPT = "请读取我的档案并逐条点评工作经历，尽量详细，给出具体修改建议"


@dataclass
class UserContext:
    label: str
    client: httpx.Client
    profile_id: str
    session_id: str


def make_user(base: str, label: str) -> UserContext:
    client = httpx.Client(base_url=base, timeout=120.0)
    email = f"jc-concurrency-{uuid.uuid4().hex[:10]}@example.com"
    password = "Verify-Concurrency-1!"
    resp = client.post("/auth/register", json={"email": email, "password": password})
    resp.raise_for_status()

    resume_bytes = RESUME_FIXTURE.read_bytes()
    upload = client.post("/profiles/upload", files={"file": ("resume.txt", resume_bytes, "text/plain")})
    upload.raise_for_status()
    profile_id = upload.json()["id"]

    session_resp = client.post(
        "/agent/sessions",
        json={"profile_id": profile_id, "skill_hint": "resume-coach", "kind": "resume"},
    )
    session_resp.raise_for_status()
    session_id = session_resp.json()["id"]
    return UserContext(label=label, client=client, profile_id=profile_id, session_id=session_id)


def send_message(ctx: UserContext, content: str) -> tuple[float, list[dict]]:
    start = time.monotonic()
    events: list[dict] = []
    with ctx.client.stream(
        "POST",
        f"/agent/sessions/{ctx.session_id}/messages",
        json={"content": content},
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload:
                events.append(json.loads(payload))
    elapsed = time.monotonic() - start
    return elapsed, events


def check_isolation(base: str, n_users: int) -> bool:
    print(f"\n=== 1. Cross-user isolation ({n_users} concurrent users) ===")
    users = [make_user(base, f"user{i}") for i in range(n_users)]
    print(f"  created {n_users} isolated users/sessions")

    baseline_user = users[0]
    baseline_elapsed, baseline_events = send_message(baseline_user, PROMPT)
    if not any(e.get("type") == "done" for e in baseline_events):
        print(f"  FAIL: baseline solo request never completed (events={[e.get('type') for e in baseline_events]})")
        return False
    print(f"  solo baseline latency (user0): {baseline_elapsed:.1f}s")

    results: dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=n_users) as pool:
        futures = {pool.submit(send_message, u, PROMPT): u.label for u in users}
        for future in as_completed(futures):
            label = futures[future]
            elapsed, events = future.result()
            ok = any(e.get("type") == "done" for e in events)
            results[label] = elapsed
            status = "done" if ok else f"NO DONE EVENT ({[e.get('type') for e in events]})"
            print(f"  {label}: {elapsed:.1f}s concurrent -- {status}")
            if not ok:
                print(f"  FAIL: {label} did not complete")
                return False

    worst_ratio = max(results.values()) / baseline_elapsed if baseline_elapsed > 0 else 0
    print(f"  worst concurrent/solo latency ratio: {worst_ratio:.2f}x")
    if worst_ratio > 1.5:
        print(
            "  FAIL: a concurrent request took >1.5x the solo baseline -- "
            "check for cross-user serialization (ADR-004 regression)"
        )
        return False
    print("  PASS: all users completed with no signs of cross-user queuing")
    return True


def check_cancel_recovery(base: str) -> bool:
    print("\n=== 2. Mid-stream cancel leaves the session usable ===")
    ctx = make_user(base, "cancel-probe")
    client = ctx.client

    events: list[dict] = []
    with client.stream(
        "POST", f"/agent/sessions/{ctx.session_id}/messages", json={"content": PROMPT}
    ) as resp:
        resp.raise_for_status()
        start = time.monotonic()
        for line in resp.iter_lines():
            if time.monotonic() - start > 2.0:
                client.post(f"/agent/sessions/{ctx.session_id}/cancel")
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload:
                events.append(json.loads(payload))
    print(f"  cancelled stream; event types observed: {[e.get('type') for e in events]}")

    open_tools: list[str] = []
    for e in events:
        if e.get("type") == "tool_start":
            open_tools.append(e.get("name") or "tool")
        elif e.get("type") in {"tool_result", "tool"} and open_tools:
            open_tools.pop()
    if open_tools:
        print(f"  FAIL: cancel left dangling tool_start without tool_result: {open_tools}")
        return False

    print("  sending a fresh message on the same (cancelled) session ...")
    elapsed, followup_events = send_message(ctx, "你好，刚才那个先不管，简单打个招呼")
    if not any(e.get("type") == "done" for e in followup_events):
        print(
            f"  FAIL: session is wedged after cancel -- follow-up never completed "
            f"(events={[e.get('type') for e in followup_events]})"
        )
        return False
    print(f"  PASS: session recovered after cancel, follow-up completed in {elapsed:.1f}s")
    return True


def check_restart_recovery(base: str) -> bool:
    print("\n=== 3. Restart recovery (manual step) ===")
    ctx = make_user(base, "restart-probe")
    elapsed, events = send_message(ctx, "你好，请记住这句话：restart-recovery-probe")
    if not any(e.get("type") == "done" for e in events):
        print(f"  FAIL: pre-restart message never completed (events={[e.get('type') for e in events]})")
        return False
    print(f"  pre-restart message completed in {elapsed:.1f}s, session_id={ctx.session_id}")

    print(
        "\n  >>> Now restart the API process (Ctrl+C and re-run ./scripts/dev.sh, "
        "or your usual restart command). <<<"
    )
    input("  Press Enter once the API is back up and responding to /health ...")

    history = ctx.client.get(f"/agent/sessions/{ctx.session_id}/messages")
    if history.status_code != 200:
        print(f"  FAIL: session history unreachable after restart (status={history.status_code})")
        return False
    messages = history.json().get("messages", [])
    if not messages:
        print("  FAIL: session history is empty after restart (persistence did not survive restart)")
        return False
    print(f"  session history readable after restart: {len(messages)} messages")

    elapsed2, events2 = send_message(ctx, "再确认一下，你还记得刚才那句话吗？")
    if not any(e.get("type") == "done" for e in events2):
        print(f"  FAIL: post-restart message never completed (events={[e.get('type') for e in events2]})")
        return False
    print(f"  PASS: session usable after restart, new message completed in {elapsed2:.1f}s")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=os.environ.get("JC_E2E_BASE", "http://127.0.0.1:8000/api/v1"))
    parser.add_argument("--users", type=int, default=5, help="Concurrent users for the isolation check")
    parser.add_argument("--skip-restart", action="store_true", help="Skip the manual restart-recovery step")
    parser.add_argument("--output", type=Path, default=Path("docs/evidence/concurrency-resilience.json"))
    args = parser.parse_args()

    try:
        outcomes = {}
        outcomes["isolation"] = check_isolation(args.base, args.users)
        outcomes["cancel_recovery"] = check_cancel_recovery(args.base)
        if not args.skip_restart:
            outcomes["restart_recovery"] = check_restart_recovery(args.base)
        else:
            print("\n=== 3. Restart recovery: skipped (--skip-restart) ===")
    except httpx.ConnectError as exc:
        print(f"FAIL: cannot reach {args.base}: {exc}", file=sys.stderr)
        print("Start the API first (./scripts/dev.sh) and confirm --base.", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(outcomes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n" + "=" * 60)
    failed = [name for name, ok in outcomes.items() if not ok]
    if failed:
        print(f"FAIL: {', '.join(failed)}")
        return 1
    print(f"PASS: all {len(outcomes)} checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
