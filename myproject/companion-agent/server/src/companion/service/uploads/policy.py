"""上传的纯规则（O §5）：按文件头判类型、大小与像素上限。无 I/O。"""

from __future__ import annotations

MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS_SIDE = 4096
LONG_EDGE = 2048
JPEG_QUALITY = 85

# 只认文件头，不信扩展名与 Content-Type。
_SIGNATURES: tuple[tuple[str, bytes, int, int], ...] = (
    ("image/jpeg", b"\xff\xd8\xff", 0, 3),
    ("image/png", b"\x89PNG\r\n\x1a\n", 0, 8),
    ("image/webp", b"RIFF", 0, 4),         # 之后 8–12 字节需为 WEBP，见 detect_type
    ("image/heic", b"ftyp", 4, 4),         # ftyp 在第 4 字节开始；品牌在 8–12
)


class UploadRejected(ValueError):
    """上传被拒绝；消息面向用户，不包含文件内容。"""


def detect_type(head: bytes) -> str | None:
    for mime, magic, offset, length in _SIGNATURES:
        if head[offset: offset + length] == magic[:length]:
            if mime == "image/webp" and head[8:12] != b"WEBP":
                continue
            if mime == "image/heic" and head[8:12] not in (b"heic", b"heix", b"mif1", b"msf1"):
                continue
            return mime
    return None


def check_size(data: bytes) -> None:
    if not data:
        raise UploadRejected("empty upload")
    if len(data) > MAX_BYTES:
        raise UploadRejected("file exceeds 8 MB")


def check_pixels(width: int, height: int) -> None:
    if width <= 0 or height <= 0 or max(width, height) > MAX_PIXELS_SIDE * 2:
        raise UploadRejected("image dimensions out of range")


def scaled_size(width: int, height: int) -> tuple[int, int]:
    """长边缩到 LONG_EDGE，短边等比；不放大。"""
    longest = max(width, height)
    if longest <= LONG_EDGE:
        return width, height
    scale = LONG_EDGE / longest
    return max(1, round(width * scale)), max(1, round(height * scale))
