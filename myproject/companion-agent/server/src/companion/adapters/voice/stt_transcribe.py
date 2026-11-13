"""把一段 WAV 送进 LiveKit 的 STT，拿回识别文本。供 TTS 准确性检查回灌音频用。

只做“一整段音频 → 一句文本”：按 100 毫秒切帧推进流，结束后收集所有最终结果拼起来。
"""

from __future__ import annotations

import io
import wave
from typing import Any

FRAME_MS = 100


def wav_frames(wav_bytes: bytes, rtc: Any):
    """WAV → 100 毫秒一帧的 AudioFrame。只接受 16-bit PCM；别的格式要先转，静默按错的位宽读会得到噪声。"""
    with wave.open(io.BytesIO(wav_bytes)) as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"expected 16-bit PCM, got {w.getsampwidth() * 8}-bit")
        rate, channels = w.getframerate(), w.getnchannels()
        per_frame = rate * FRAME_MS // 1000
        while chunk := w.readframes(per_frame):
            yield rtc.AudioFrame(data=chunk, sample_rate=rate, num_channels=channels,
                                 samples_per_channel=len(chunk) // (2 * channels))


# 音频推完之后，多久没有新事件就认为识别结束。识别器可能在末尾再补一段结果，所以不能一收到
# end_of_speech 就走；也不能无限等（火山识别完会断开，插件一直重连，迭代器不会自己结束）。
SETTLE_SEC = 2.0


async def transcribe_wav(stt: Any, wav_bytes: bytes, *, language: str = "zh", pace: bool = True,
                         timeout: float = 30.0, settle: float = SETTLE_SEC) -> str:
    """识别一整段 WAV，返回拼好的最终文本。

    - **按实时节奏推帧**（``pace``）：流式识别器按“说话的速度”设计，一次性灌入会丢字
      （实测同一句话一次性推送少了“儿”，按节奏推送则完整）。测试里传 ``pace=False`` 免得真等。
    - **不以 ``end_of_speech`` 为结束信号**：识别器按语音端点切段，一句话中间的停顿就会提前发一个，
      而且它之后还可能补出结果。收尾只看“音频推完、已有结果、之后安静了 ``settle`` 秒”。
    - ``timeout`` 兜底；超时时返回已收到的最终结果，一句都没有才抛错。
    """
    import asyncio

    from livekit import rtc
    from livekit.agents import stt as lk_stt

    stream = stt.stream(language=language)

    async def feed() -> None:
        for frame in wav_frames(wav_bytes, rtc):
            stream.push_frame(frame)
            if pace:
                await asyncio.sleep(FRAME_MS / 1000)
        stream.end_input()

    feeder = asyncio.create_task(feed())
    parts: list[str] = []

    async def collect() -> None:
        events = stream.__aiter__()
        while True:
            idle = settle if feeder.done() and parts else None
            try:
                event = await asyncio.wait_for(events.__anext__(), idle)
            except asyncio.TimeoutError:
                return                              # 推完之后安静了 settle 秒
            except StopAsyncIteration:
                return
            if event.type == lk_stt.SpeechEventType.FINAL_TRANSCRIPT and event.alternatives:
                parts.append(event.alternatives[0].text)
            # end_of_speech 不当作结束信号：识别器在它之后还可能补出结果。只靠“推完音频后安静 settle 秒”收尾。

    try:
        await asyncio.wait_for(collect(), timeout)
    except asyncio.TimeoutError:
        if not parts:
            raise TimeoutError(f"no transcript within {timeout}s") from None
    finally:
        feeder.cancel()
        await asyncio.gather(feeder, return_exceptions=True)
        await stream.aclose()
    return "".join(parts).strip()
