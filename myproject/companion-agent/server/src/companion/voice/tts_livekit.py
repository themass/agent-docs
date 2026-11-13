"""把项目自己的 TTS 适配器包成 LiveKit 的 ``tts.TTS``。

为什么需要这一层：阿里云 NLS 的适配器是按项目自己的 ``VoiceProvider`` 协议写的
（验证过的、能出声），而 ``AgentSession`` 要的是 LiveKit 的 ``tts.TTS``。中间只做
格式转换，不做业务逻辑——协议、错误、重试都留在原来的适配器里。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from livekit.agents import tts

from companion.voice.port import VoiceProvider, VoiceRef

log = logging.getLogger("companion.voice")


class ProviderTTS(tts.TTS):
    """把一个 ``VoiceProvider`` 包成 LiveKit 的 TTS。

    LiveKit 的 ``synthesize`` 要的是「一段文本 → 一段音频」，而项目的适配器按
    「文本流 → 音频块流」工作。这里把单段文本包成只有一项的流，再把音频块拼回
    一次性的 ``ChunkedStream``。
    """

    def __init__(self, provider: VoiceProvider, *, voice_ref: VoiceRef, sample_rate: int = 16000,
                 num_channels: int = 1) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=sample_rate,
            num_channels=num_channels,
        )
        self._provider = provider
        self._voice_ref = voice_ref

    @property
    def provider_name(self) -> str:
        return self._provider.name

    @property
    def model(self) -> str:
        return self._voice_ref.voice_id

    def synthesize(self, text: str, *, conn_options: Any = None) -> "ProviderTTSStream":
        return ProviderTTSStream(tts=self, text=text, provider=self._provider, voice_ref=self._voice_ref)


class ProviderTTSStream(tts.ChunkedStream):
    def __init__(self, *, tts: ProviderTTS, text: str, provider: VoiceProvider, voice_ref: VoiceRef) -> None:
        super().__init__(tts=tts, input_text=text)
        self._provider = provider
        self._voice_ref = voice_ref

    async def _run(self, output_emitter: Any) -> None:
        async def one() -> AsyncIterator[str]:
            yield self._input_text

        chunks = [chunk async for chunk in self._provider.tts(one(), self._voice_ref)]
        data = b"".join(c.data for c in chunks)
        if not data:
            log.warning("tts returned no audio", extra={"provider": self._provider.name})
        output_emitter.initialize(
            request_id="tts-request",
            sample_rate=self._tts.sample_rate,
            num_channels=self._tts.num_channels,
            mime_type="audio/wav",
        )
        output_emitter.push(data)
        output_emitter.flush()
