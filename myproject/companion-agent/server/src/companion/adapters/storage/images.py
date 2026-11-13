"""图片处理（O §5）：解码 → 去 EXIF → 缩放 → 重新编码为 JPEG。Pillow 实现。

重新编码本身就会丢弃 EXIF（包括 GPS），这里再显式清空 info 作为双保险。
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps

from companion.domain.uploads.policy import JPEG_QUALITY, UploadRejected, check_pixels, scaled_size


@dataclass(frozen=True)
class Processed:
    data: bytes
    width: int
    height: int


def normalize_image(raw: bytes) -> Processed:
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            width, height = probe.size
            check_pixels(width, height)
        with Image.open(io.BytesIO(raw)) as img:
            img = ImageOps.exif_transpose(img)  # 按方向信息转正，之后方向标记不再需要
            img = img.convert("RGB")
            target = scaled_size(*img.size)
            if target != img.size:
                img = img.resize(target, Image.Resampling.LANCZOS)
            img.info.clear()
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            width, height = img.size
    except UploadRejected:
        raise
    except Exception as exc:  # noqa: BLE001 — 解码失败统一为用户可见的拒绝，不泄露库内部信息
        raise UploadRejected("cannot decode image") from exc
    return Processed(out.getvalue(), width, height)
