#!/usr/bin/env python3
"""Compare live SSE event timing directly and through the frontend proxy.

Usage: python scripts/diagnose_stream.py
Creates a throwaway account and fixture profiles, and makes two real model
requests. It does not access an existing user's data. Both servers must already
be running. Each probe is a different generation: timing alone is evidence,
not proof that a gateway or proxy is responsible for buffering. Frontend
progressive rendering is independently tested by verify_agent_reply.py.
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from dataclasses import dataclass, field

from lib.bootstrap import ensure_project_env

ensure_project_env()

import httpx  # noqa: E402

from jc.paths import SERVER_ROOT  # noqa: E402

RESUME_FIXTURE = SERVER_ROOT / "tests/regression_assets/resumes/sample_backend_zh.txt"

DEFAULT_MESSAGE = "请用三句话介绍一下你能帮我做什么，每句话单独一行。"


@dataclass
class Probe:
    """One timestamped SSE read."""

    label: str
    base: str
    events: list[tuple[float, str]] = field(default_factory=list)
    error: str | None = None

    @property
    def token_stamps(self) -> list[float]:
        return [t for t, kind in self.events if kind == "token"]

    @property
    def spread(self) -> float:
        stamps = self.token_stamps
        return round(stamps[-1] - stamps[0], 3) if len(stamps) > 1 else 0.0

    @property
    def verdict(self) -> str:
        n = len(self.token_stamps)
        if self.error:
            return f"ERROR {self.error}"
        if n == 0:
            return "NO TOKENS (run failed or produced only an error event)"
        if n == 1:
            return "SINGLE CHUNK -- whole answer arrived at once"
        if self.spread < 0.5:
            return f"{n} tokens but spread {self.spread}s -- effectively one chunk"
        return f"{n} tokens over {self.spread}s -- real increments"


def _authenticate(client: httpx.Client, email: str, password: str) -> None:
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    if resp.status_code == 409:
        resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    resp.raise_for_status()


def _upload_profile(client: httpx.Client) -> str:
    resp = client.post(
        "/api/v1/profiles/upload",
        files={"file": ("resume.txt", RESUME_FIXTURE.read_bytes(), "text/plain")},
    )
    resp.raise_for_status()
    return str(resp.json()["id"])


def _open_session(client: httpx.Client, profile_id: str) -> str:
    resp = client.post(
        "/api/v1/agent/sessions",
        json={"profile_id": profile_id, "kind": "resume", "skill_hint": "resume-coach"},
    )
    resp.raise_for_status()
    return str(resp.json()["id"])


def probe(base: str, label: str, cookies: httpx.Cookies, message: str, timeout: float) -> Probe:
    """Stream one message and timestamp each `data:` line as it arrives."""
    result = Probe(label=label, base=base)
    # `httpx.Client.stream` + `iter_lines` is the only shape that preserves
    # arrival order here: `client.post(...)` would read the whole body first and
    # make every probe look like a single chunk regardless of the truth. (The
    # same trap as httpx's ASGITransport, which joins `body_parts`.)
    try:
        with httpx.Client(base_url=base, cookies=cookies, timeout=timeout) as c:
            profile_id = _upload_profile(c)
            session_id = _open_session(c, profile_id)
            t0 = time.monotonic()
            with c.stream(
                "POST",
                f"/api/v1/agent/sessions/{session_id}/messages",
                json={"content": message, "attachments": [], "reply_locale": "zh-CN"},
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    stamp = round(time.monotonic() - t0, 3)
                    try:
                        payload = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    kind = str(payload.get("type") or "?")
                    result.events.append((stamp, kind))
    except Exception as exc:  # noqa: BLE001
        result.error = f"{type(exc).__name__}: {exc}"
    return result


def _print_probe(p: Probe) -> None:
    print(f"\n=== {p.label} ({p.base}) ===")
    if p.error:
        print(f"  {p.error}")
        return
    if not p.events:
        print("  no SSE events at all")
        return
    print(f"  {len(p.events)} events, first at {p.events[0][0]}s, last at {p.events[-1][0]}s")
    counts: dict[str, int] = {}
    for _, kind in p.events:
        counts[kind] = counts.get(kind, 0) + 1
    print("  by type: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    stamps = p.token_stamps
    if stamps:
        shown = stamps[:12]
        gaps = [round(b - a, 3) for a, b in zip(stamps, stamps[1:])][:11]
        print(f"  token arrival: {shown}{' ...' if len(stamps) > 12 else ''}")
        print(f"  gaps: {gaps}")
    print(f"  VERDICT: {p.verdict}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--api", default="http://127.0.0.1:8001", help="FastAPI origin")
    ap.add_argument("--web", default="http://127.0.0.1:3000", help="next dev origin")
    ap.add_argument("--message", default=DEFAULT_MESSAGE)
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument(
        "--skip-proxy",
        action="store_true",
        help="only probe the API directly (use when next dev is not running)",
    )
    args = ap.parse_args()

    if not RESUME_FIXTURE.exists():
        print(f"missing fixture: {RESUME_FIXTURE}")
        return 2

    email = f"stream-probe-{uuid.uuid4().hex[:10]}@example.com"
    password = "Probe!2345"

    # Both probes use the same account and fixture, but independent sessions.
    with httpx.Client(base_url=args.api, timeout=60.0) as c:
        try:
            _authenticate(c, email, password)
        except Exception as exc:  # noqa: BLE001
            print(f"cannot reach the API at {args.api}: {type(exc).__name__}: {exc}")
            print("start it with ./scripts/dev.sh first")
            return 2
        cookies = c.cookies

    probes = [probe(args.api, "direct (FastAPI)", cookies, args.message, args.timeout)]
    if not args.skip_proxy:
        probes.append(probe(args.web, "proxied (next dev)", cookies, args.message, args.timeout))

    for p in probes:
        _print_probe(p)

    print("\n=== observation (not a root-cause verdict) ===")
    if any(p.error for p in probes):
        print("At least one request failed; timing comparison is inconclusive.")
        return 1
    if any(not p.token_stamps for p in probes):
        print("At least one run produced no text. Inspect its session trace before diagnosing buffering.")
        return 1
    for p in probes:
        print(f"{p.label}: {p.verdict}")
    print("These are independent generations; repeat before attributing differences to the proxy.")
    print("Streaming transport and visible typing are separate checks; run verify_agent_reply.py for the latter.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
