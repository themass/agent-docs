"""剧本房 Live ScriptRoomRunner：hello 门禁 + barge 截断 PCM。"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from companion.devtools.script_room.case_schema import load_case
from companion.devtools.script_room.rtc import MemoryRtcAdapter
from companion.service.voice.fake import FakeVoiceProvider
from companion.service.voice.port import VoiceRef

CASES = Path(__file__).resolve().parents[1] / "cases" / "voice"


def _pcm_bytes(rtc: MemoryRtcAdapter) -> int:
    return sum(len(frame) for kind, frame, _sr in rtc.published if kind == "pcm")


def _full_utterance_bytes(tts: FakeVoiceProvider, texts: list[str]) -> int:
    """不经 runner：同一 FakeVoiceProvider 规则下全文合成的字节数。"""
    voice = VoiceRef(provider="fake", voice_id="script")
    total = 0
    for text in texts:
        for chunk in tts._chunks(text, voice):
            total += len(chunk.data)
    return total


@pytest.mark.asyncio
async def test_runner_waits_for_hello_before_first_seg():
    from companion.devtools.script_room.runner import run_script_room

    case = load_case(CASES / "greet_emotion.yaml")
    rtc = MemoryRtcAdapter()
    tts = FakeVoiceProvider()

    async def _join_only() -> None:
        await asyncio.sleep(0.01)
        rtc.simulate_remote_join()

    join_task = asyncio.create_task(_join_only())
    with pytest.raises(TimeoutError):
        await run_script_room(
            case=case,
            url="mem://room",
            token="tok",
            tts=tts,
            rtc=rtc,
            wait_timeout_sec=1.0,
            hello_timeout_sec=0.05,
        )
    await join_task

    # fail closed：无 speech.seg 数据、无 PCM
    data_types = []
    from companion.agent.protocol import decode

    for item in rtc.published:
        if item[0] != "data":
            continue
        env, _ = decode(item[2])
        if env is not None:
            data_types.append(env.t)
    assert "speech.seg" not in data_types
    assert _pcm_bytes(rtc) == 0


@pytest.mark.asyncio
async def test_runner_barge_stops_pcm_and_emits_cancel():
    from companion.devtools.script_room.bridge_over_rtc import BridgeOverRtc
    from companion.devtools.script_room.runner import run_script_room

    case = load_case(CASES / "barge_mid_sentence.yaml")
    rtc = MemoryRtcAdapter()
    tts = FakeVoiceProvider()
    bridge = BridgeOverRtc(rtc, hello_timeout_sec=1.0)

    async def _join_and_hello() -> None:
        await asyncio.sleep(0.01)
        rtc.simulate_remote_join()
        await bridge.simulate_hello()

    feed = asyncio.create_task(_join_and_hello())
    timeline = await run_script_room(
        case=case,
        url="mem://room",
        token="tok",
        tts=tts,
        rtc=rtc,
        bridge=bridge,
        wait_timeout_sec=1.0,
        hello_timeout_sec=1.0,
    )
    await feed

    assert "control.cancel" in timeline
    assert "speech.seg" in timeline

    # barge 截断：PCM 少于两句全文合成
    full = _full_utterance_bytes(tts, ["听到了。", "累了就先歇会儿吧。"])
    assert _pcm_bytes(rtc) < full
    assert _pcm_bytes(rtc) > 0
