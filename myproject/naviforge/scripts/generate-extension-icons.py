#!/usr/bin/env python3
"""Generate square NaviForge extension icons from BrandMark geometry."""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "apps/extension/public"
STORE = ROOT / "docs/store-assets"

BG = (0x17, 0x21, 0x1f)
ORANGE = (0xff, 0x5c, 0x35)
LIME = (0xbe, 0xf2, 0x64)


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 32
    radius = int(8 * s)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=BG)

    def pt(x: float, y: float) -> tuple[float, float]:
        return (x * s, y * s)

    stroke = max(1, int(2.75 * s))
    p1, p2, p3 = pt(9, 22), pt(16, 10), pt(23, 22)
    draw.line([p1, p2, p3], fill=ORANGE, width=stroke, joint="curve")

    cx, cy = pt(23, 9)
    r = max(1, int(3 * s))
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=LIME)
    return img


def main() -> None:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    STORE.mkdir(parents=True, exist_ok=True)

    for size in (16, 32, 48, 64, 128):
        icon = draw_icon(size)
        icon.save(PUBLIC / f"icon-{size}.png", "PNG")
        icon.save(STORE / f"icon-{size}-store.png", "PNG")

    master.save(STORE / "icon-512-store.png", "PNG")

    print("icons ok:", PUBLIC, STORE)


if __name__ == "__main__":
    main()
