"""媒体上传的共用底座：按文件头判类型、限制大小、规范化图片、按前缀存桶。

**为什么在这里而不是某个产品里**：头像、消息图片、解题图片走的是同一条链路
（客户端压缩 → 上传 → 服务端读桶 → 模型看图）。把规则与存取放在产品里，
第二个产品接进来就会复制一遍，然后各自漂移——一边改了上限，另一边不知道。

这里只有领域无关的规则与 I/O；「谁的上传」「哪条消息引用它」是产品自己的事，
留在产品侧的记录表里。

同步实现（boto3 是同步客户端）；在 asyncio 服务里调用方用 ``asyncio.to_thread``
包一层，或者用 :meth:`SyncMediaStore.put_path` 里的说明。
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Protocol

from agentkit.storage.object_store import ObjectStore

# 默认上限。产品可以按场景传自己的（解题图要更清晰，头像可以更小）。
MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS_SIDE = 4096
LONG_EDGE = 2048
JPEG_QUALITY = 85

# 只认文件头，不信扩展名与 Content-Type：被改过的客户端可以随便声明。
_SIGNATURES: tuple[tuple[str, bytes, int, int], ...] = (
    ("image/jpeg", b"\xff\xd8\xff", 0, 3),
    ("image/png", b"\x89PNG\r\n\x1a\n", 0, 8),
    ("image/webp", b"RIFF", 0, 4),         # 之后 8–12 字节需为 WEBP，见 detect_type
    ("image/heic", b"ftyp", 4, 4),         # ftyp 在第 4 字节开始；品牌在 8–12
)

_HEIC_BRANDS = (b"heic", b"heix", b"mif1", b"msf1")


class UploadRejected(ValueError):
    """上传被拒绝；消息面向用户，不包含文件内容。"""


@dataclass(frozen=True, slots=True)
class ImageLimits:
    """一个场景的图片上限。默认值适合聊天图；解题图建议放宽长边。"""

    max_bytes: int = MAX_BYTES
    max_pixels_side: int = MAX_PIXELS_SIDE
    long_edge: int = LONG_EDGE
    jpeg_quality: int = JPEG_QUALITY


@dataclass(frozen=True, slots=True)
class Processed:
    data: bytes
    width: int
    height: int


def detect_type(head: bytes) -> str | None:
    """按文件头判 MIME；认不出返回 None。"""
    for mime, magic, offset, length in _SIGNATURES:
        if head[offset: offset + length] == magic[:length]:
            if mime == "image/webp" and head[8:12] != b"WEBP":
                continue
            if mime == "image/heic" and head[8:12] not in _HEIC_BRANDS:
                continue
            return mime
    return None


def check_size(data: bytes, limits: ImageLimits = ImageLimits()) -> None:
    if not data:
        raise UploadRejected("empty upload")
    if len(data) > limits.max_bytes:
        raise UploadRejected(f"file exceeds {limits.max_bytes // (1024 * 1024)} MB")


def check_pixels(width: int, height: int, limits: ImageLimits = ImageLimits()) -> None:
    if width <= 0 or height <= 0 or max(width, height) > limits.max_pixels_side * 2:
        raise UploadRejected("image dimensions out of range")


def scaled_size(width: int, height: int, limits: ImageLimits = ImageLimits()) -> tuple[int, int]:
    """长边缩到 ``limits.long_edge``，短边等比；不放大。"""
    longest = max(width, height)
    if longest <= limits.long_edge:
        return width, height
    scale = limits.long_edge / longest
    return max(1, round(width * scale)), max(1, round(height * scale))


def normalize_image(raw: bytes, limits: ImageLimits = ImageLimits()) -> Processed:
    """解码 → 去 EXIF（含 GPS，重新编码本身也会丢弃）→ 缩放 → 统一转 JPEG。"""
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:  # pragma: no cover —— 没装 Pillow 的产品不该用这个方法
        raise RuntimeError("normalize_image 需要 Pillow（pip install Pillow）") from exc

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            width, height = probe.size
            check_pixels(width, height, limits)
        with Image.open(io.BytesIO(raw)) as img:
            img = ImageOps.exif_transpose(img)     # 按方向信息转正，之后方向标记不再需要
            img = img.convert("RGB")
            target = scaled_size(*img.size, limits)
            if target != img.size:
                img = img.resize(target, Image.Resampling.LANCZOS)
            img.info.clear()
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=limits.jpeg_quality, optimize=True)
            width, height = img.size
    except UploadRejected:
        raise
    except Exception as exc:  # noqa: BLE001 —— 解码失败统一为用户可见的拒绝，不泄露库内部信息
        raise UploadRejected("cannot decode image") from exc
    return Processed(out.getvalue(), width, height)


class MediaStorePort(Protocol):
    """存图片需要的最小对象存储接口。``ObjectStore`` 满足它。"""

    def put_object(self, key: str, body: bytes, *, content_type: str | None = None) -> str: ...
    def get_object_bytes(self, key: str) -> bytes: ...
    def delete_object(self, key: str) -> None: ...


class MediaStore:
    """按前缀存图片：校验类型与像素、去 EXIF、统一转 JPEG，key 由调用方给。

    ``key_prefix`` 让多个产品共用一个桶而不互相干扰（``companion/``、``jc/``…）。
    前缀只是**地盘约定**，不是安全边界——能不能读某个 key 由产品自己的归属校验决定。
    """

    def __init__(self, objects: MediaStorePort, *, key_prefix: str = "") -> None:
        self._objects = objects
        self._prefix = key_prefix.strip("/")
        if self._prefix:
            self._prefix += "/"

    def key_for(self, relative: str) -> str:
        return f"{self._prefix}{relative.lstrip('/')}"

    def accept(self, *, raw: bytes, key: str, limits: ImageLimits = ImageLimits()) -> Processed:
        """校验并规范化后写入 ``key``，返回规范化后的字节与尺寸。

        ``key`` 必须是本产品的完整 key（含前缀）；用 :meth:`key_for` 拼。
        """
        check_size(raw, limits)
        mime = detect_type(raw[:16])
        if mime is None:
            raise UploadRejected("unsupported file type")
        processed = normalize_image(raw, limits)
        self._objects.put_object(key, processed.data, content_type="image/jpeg")
        return processed

    def read(self, key: str) -> bytes:
        """按 key 直接读字节（AK/SK 鉴权，不经签名 URL）。

        模型看图走这条：签名 URL 是 bearer secret，进模型请求或日志等于外泄。
        **调用方必须先自己做归属校验**——这个方法不知道谁能读。
        """
        return self._objects.get_object_bytes(key)

    def delete(self, key: str) -> None:
        self._objects.delete_object(key)
