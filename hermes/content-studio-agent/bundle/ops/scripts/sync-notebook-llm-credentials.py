#!/usr/bin/env python3
"""Update Open Notebook openai_compatible credentials to use the local LLM proxy."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def _request(method: str, url: str, body: dict | None = None) -> list | dict:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:5055")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument(
        "--providers",
        default="openai_compatible,openai",
        help="Comma-separated provider names to patch",
    )
    args = parser.parse_args()
    base = args.api_url.rstrip("/")
    api_base = f"{base}/api"
    targets = {p.strip() for p in args.providers.split(",") if p.strip()}

    try:
        credentials = _request("GET", f"{api_base}/credentials")
    except urllib.error.URLError as exc:
        print(f"failed to list credentials: {exc}", file=sys.stderr)
        return 1

    if not isinstance(credentials, list):
        print("unexpected /credentials response", file=sys.stderr)
        return 1

    updated = 0
    for cred in credentials:
        provider = cred.get("provider", "")
        if provider not in targets:
            continue
        name = cred.get("name", "")
        existing_base = (cred.get("base_url") or "").lower()
        # Do not overwrite TTS proxy credentials (ali-tts on :8969).
        if "tts" in name.lower() or ":8969" in existing_base:
            print(f"skip TTS credential {name}")
            continue
        cred_id = cred.get("id")
        if not cred_id:
            continue
        payload = {
            "api_key": args.api_key,
            "base_url": args.base_url,
        }
        if name:
            payload["name"] = name
        try:
            _request("PUT", f"{api_base}/credentials/{cred_id}", payload)
            print(f"updated credential {name} ({cred_id}) → {args.base_url}")
            updated += 1
        except urllib.error.HTTPError as exc:
            print(f"skip {cred_id}: HTTP {exc.code}", file=sys.stderr)

    if updated == 0:
        print("no matching credentials updated", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
