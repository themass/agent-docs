"""LiveKit 接入层。

只有当真的依赖 livekit-agents 时才 import 它——测试环境、CI 和只需要跑
HTTP 接口的场景不该被迫安装整个语音栈。
"""

from __future__ import annotations


class LiveKitUnavailable(RuntimeError):
    """没安装 livekit-agents。"""


def available() -> bool:
    try:
        import livekit.agents  # noqa: F401
    except ImportError:
        return False
    return True


def require() -> None:
    try:
        import livekit.agents  # noqa: F401
    except ImportError as exc:
        raise LiveKitUnavailable(
            "livekit-agents 未安装：pip install 'livekit-agents>=1.0'"
        ) from exc
