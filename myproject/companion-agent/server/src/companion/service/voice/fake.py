"""测试用语音供应商。

不是 mock：输出是确定性的（同一段文本永远同一串字节），所以缓存命中、断句边界、
失败切换都可以直接断言，不需要网络也不需要真音频。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from companion.service.voice.port import AudioChunk, Transcript, VoiceProviderError, VoiceRef

DEFAULT_CHUNK_BYTES = 8


@dataclass
class FakeVoiceProvider:
    """把文本编码成合成音频块。

    ``fail_times`` 是构造时一次性的：前 N 次调用抛错，之后恢复。``fail_forever``
    用来测「一直坏、没有备用」的场景。两种都只影响下一次调用，不累积副作用，
    测试之间互不影响。
    """

    name: str = "fake"
    sample_rate: int = 24_000
    format: str = "pcm"
    chunk_bytes: int = DEFAULT_CHUNK_BYTES
    fail_times: int = 0
    fail_forever: bool = False

    tts_calls: list[tuple[str, str]] = field(default_factory=list)
    asr_calls: int = 0
    # 记录每次调用收到的完整文本，用来断言缓存命中时没有再合成。
    synthesized_text: list[str] = field(default_factory=list)

    async def tts(
        self, text_stream: AsyncIterator[str], voice_ref: VoiceRef
    ) -> AsyncIterator[AudioChunk]:
        parts = [text async for text in text_stream]
        text = "".join(parts)
        self.tts_calls.append((voice_ref.voice_id, text))
        self._maybe_fail("tts", text)
        if not text:
            return
        # 合成结果带 voice_id，这样断言「换供应商后音色没串」是可能的。
        for chunk in self._chunks(text, voice_ref):
            yield chunk
        self.synthesized_text.append(text)

    async def asr(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
        self.asr_calls += 1
        self._maybe_fail("asr", "")
        buffered = 0
        async for audio in audio_stream:
            buffered += len(audio)
            yield Transcript(text=f"{buffered}", is_final=False, confidence=0.5)
        yield Transcript(text=f"done:{buffered}", is_final=True, confidence=0.99)

    # ---- 内部 ----

    def _maybe_fail(self, direction: str, text: str) -> None:
        if self.fail_forever:
            raise VoiceProviderError(
                f"{self.name} {direction} is configured to fail", provider=self.name, direction=direction
            )
        if self.fail_times > 0:
            self.fail_times -= 1
            raise VoiceProviderError(
                f"{self.name} {direction} failure (remaining {self.fail_times})",
                provider=self.name,
                direction=direction,
            )

    def _chunks(self, text: str, voice_ref: VoiceRef) -> list[AudioChunk]:
        seed = f"{voice_ref.voice_id}|{text}".encode("utf-8")
        pieces = [
            seed[i : i + self.chunk_bytes] for i in range(0, len(seed), self.chunk_bytes)
        ] or [b""]
        return [
            AudioChunk(data=piece, sample_rate=self.sample_rate, format=self.format)
            for piece in pieces
        ]
