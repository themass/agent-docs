"""上传的纯规则（O §5）：校验器与图片规范化的实现在 ``agentkit.storage.media``。

**为什么这里只剩转发**：头像、消息图片、解题图片走同一条链路，另外几个应用也要接。
规则一旦在产品里各写一份，就会各漂各的——一边改了上限，另一边不知道。
所以真正的实现在共用的 agentkit 里，这里保留这个模块名是为了不让调用点大改。

历史差异：这个产品的默认上限沿用 ``MAX_BYTES = 8 MiB`` 与 ``LONG_EDGE = 2048``，
与 agentkit 的默认值一致；``UploadRejected`` 也是同一个类，路由层照旧捕获它。
"""

from __future__ import annotations

from agentkit.storage.media import (  # noqa: F401 —— 对产品而言这就是它的公共接口
    JPEG_QUALITY,
    LONG_EDGE,
    MAX_BYTES,
    MAX_PIXELS_SIDE,
    ImageLimits,
    UploadRejected,
    check_pixels,
    check_size,
    detect_type,
    normalize_image,
    scaled_size,
)

__all__ = [
    "ImageLimits",
    "JPEG_QUALITY",
    "LONG_EDGE",
    "MAX_BYTES",
    "MAX_PIXELS_SIDE",
    "UploadRejected",
    "check_pixels",
    "check_size",
    "detect_type",
    "normalize_image",
    "scaled_size",
]
