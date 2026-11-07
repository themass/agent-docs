"""语音层。

``port.py`` 定义供应商无关的接口，``gateway.py`` 负责路由、短句缓存与故障切换，
``volcengine.py`` 是 v1 适配器，``fake.py`` 给测试用。换供应商只加一个适配器加
一个 ``voice_ref.provider``，上层不动（设计文档第 13 节）。
"""

from companion.voice.fake import FakeVoiceProvider
from companion.voice.gateway import (
    FailureOutcome,
    ProviderSwitch,
    VoiceGateway,
    build_gateway,
)
from companion.voice.port import (
    DEFAULT_FORMAT,
    DEFAULT_SAMPLE_RATE,
    AudioChunk,
    Transcript,
    UnknownVoiceProvider,
    VoiceError,
    VoiceProvider,
    VoiceProviderError,
    VoiceRef,
    VoiceUnavailable,
)
from companion.voice.volcengine import VolcengineConfig, VolcengineProvider

__all__ = [
    "DEFAULT_FORMAT",
    "DEFAULT_SAMPLE_RATE",
    "AudioChunk",
    "FailureOutcome",
    "FakeVoiceProvider",
    "ProviderSwitch",
    "Transcript",
    "UnknownVoiceProvider",
    "VoiceError",
    "VoiceGateway",
    "VoiceProvider",
    "VoiceProviderError",
    "VoiceRef",
    "VoiceUnavailable",
    "build_gateway",
    "VolcengineConfig",
    "VolcengineProvider",
]
