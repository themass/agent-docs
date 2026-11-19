"""语音栈装配：给 LiveKit AgentSession 提供 TTS / STT。

Voice Gateway 是我们自己的供应商抽象；LiveKit 需要的是它自己的 `tts.TTS` /
`stt.STT` 实例。所以两者之间需要一层适配器——把 LiveKit 的接口转发到 Gateway。
这样换供应商只改 Gateway 的注册表，LiveKit 与 agent 都不动。

livekit-agents 是可选依赖：没装时这一层不导入，文字模式完全不受影响。
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from companion.service.voice.gateway import VoiceGateway
from companion.service.voice.port import VoiceProvider, VoiceUnavailable

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "female_warm"

#: 与 ``worker.py`` 里那个兜底值同一个字符串。两处都留着是因为它们服务于不同的时点：
#: 一个在装配房间、一个在写质检记录，谁都不该为了让另一个少一行字而改。
ENV_FALLBACK_VOICE = "saturn_zh_female_keainvsheng_tob"


@dataclass(frozen=True)
class VoiceStackConfig:
    provider: str = "volcengine"
    voice_id: str = DEFAULT_VOICE
    # 语音模式是否启用。默认关闭：第一版默认文字。
    enabled: bool = False
    # 角色卡 ``voice_ref.voice_id`` 不是火山说话人 id 时的兜底。``None`` 表示按环境变量。
    fallback_voice: str | None = None


def config_from_env() -> VoiceStackConfig:
    return VoiceStackConfig(
        provider=os.getenv("COMPANION_VOICE_PROVIDER", "volcengine"),
        voice_id=os.getenv("COMPANION_VOICE_ID", DEFAULT_VOICE),
        enabled=os.getenv("COMPANION_VOICE_ENABLED", "false").lower() in {"1", "true", "yes"},
    )


def resolve_voice_id(*, card_voice: str | None, config: VoiceStackConfig) -> str:
    """一张卡该用哪个说话人。顺序：角色卡 → 环境变量 → 常量兜底。

    **角色卡里的值必须能真的出声，否则要在装配前被换掉。** 仓库自带的卡写的是
    ``male_calm`` / ``female_warm`` 这类描述性占位（见 ``agent/characters/README.md``），
    不是火山说话人 id；直接送过去，每一句都是一个 400，用户听到的是静音。
    所以卡里的值只当作**已核实的候选**：调用方能确认它可用时传进来，否则用环境变量的值。
    """
    for candidate in (card_voice, config.voice_id, config.fallback_voice,
                      os.getenv("VOLC_TTS_VOICE"), ENV_FALLBACK_VOICE):
        value = (candidate or "").strip()
        if value:
            return value
    return ENV_FALLBACK_VOICE


def build_tts(config: VoiceStackConfig, *, voice_id: str | None = None) -> Any:
    """这个房间的 TTS。单独一个函数，是为了让「说话人到底传没传进去」可以被直接断言——
    走整个 ``build_voice_stack`` 的话还得先把 VAD 模型加载起来，测试就成了在验 silero。"""
    from companion.service.voice.volcengine_livekit import NewConsoleTTS

    return NewConsoleTTS(voice=resolve_voice_id(card_voice=voice_id, config=config), sample_rate=16000)


def build_voice_stack(
    config: VoiceStackConfig | None = None,
    *,
    voice_id: str | None = None,
) -> tuple[object, object, object]:
    """返回 (tts, stt, vad)，供 ``AgentSession(tts=..., stt=..., vad=...)``。

    ``voice_id`` 是**这个房间**的说话人（由入口从角色卡解析后传入）。不传就用
    ``config.voice_id``——单角色调试与离线脚本走这条路。这一层必须接受它：
    否则一间房里两个角色只能共用一个嗓子，而「音色跟着形象走」是这个产品的主线。

    **用社区插件 ``livekit-plugins-volcengine``**，不自己实现协议：插件负责 URL、
    请求体、分包、响应解析与重连；我们只覆盖鉴权头（新版控制台签发的是
    ``X-Api-Key``，插件写死的是旧版头）。见 ``adapters/voice/volcengine_livekit.py``。

    VAD 用 LiveKit 官方默认的 silero：语音端点检测是通用问题，官方模型已经调好，
    自己实现只会更差。

    未配置时抛错而不是返回 None：静默降级会让「语音模式」看起来能用但没声音，
    比直接失败更难查。
    """
    resolved = config or config_from_env()
    if not resolved.enabled:
        raise RuntimeError("语音未启用：设置 COMPANION_VOICE_ENABLED=true 并配置供应商凭据")

    try:
        from livekit.plugins import silero
    except ImportError as exc:
        raise RuntimeError("语音需要 livekit-agents：uv pip install livekit-agents") from exc

    from livekit.agents import vad as lk_vad

    if resolved.provider != "volcengine":
        raise RuntimeError(f"暂只接了火山（volcengine），当前配置是 {resolved.provider!r}")

    from companion.service.voice.volcengine_livekit import NewConsoleSTT

    tts = build_tts(resolved, voice_id=voice_id)
    stt = NewConsoleSTT()
    # silero 需要在 worker 启动时预加载（prewarm），否则第一句会有明显延迟。
    vad = silero.VAD.load()
    if not isinstance(vad, lk_vad.VAD):
        raise RuntimeError("VAD 不是 LiveKit 的 VAD 实例")
    return tts, stt, vad



# ---- 以下从 app/voice/gateway.py 移入：装配火山引擎等具体供应商，属于组合根 ----

def build_gateway(
    providers: Mapping[str, VoiceProvider] | None = None,
    **kwargs: Any,
) -> VoiceGateway:
    """按环境变量装配一个网关。

    配置不全时抛 ``VoiceUnavailable`` 而不是返回一个空网关：调用方（``stack.py``）
    宁可启动时就失败，也不要上线后第一句话没有声音才被发现。
    """
    if providers:
        return VoiceGateway(providers, **kwargs)

    from companion.service.voice.volcengine import VolcengineConfig, VolcengineProvider

    registered: dict[str, VoiceProvider] = {}
    try:
        registered["volcengine"] = VolcengineProvider(config=VolcengineConfig.from_env())
    except VoiceUnavailable as exc:
        logger.warning("volcengine voice provider unavailable: %s", exc)

    # 阿里云 NLS：短文本 REST。与火山并存，由 voice_ref.provider 或 COMPANION_VOICE_PROVIDER 选择。
    try:
        from companion.service.voice.aliyun import AliyunConfig, AliyunProvider

        registered["aliyun"] = AliyunProvider(config=AliyunConfig.from_env())
    except VoiceUnavailable as exc:
        logger.warning("aliyun voice provider unavailable: %s", exc)

    if not registered:
        raise VoiceUnavailable(
            "没有可用的语音供应商：设置 VOLC_TTS_* 或 ALI_TTS_APP_ID / ALI_TTS_ACCESS_KEY / ALI_TTS_ACCESS_KEY_SECRET"
        )

    kwargs.setdefault("secondary", _env_or_none("COMPANION_VOICE_SECONDARY"))
    kwargs.setdefault("asr_provider", _env_or_none("COMPANION_VOICE_ASR_PROVIDER"))
    return VoiceGateway(registered, **kwargs)


def _env_or_none(name: str):
    value = (os.environ.get(name) or "").strip()
    return value or None