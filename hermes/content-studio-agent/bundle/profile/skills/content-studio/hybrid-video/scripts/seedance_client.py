#!/usr/bin/env python3
"""Volcengine Seedance provider boundary for hybrid-video.

This v1 client intentionally does not embed a volatile Volcengine payload.
It validates configuration and returns a structured "unavailable" result so
the hybrid pipeline can safely fallback to cards until credentials and model
IDs are confirmed.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path


REQUIRED_ENV = (
    "VOLCENGINE_ACCESS_KEY_ID",
    "VOLCENGINE_SECRET_ACCESS_KEY",
    "VOLCENGINE_SEEDANCE_MODEL",
)


class ProviderUnavailable(RuntimeError):
    """Raised when Seedance cannot be used and fallback should be applied."""


@dataclass
class ProviderStatus:
    available: bool
    reason: str
    provider: str = "volcengine_seedance"


def check_provider() -> ProviderStatus:
    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    if missing:
        return ProviderStatus(
            available=False,
            reason="missing env: " + ", ".join(missing),
        )
    return ProviderStatus(
        available=False,
        reason=(
            "Seedance credentials are present, but the concrete API payload is not "
            "enabled in this local client yet. Confirm the exact Volcengine endpoint "
            "and model id before enabling real generation."
        ),
    )


def generate_ai_broll(
    *,
    prompt: str,
    negative_prompt: str,
    output_path: Path,
    duration_seconds: float,
    aspect_ratio: str = "9:16",
    mode: str = "text_to_video",
) -> Path:
    """Generate an AI b-roll clip or raise `ProviderUnavailable`.

    Args:
        prompt: Positive visual prompt.
        negative_prompt: Negative prompt.
        output_path: Expected generated clip path.
        duration_seconds: Desired duration.
        aspect_ratio: Output aspect ratio.
        mode: Provider mode such as `text_to_video`.

    Returns:
        Path to generated media.

    Raises:
        ProviderUnavailable: If Seedance is not configured or not enabled.
    """
    status = check_provider()
    if not status.available:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        request_path = output_path.with_suffix(".seedance-request.json")
        request_path.write_text(
            json.dumps(
                {
                    "provider": status.provider,
                    "available": status.available,
                    "reason": status.reason,
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "duration_seconds": duration_seconds,
                    "aspect_ratio": aspect_ratio,
                    "mode": mode,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        raise ProviderUnavailable(status.reason)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()

    if args.smoke_test:
        status = check_provider()
        print(json.dumps(asdict(status), ensure_ascii=False, indent=2))
        return 0

    parser.error("Only --smoke-test is supported by the v1 CLI.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
