"""剧本 case：YAML 加载 + 离线协议时间线（FakeBridge）。"""

from __future__ import annotations

from pathlib import Path

from companion.agent.protocol.speech_plan import MAX_SEGMENTS
from companion.devtools.script_room.case_schema import load_case
from companion.devtools.script_room.offline_runner import run_offline

CASES = Path(__file__).resolve().parents[1] / "cases" / "voice"


def test_load_barge_case_roundtrip():
    case = load_case(CASES / "barge_mid_sentence.yaml")
    assert case.id == "barge_mid_sentence"
    assert case.audios == "synthesize"


async def test_offline_barge_case_emits_state_seg_emotion_seg_cancel():
    """契约 v2 §4：时间线含显式状态（thinking→speaking），barge 后 cancel，无后续 seg。"""
    types = await run_offline(load_case(CASES / "barge_mid_sentence.yaml"))
    assert types == [
        "presentation.state",   # thinking：回合开始生成
        "presentation.state",   # speaking：第一句 speech.seg 之前（§13-1 顺序）
        "speech.seg",
        "presentation.emotion",
        "presentation.state",   # speaking：第二句
        "speech.seg",
        "presentation.state",   # interrupted：barge
        "control.cancel",
    ]


async def test_offline_barge_case_state_vocabulary_is_lowercase_contract_order():
    """状态词汇必须是小写的契约值，顺序 thinking→speaking→…→interrupted。"""
    from companion.devtools.script_room.offline_runner import RecordingBridge

    bridge = RecordingBridge()
    await run_offline(load_case(CASES / "barge_mid_sentence.yaml"), bridge=bridge)
    assert bridge.states == ["thinking", "speaking", "speaking", "interrupted"]


async def test_offline_greet_emotion_ends_with_end_and_includes_emotion():
    types = await run_offline(load_case(CASES / "greet_emotion.yaml"))
    assert "presentation.emotion" in types
    assert types[-1] == "speech.end"


async def test_offline_multi_seg_has_at_least_two_segs_then_end():
    types = await run_offline(load_case(CASES / "multi_seg.yaml"))
    segs = [t for t in types if t == "speech.seg"]
    assert len(segs) >= 2
    assert types[-1] == "speech.end"


async def test_offline_truncation_respects_max_segments_and_finishes():
    types = await run_offline(load_case(CASES / "truncation.yaml"))
    assert types.count("speech.seg") == MAX_SEGMENTS
    assert types[-1] == "speech.end"
