#!/usr/bin/env python3
"""Ensure Open Notebook speaker profiles use unique OpenAI voice_id values.

podcast_creator requires unique voice_id per speaker in a profile. Ali TTS proxy
maps these OpenAI names to Ali NLS voices — do NOT collapse all to 'nova'.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

# Canonical defaults (unique per speaker). Proxy maps each to a distinct Ali NLS voice.
CANONICAL_VOICES: dict[str, list[str]] = {
    "business_panel": ["echo", "shimmer", "ash"],
    "solo_expert": ["nova"],
    "tech_experts": ["nova", "alloy"],
}

_OPENAI_VOICES = frozenset(
    {
        "alloy",
        "ash",
        "ballad",
        "coral",
        "echo",
        "fable",
        "onyx",
        "nova",
        "sage",
        "shimmer",
        "verse",
        "default",
    }
)


def _get(url: str) -> list | dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


def _put(url: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="PUT"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _assign_unique_voices(profile_name: str, speakers: list[dict]) -> tuple[list[dict], bool]:
    """Return speakers with unique OpenAI voice_id values."""
    pool = list(CANONICAL_VOICES.get(profile_name, ["nova", "echo", "shimmer", "alloy"]))
    if len(pool) < len(speakers):
        pool.extend(["fable", "onyx", "shimmer", "echo", "ash", "alloy"])

    voice_ids = [str(s.get("voice_id", "")).strip().lower() for s in speakers]
    needs_fix = len(voice_ids) != len(set(voice_ids)) or any(
        v not in _OPENAI_VOICES for v in voice_ids
    )
    if not needs_fix:
        return speakers, False

    new_speakers = []
    for i, sp in enumerate(speakers):
        sp = dict(sp)
        sp["voice_id"] = pool[i % len(pool)]
        new_speakers.append(sp)
    return new_speakers, True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:5055")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    base = args.api_url.rstrip("/")

    try:
        profiles = _get(f"{base}/api/speaker-profiles")
    except urllib.error.URLError as exc:
        print(f"failed to list speaker profiles: {exc}", file=sys.stderr)
        return 1

    updated = 0
    for profile in profiles:
        name = profile.get("name", "")
        speakers = profile.get("speakers") or []
        new_speakers, changed = _assign_unique_voices(name, speakers)
        if not changed:
            continue
        for old, new in zip(speakers, new_speakers):
            if old.get("voice_id") != new.get("voice_id"):
                print(f"  {name}: {old.get('name')} {old.get('voice_id')} -> {new.get('voice_id')}")
        payload = {
            "name": name,
            "description": profile.get("description", ""),
            "voice_model": profile.get("voice_model"),
            "speakers": new_speakers,
            "tts_provider": profile.get("tts_provider"),
            "tts_model": profile.get("tts_model"),
        }
        if args.dry_run:
            updated += 1
            continue
        _put(f"{base}/api/speaker-profiles/{profile['id']}", payload)
        updated += 1

    print(f"updated {updated} speaker profile(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
