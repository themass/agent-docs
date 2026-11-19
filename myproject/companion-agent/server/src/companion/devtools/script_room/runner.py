"""剧本房 Live runner：hello 门禁 → 逐句 say/cue/TTS/PCM → barge 截断。

不 import livekit；RTC 经 :class:`RtcAdapter`。默认 TTS 由调用方注入
（单测 ``FakeVoiceProvider``，CLI 后续 ``VolcengineProvider``）。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any, Protocol

from companion.agent.protocol.cue_compiler import CueBudget
from companion.agent.protocol.handshake import LEGACY_WAIT_SECONDS
from companion.api.livekit.speech_publisher import SpeechPublisher
from companion.devtools.script_room.bridge_over_rtc import BridgeOverRtc
from companion.devtools.script_room.case_schema import ScriptCase, Step
from companion.devtools.script_room.offline_runner import drive_reply_line
from companion.devtools.script_room.rtc import MemoryRtcAdapter, RtcAdapter
from companion.service.voice.port import AudioChunk, VoiceRef


class _TTS(Protocol):
    def tts(
        self, text_stream: AsyncIterator[str], voice_ref: VoiceRef
    ) -> AsyncIterator[AudioChunk]: ...


def _next_is_barge(steps: Sequence[Step], index: int) -> bool:
    """``steps[index]`` 之后（跳过 protocol）是否为 ``inject: barge_in``。"""
    for step in steps[index + 1 :]:
        if step.protocol is not None:
            continue
        return step.inject == "barge_in"
    return False


async def _iter_one(text: str) -> AsyncIterator[str]:
    yield text


async def _publish_pcm_for_text(
    *,
    rtc: RtcAdapter,
    tts: _TTS,
    text: str,
    voice_ref: VoiceRef,
    stop_after_half: bool,
) -> int:
    """合成并 ``publish_pcm``。``stop_after_half`` 时按字节数只发约一半。"""
    chunks: list[AudioChunk] = []
    async for chunk in tts.tts(_iter_one(text), voice_ref):
        if chunk.data:
            chunks.append(chunk)
    if not chunks:
        return 0

    total = sum(len(c.data) for c in chunks)
    limit = total // 2 if stop_after_half else total
    if stop_after_half and limit <= 0:
        limit = len(chunks[0].data)  # 至少发一帧，便于断言 > 0 且 < full

    sent = 0
    for chunk in chunks:
        if sent >= limit:
            break
        await rtc.publish_pcm(chunk.data, sample_rate=chunk.sample_rate)
        sent += len(chunk.data)
    return sent


async def run_script_room(
    *,
    case: ScriptCase,
    url: str,
    token: str,
    tts: _TTS,
    wait_timeout_sec: float = 60,
    rtc: RtcAdapter | None = None,
    bridge: BridgeOverRtc | None = None,
    hello_timeout_sec: float = LEGACY_WAIT_SECONDS,
    voice_ref: VoiceRef | None = None,
) -> list[str]:
    """连接 → 等远端 → 等 hello（fail closed）→ 驱动 reply/TTS/PCM → 返回时间线类型名。"""
    own_rtc = rtc is None
    if rtc is None:
        rtc = MemoryRtcAdapter()
    if bridge is None:
        bridge = BridgeOverRtc(rtc, hello_timeout_sec=hello_timeout_sec)
    else:
        bridge.hello_timeout_sec = hello_timeout_sec

    if voice_ref is None:
        voice_ref = VoiceRef(provider="fake", voice_id="script")

    publisher = SpeechPublisher(bridge)  # type: ignore[arg-type]
    budget = CueBudget()
    turn_id = f"script-{case.id}"
    synthesize = case.audios != "none"
    cancelled = False

    try:
        await rtc.connect(url, token)
        await rtc.wait_for_remote_participant(timeout=wait_timeout_sec)
        await bridge.wait_for_hello()

        await publisher.start_reply()

        for i, step in enumerate(case.steps):
            if step.expect_reply is not None:
                barge_after = _next_is_barge(case.steps, i)
                lines = list(step.expect_reply)
                for line_i, line in enumerate(lines):
                    said = await drive_reply_line(
                        line,
                        publisher=publisher,
                        bridge=bridge,  # type: ignore[arg-type]
                        turn_id=turn_id,
                        budget=budget,
                    )
                    if not synthesize or not said:
                        continue
                    is_last = line_i == len(lines) - 1
                    stop_half = barge_after and is_last
                    # 多句 line 时，只对最后一个 say 片段做半程截断
                    for say_i, say_text in enumerate(said):
                        half = stop_half and say_i == len(said) - 1
                        await _publish_pcm_for_text(
                            rtc=rtc,
                            tts=tts,
                            text=say_text,
                            voice_ref=voice_ref,
                            stop_after_half=half,
                        )
            elif step.inject == "barge_in":
                await publisher.cancel()
                cancelled = True
                break
            # user / protocol：live runner 不执行（protocol 供断言；user 留给 capture）

        if not cancelled:
            await publisher.finish()

        return list(bridge.types)
    finally:
        if own_rtc:
            await rtc.close()
