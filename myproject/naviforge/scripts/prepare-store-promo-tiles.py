#!/usr/bin/env python3
"""Chrome Web Store optional promo tiles (RGB JPEG, no alpha).

  Small promo tile:  440×280
  Marquee promo tile: 1400×560

Inputs: docs/store-assets/icon-128-store.png + screenshots/store-1280x800/*.jpg
Output: docs/store-assets/promo/
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "docs/store-assets"
SHOT = STORE / "screenshots/store-1280x800"
PROMO = STORE / "promo"
ICON = STORE / "icon-128-store.png"

BG = (0x17, 0x21, 0x1F)
FG = (0xF4, 0xF7, 0xF5)
MUTED = (0x8A, 0x95, 0x8C)
ACCENT = (0xFF, 0x5C, 0x35)

SMALL = (440, 280)
MARQUEE = (1400, 560)


def cover_crop(im: Image.Image, target_w: int, target_h: int) -> Image.Image:
    target_ar = target_w / target_h
    w, h = im.size
    ar = w / h
    if ar > target_ar:
        new_h = h
        new_w = int(round(h * target_ar))
        left = (w - new_w) // 2
        box = (left, 0, left + new_w, h)
    else:
        new_w = w
        new_h = int(round(w / target_ar))
        top = (h - new_h) // 2
        box = (0, top, w, top + new_h)
    return im.crop(box).resize((target_w, target_h), Image.Resampling.LANCZOS)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        p = Path(path)
        if not p.is_file():
            continue
        try:
            index = 1 if bold and path.endswith(".ttc") else 0
            return ImageFont.truetype(str(p), size=size, index=index)
        except OSError:
            continue
    return ImageFont.load_default()


def save_jpeg(im: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rgb = im.convert("RGB")
    rgb.save(path, "JPEG", quality=92, optimize=True, subsampling=0)


def pick_shot(name: str) -> Image.Image:
    path = SHOT / name
    if not path.is_file():
        raise SystemExit(f"missing screenshot: {path}")
    im = Image.open(path)
    return im.convert("RGB") if im.mode != "RGB" else im


def small_promo_from_shot() -> Image.Image:
    # Product UI — settings + side panel reads well at small size.
    return cover_crop(pick_shot("03-toolkit-and-agent.jpg"), *SMALL)


def marquee_composite() -> Image.Image:
    w, h = MARQUEE
    canvas = Image.new("RGB", MARQUEE, BG)
    draw = ImageDraw.Draw(canvas)

    shot = cover_crop(pick_shot("01-toolkit-quick-menu.jpg"), int(w * 0.58), h)
    canvas.paste(shot, (int(w * 0.42), 0))

    # Gradient blend over the join
    grad = Image.new("L", (int(w * 0.22), h), 0)
    gdraw = ImageDraw.Draw(grad)
    for x in range(grad.width):
        alpha = int(255 * (x / max(1, grad.width - 1)))
        gdraw.line([(x, 0), (x, h)], fill=alpha)
    dark = Image.new("RGBA", grad.size, (*BG, 255))
    canvas.paste(Image.composite(dark, Image.new("RGBA", grad.size, (0, 0, 0, 0)), grad), (int(w * 0.38), 0))

    icon = Image.open(ICON).convert("RGBA")
    icon_size = 120
    icon = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
    canvas.paste(icon, (48, 72), icon)

    title_font = load_font(52, bold=True)
    sub_font = load_font(26)
    tag_font = load_font(20)

    draw.text((48, 210), "NaviForge", font=title_font, fill=FG)
    draw.text((48, 278), "侧栏 AI · 网页工具箱", font=sub_font, fill=FG)
    draw.text((48, 320), "BYOK · 本地会话 · ⌥N 快捷工具", font=tag_font, fill=MUTED)
    draw.rectangle([(48, 368), (420, 372)], fill=ACCENT)

    return canvas


def main() -> int:
    small = small_promo_from_shot()
    marquee = marquee_composite()

    save_jpeg(small, PROMO / "small-promo-tile-440x280.jpg")
    save_jpeg(marquee, PROMO / "marquee-promo-tile-1400x560.jpg")

    print(f"small  {SMALL[0]}×{SMALL[1]}  → {PROMO / 'small-promo-tile-440x280.jpg'}")
    print(f"marquee {MARQUEE[0]}×{MARQUEE[1]} → {PROMO / 'marquee-promo-tile-1400x560.jpg'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
