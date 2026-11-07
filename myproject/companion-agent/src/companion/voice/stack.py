"""语音栈装配：给 LiveKit AgentSession 提供 TTS / STT。

Voice Gateway 是我们自己的供应商抽象；LiveKit 需要的是它自己的 `tts.TTS` /
`stt.STT` 实例。所以两者之间需要一层适配器——把 LiveKit 的接口转发到 Gateway。
这样换供应商只改 Gateway 的注册表，LiveKit 与 agent 都不动。

livekit-agents 是可选依赖：没装时这一层不导入，文字模式完全不受影响。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "female_warm"


@dataclass(frozen=True)
class VoiceStackConfig:
    provider: str = "volcengine"
    voice_id: str = DEFAULT_VOICE
    # 语音模式是否启用。默认关闭：第一版默认文字。
    enabled: bool = False


def config_from_env() -> VoiceStackConfig:
    return VoiceStackConfig(
        provider=os.getenv("COMPANION_VOICE_PROVIDER", "volcengine"),
        voice_id=os.getenv("COMPANION_VOICE_ID", DEFAULT_VOICE),
        enabled=os.getenv("COMPANION_VOICE_ENABLED", "false").lower() in {"1", "true", "yes"},
    )


def build_voice_stack(
    config: VoiceStackConfig | None = None,
) -> tuple[object, object]:
    """返回 (tts, stt)，供 `AgentSession(tts=..., stt=...)`。

    未配置语音供应商时抛错而不是返回 None：静默降级会让「语音模式」看起来能用
    但实际上没有声音，比直接失败更难查。
    """
    resolved = config or config_from_env()
    if not resolved.enabled:
        raise RuntimeError(
            "语音未启用：设置 COMPANION_VOICE_ENABLED=true 并配置供应商凭据"
        )

    from companion.voice import build_gateway

    gateway = build_gateway()
    try:
        from companion.voice.livekit_adapters import GatewaySTT, GatewayTTS
    except ImportError as exc:
        raise RuntimeError(
            "语音需要 livekit-agents：pip install 'livekit-agents'"
        ) from exc

    return (
        GatewayTTS(gateway, provider=resolved.provider, voice_id=resolved.voice_id),
        GatewaySTT(gateway, provider=resolved.provider),
    )
