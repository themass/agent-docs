#!/usr/bin/env python3
"""Compose hybrid-video clips into a v1 visual-only mp4."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


def load_spec(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text)
    return json.loads(text)


def compose(spec_path: Path) -> Path:
    spec = load_spec(spec_path)
    metadata = spec["metadata"]
    asset_dir = Path(metadata["asset_dir"])
    output_video = Path(metadata["output_video"])
    clips_dir = asset_dir / "clips"

    clips: list[Path] = []
    for segment in spec.get("segments", []):
        clip = clips_dir / f"{_slug(segment['id'])}.mp4"
        if clip.exists() and clip.stat().st_size > 0:
            clips.append(clip)

    if not clips:
        msg = f"没有可合成的 hybrid clips: {clips_dir}"
        raise FileNotFoundError(msg)

    output_video.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt") as handle:
        list_path = Path(handle.name)
        for clip in clips:
            handle.write(f"file '{clip.as_posix()}'\n")

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            str(output_video),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0 or not output_video.exists() or output_video.stat().st_size == 0:
            msg = result.stderr[-1000:] or "ffmpeg concat failed"
            raise RuntimeError(msg)
    finally:
        list_path.unlink(missing_ok=True)

    return output_video


def _slug(value: str) -> str:
    import re

    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value).strip())
    return value.strip("-") or "segment"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    args = parser.parse_args()
    output = compose(args.spec)
    print(f"✅ hybrid video: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
