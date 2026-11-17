"""图片处理（O §5）：实现已挪到 ``agentkit.storage.media.normalize_image``。

保留这个模块名，是为了让 ``bootstrap`` 里的装配与既有调用点不变；
真正解码/去 EXIF/缩放/重编码的代码只有一份，在共用包里。
"""

from __future__ import annotations

from agentkit.storage.media import Processed, normalize_image  # noqa: F401

__all__ = ["Processed", "normalize_image"]
