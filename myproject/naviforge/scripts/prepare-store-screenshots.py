#!/usr/bin/env python3
"""Crop + scale screenshots to Chrome Web Store 1280×800 (cover, center)."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

TARGET_W, TARGET_H = 1280, 800
TARGET_AR = TARGET_W / TARGET_H

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs/store-assets/screenshots/store-1280x800"

# basename → source under Cursor assets (copied into repo on first run)
NAMES = [
    ("01-toolkit-quick-menu.jpg", "image-f8250602-e962-4d8d-af88-8372d06d3168.jpg"),
    ("02-agent-sidepanel.png", "image-63fbe6c2-5a6a-4031-a4a3-9ae004d01ff7.png"),
    ("03-toolkit-and-agent.jpg", "image-96c6d3ed-d6bf-4d6d-a538-03b8fbe9448c.jpg"),
    ("04-plugins-skills.jpg", "image-2003c12f-83ee-4462-97dc-b38cbf498a8e.jpg"),
]

ASSETS = Path("/Users/gqli/.cursor/projects/Users-gqli-work-deepagents/assets")
SOURCE_DIR = ROOT / "docs/store-assets/screenshots/source"


def cover_crop(im: Image.Image) -> Image.Image:
    w, h = im.size
    ar = w / h
    if ar > TARGET_AR:
        # too wide — match height, crop width
        new_h = h
        new_w = int(round(h * TARGET_AR))
        left = (w - new_w) // 2
        box = (left, 0, left + new_w, h)
    else:
        # too tall — match width, crop height
        new_w = w
        new_h = int(round(w / TARGET_AR))
        top = (h - new_h) // 2
        box = (0, top, w, top + new_h)
    cropped = im.crop(box)
    return cropped.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)


def main() -> int:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for out_name, asset_name in NAMES:
        src_asset = ASSETS / asset_name
        src_repo = SOURCE_DIR / out_name
        if src_asset.is_file() and not src_repo.is_file():
            src_repo.write_bytes(src_asset.read_bytes())
        src = src_repo if src_repo.is_file() else src_asset
        if not src.is_file():
            print(f"missing: {src}", file=sys.stderr)
            return 1
        im = Image.open(src)
        if im.mode in ("RGBA", "P"):
            im = im.convert("RGB")
        out = cover_crop(im)
        dest = OUT_DIR / out_name.replace(".png", ".jpg") if out_name.endswith(".png") else OUT_DIR / out_name
        if dest.suffix.lower() == ".png" and out_name.endswith(".png"):
            out.save(dest, "PNG", optimize=True)
        else:
            dest = dest.with_suffix(".jpg")
            out.save(dest, "JPEG", quality=92, optimize=True)
        print(f"{dest.name}  {out.size[0]}×{out.size[1]}  ← {src.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
