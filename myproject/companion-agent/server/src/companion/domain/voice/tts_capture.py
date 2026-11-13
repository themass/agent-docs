"""采集 ``tts_node`` 的一次合成：送进 TTS 的文本，和 TTS 吐出的音频。

判断 TTS 念得对不对，需要这一对数据。放在 ``tts_node`` 里取，是因为这里拿到的正是**框架做完文本变换
（默认过滤 markdown 和 emoji）之后真正送给合成引擎的文本**，以及引擎返回的原始音频帧——
不是我们的 ``llm_node`` 产出的文本，那一份在变换之前，和实际念的可能不同。

本模块不依赖 LiveKit：音频帧只要有 ``data`` / ``sample_rate`` / ``num_channels`` 就行，所以能用假帧测。
"""

from __future__ import annotations

import io
import time
import wave
from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass
from typing import Any

# 单次合成最多留这么长的音频。一句话几秒，一整段回复也很少过一分钟；
# 设上限是为了一个失控的长回复不会把进程内存吃光。
DEFAULT_MAX_SECONDS = 60.0
BYTES_PER_SAMPLE = 2          # 16-bit PCM


def pcm_to_wav(pcm: bytes, *, sample_rate: int, channels: int = 1) -> bytes:
    """裸 PCM16 包成 WAV 容器，任何播放器和 ASR 都能直接读。"""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(BYTES_PER_SAMPLE)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


@dataclass(frozen=True)
class TtsSegment:
    """一次 ``tts_node`` 调用的结果。"""

    text: str
    pcm: bytes
    sample_rate: int
    channels: int
    ttfb_ms: int | None
    truncated: bool          # 音频超过上限被截断，或中途采样率变了
    completed: bool          # False = 被打断，音频只到打断那一刻

    @property
    def audio_ms(self) -> int:
        if not self.sample_rate or not self.channels:
            return 0
        samples = len(self.pcm) // (BYTES_PER_SAMPLE * self.channels)
        return int(samples * 1000 / self.sample_rate)


class TtsCapture:
    """一次合成的采集状态。``tee_text`` 包住输入文本流，``tee_frames`` 包住输出音频流。"""

    def __init__(self, *, max_seconds: float = DEFAULT_MAX_SECONDS, clock=time.monotonic) -> None:
        self._max_seconds = max_seconds
        self._clock = clock
        self._texts: list[str] = []
        self._pcm = bytearray()
        self._rate = 0
        self._channels = 1
        self._first_text_at: float | None = None
        self._first_audio_at: float | None = None
        self._truncated = False

    @property
    def started(self) -> bool:
        """已经收到过文本。"""
        return self._first_text_at is not None

    async def tee_text(self, text: AsyncIterable[str]) -> AsyncIterator[str]:
        async for chunk in text:
            if self._first_text_at is None:
                self._first_text_at = self._clock()
            self._texts.append(chunk)
            yield chunk

    async def tee_frames(self, frames: AsyncIterable[Any]) -> AsyncIterator[Any]:
        async for frame in frames:
            self._take(frame)
            yield frame

    def _take(self, frame: Any) -> None:
        if self._first_audio_at is None:
            self._first_audio_at = self._clock()
        rate, channels = int(frame.sample_rate), int(frame.num_channels)
        if not self._rate:
            self._rate, self._channels = rate, channels
        elif (rate, channels) != (self._rate, self._channels):
            self._truncated = True      # 一个 WAV 只能有一种格式；混着写会放出变调的声音，不如停在这里
            return
        if self._truncated:
            return
        limit = int(self._max_seconds * self._rate * self._channels * BYTES_PER_SAMPLE)
        room = limit - len(self._pcm)
        data = bytes(frame.data)
        if len(data) > room:
            self._pcm += data[: max(room, 0)]
            self._truncated = True
        else:
            self._pcm += data

    def finish(self, *, completed: bool) -> TtsSegment:
        ttfb = None
        if self._first_text_at is not None and self._first_audio_at is not None:
            ttfb = round((self._first_audio_at - self._first_text_at) * 1000)
        return TtsSegment(text="".join(self._texts), pcm=bytes(self._pcm), sample_rate=self._rate,
                          channels=self._channels, ttfb_ms=ttfb, truncated=self._truncated, completed=completed)
