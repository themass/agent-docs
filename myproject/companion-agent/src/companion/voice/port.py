"""语音端口：TTS 与 ASR 的供应商无关接口。

供应商可替换（设计文档第 13 节）：角色卡只存 ``voice_ref``，不存端点、不存密钥，
换供应商只改适配器与 ``voice_ref.provider``，agent 侧一行不动。

这里只有协议与数据形状，不 import 任何供应商 SDK。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

DEFAULT_SAMPLE_RATE = 24_000
DEFAULT_FORMAT = "pcm"


class VoiceError(RuntimeError):
    """语音层错误的基类。"""


class UnknownVoiceProvider(VoiceError):
    """VoiceRef 指向了一个没有注册的供应商。"""


class VoiceUnavailable(VoiceError):
    """配置或依赖缺失，供应商暂时不可用。"""


class VoiceProviderError(VoiceError):
    """供应商调用失败（网络、鉴权、协议错误）。

    ``direction`` 区分 "tts" / "asr"，``provider`` 是失败时真正在用的供应商名。
    网关据此决定是否切换，日志也靠它定位。
    """

    def __init__(self, message: str, *, provider: str = "", direction: str = "") -> None:
        super().__init__(message)
        self.provider = provider
        self.direction = direction


@dataclass(frozen=True)
class VoiceRef:
    """角色声音的引用。可序列化，能直接放进角色卡 ``data.voice_ref``。

    ``params`` 是供应商参数（语速、情绪、音色变体），原样交给适配器解释；
    端口层不解释它的内容。
    """

    provider: str
    voice_id: str
    params: Mapping[str, Any] = field(default_factory=dict)

    def stable_key(self) -> str:
        """缓存键用：与 dict 顺序无关的参数指纹。"""
        try:
            return json.dumps(dict(self.params), sort_keys=True, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return repr(sorted((str(k), str(v)) for k, v in self.params.items()))

    def __hash__(self) -> int:
        """frozen dataclass 含 dict 时默认不可哈希。

        可哈希是需要的：供应商选择与缓存都用它做键。用 stable_key 而不是
        ``hash(self.params)``——后者对 dict 直接报错。
        """
        return hash((self.provider, self.voice_id, self.stable_key()))

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> VoiceRef | None:
        """从角色卡字段解析；``provider`` / ``voice_id`` 任一缺失视为没有声音。"""
        if not isinstance(raw, Mapping):
            return None
        provider = str(raw.get("provider") or "").strip()
        voice_id = str(raw.get("voice_id") or "").strip()
        if not provider or not voice_id:
            return None
        params = raw.get("params")
        return cls(
            provider=provider,
            voice_id=voice_id,
            params=dict(params) if isinstance(params, Mapping) else {},
        )


@dataclass(frozen=True)
class AudioChunk:
    """一段音频。``data`` 是供应商原始的字节，网关不转码。"""

    data: bytes
    sample_rate: int = DEFAULT_SAMPLE_RATE
    format: str = DEFAULT_FORMAT


@dataclass(frozen=True)
class Transcript:
    """一段识别结果。

    ``is_final`` 为 True 表示这句话已经定稿，后面的结果不会再来修正它；上层只应
    把定稿文本送进对话，中间结果只用于显示。
    """

    text: str
    is_final: bool = False
    confidence: float = 0.0


@runtime_checkable
class VoiceProvider(Protocol):
    """一个供应商要满足的全部接口。"""

    name: str

    def tts(
        self, text_stream: AsyncIterator[str], voice_ref: VoiceRef
    ) -> AsyncIterator[AudioChunk]:
        """文本片段流 → 音频块流。实现必须是异步生成器。"""
        ...

    def asr(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
        """音频块流 → 识别结果流。实现必须是异步生成器。"""
        ...
