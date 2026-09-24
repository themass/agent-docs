#!/usr/bin/env python3
"""Render hybrid-video assets from a hybrid production spec."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception as exc:  # pragma: no cover
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]
    ImageFont = None  # type: ignore[assignment]
    PIL_IMPORT_ERROR = exc
else:
    PIL_IMPORT_ERROR = None

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from seedance_client import ProviderUnavailable, generate_ai_broll  # noqa: E402


WIDTH = 1080
HEIGHT = 1920


def load_spec(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        msg = f"Invalid spec: {path}"
        raise ValueError(msg)
    return data


def slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    value = value.strip("-")
    return value or "segment"


def find_font(size: int):
    if ImageFont is None:
        return None
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def wrap_text(text: str, max_chars: int) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []
    lines: list[str] = []
    current = ""
    for char in text:
        if len(current) >= max_chars and char not in " ,.;，。；":
            lines.append(current)
            current = char
        else:
            current += char
    if current:
        lines.append(current)
    return lines


def render_card(
    output_path: Path,
    *,
    title: str,
    subtitle: str = "",
    bullets: list[str] | None = None,
    label: str = "HYBRID VIDEO",
) -> None:
    """Render a simple vertical concept card."""
    if Image is None or ImageDraw is None:
        msg = f"Pillow is required to render cards: {PIL_IMPORT_ERROR}"
        raise RuntimeError(msg)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (WIDTH, HEIGHT), (10, 14, 28))
    draw = ImageDraw.Draw(image)
    title_font = find_font(72)
    subtitle_font = find_font(42)
    body_font = find_font(38)
    label_font = find_font(28)

    # Background gradients/blocks.
    for y in range(HEIGHT):
        blue = 28 + int(y / HEIGHT * 36)
        draw.line([(0, y), (WIDTH, y)], fill=(8, 14, blue))
    draw.rounded_rectangle((70, 110, WIDTH - 70, 260), radius=38, fill=(24, 42, 88), outline=(94, 156, 255), width=2)
    draw.text((105, 165), label, fill=(150, 190, 255), font=label_font)

    y = 360
    for line in wrap_text(title, 12)[:3]:
        draw.text((90, y), line, fill=(245, 248, 255), font=title_font)
        y += 92

    if subtitle:
        y += 18
        for line in wrap_text(subtitle, 20)[:4]:
            draw.text((92, y), line, fill=(188, 210, 255), font=subtitle_font)
            y += 58

    y += 70
    for bullet in (bullets or [])[:5]:
        for index, line in enumerate(wrap_text(str(bullet), 22)[:3]):
            prefix = "• " if index == 0 else "  "
            draw.text((105, y), prefix + line, fill=(235, 238, 246), font=body_font)
            y += 54
        y += 16

    draw.rounded_rectangle((70, HEIGHT - 220, WIDTH - 70, HEIGHT - 120), radius=28, fill=(16, 25, 52), outline=(70, 100, 160), width=1)
    draw.text((105, HEIGHT - 188), "Content Studio · Hybrid Pipeline", fill=(150, 170, 210), font=label_font)
    image.save(output_path)


def create_clip(image_path: Path, output_path: Path, duration: float) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-t",
        str(duration),
        "-i",
        str(image_path),
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,format=yuv420p",
        "-r",
        "30",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0


def render_assets(spec_path: Path) -> dict[str, Any]:
    spec = load_spec(spec_path)
    metadata = spec["metadata"]
    asset_dir = Path(metadata["asset_dir"])
    cards_dir = asset_dir / "cards"
    github_dir = asset_dir / "github"
    ai_dir = asset_dir / "ai-broll"
    clips_dir = asset_dir / "clips"
    for directory in (cards_dir, github_dir, ai_dir, clips_dir):
        directory.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    counts = {"card": 0, "github": 0, "ai_broll": 0, "fallback": 0, "clip": 0}

    for segment in spec.get("segments", []):
        segment_id = str(segment["id"])
        asset_type = str(segment["asset_type"])
        duration = float(segment.get("duration_seconds", 6))
        clip_path = clips_dir / f"{slug(segment_id)}.mp4"
        record: dict[str, Any] = {
            "id": segment_id,
            "asset_type": asset_type,
            "duration_seconds": duration,
            "clip": str(clip_path),
        }

        if asset_type == "card":
            card = segment.get("card") or {}
            image_path = cards_dir / f"{slug(segment_id)}.png"
            render_card(
                image_path,
                title=str(card.get("title") or segment_id),
                subtitle=str(card.get("subtitle") or ""),
                bullets=[str(item) for item in card.get("bullets", [])],
            )
            counts["card"] += 1
            record["asset"] = str(image_path)
            if create_clip(image_path, clip_path, duration):
                counts["clip"] += 1

        elif asset_type == "github":
            repo = str(segment.get("repo") or "owner/repo")
            placeholder = github_dir / f"{slug(segment_id)}.txt"
            placeholder.write_text(
                f"GitHub evidence placeholder for {repo}\nFuture: replace with real scroll clip.\n",
                encoding="utf-8",
            )
            image_path = github_dir / f"{slug(segment_id)}.png"
            render_card(
                image_path,
                title="GitHub 证据段",
                subtitle=repo,
                bullets=["v1 先生成占位卡", "后续接入真实 GitHub 滚动片段", "不使用泛化库存素材替代证据"],
                label="GITHUB EVIDENCE",
            )
            counts["github"] += 1
            record["asset"] = str(image_path)
            record["placeholder"] = str(placeholder)
            if create_clip(image_path, clip_path, duration):
                counts["clip"] += 1

        elif asset_type == "ai_broll":
            output_path = ai_dir / f"{slug(segment_id)}.mp4"
            prompt = str(segment.get("visual_prompt") or "")
            negative_prompt = str(segment.get("negative_prompt") or "")
            mode = str((segment.get("ai_broll") or {}).get("mode") or "text_to_video")
            try:
                generated = generate_ai_broll(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    output_path=output_path,
                    duration_seconds=duration,
                    mode=mode,
                )
                record["asset"] = str(generated)
                if generated.exists():
                    clip_path.write_bytes(generated.read_bytes())
                    counts["clip"] += 1
                counts["ai_broll"] += 1
            except ProviderUnavailable as exc:
                fallback_path = ai_dir / f"{slug(segment_id)}-fallback.png"
                render_card(
                    fallback_path,
                    title="AI 相关素材占位",
                    subtitle="Seedance 未启用，已降级为概念卡",
                    bullets=[prompt[:96] or "visual prompt missing", str(exc)[:96]],
                    label="AI B-ROLL FALLBACK",
                )
                counts["fallback"] += 1
                record["asset"] = str(fallback_path)
                record["fallback_reason"] = str(exc)
                if create_clip(fallback_path, clip_path, duration):
                    counts["clip"] += 1
        else:
            record["skipped"] = f"unsupported asset_type: {asset_type}"

        records.append(record)

    status = {
        "spec": str(spec_path),
        "asset_dir": str(asset_dir),
        "counts": counts,
        "records": records,
    }
    status_path = asset_dir / "hybrid-assets-status.json"
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    args = parser.parse_args()
    status = render_assets(args.spec)
    print(json.dumps(status["counts"], ensure_ascii=False, indent=2))
    print(f"✅ hybrid assets: {status['asset_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
