"""CueCompiler：caps / 预算 / at 形状 / 溢出（P3 / §13）。"""

from __future__ import annotations

from companion.agent.protocol.cue_compiler import (
    MAX_CUES_PER_SEG,
    MAX_CUES_PER_TURN,
    CueBudget,
    compile_cues,
)
from companion.agent.protocol.cue_intent import CueIntent


def _emotion(name: str = "joy", phase: str = "start") -> CueIntent:
    return CueIntent(kind="emotion", name=name, phase=phase)


def test_compile_attaches_at_and_keeps_order():
    compiled = compile_cues(
        [_emotion("joy"), _emotion("calm", phase="after")],
        speech_id="sp_1",
        seg_idx=2,
    )
    assert len(compiled) == 2
    assert compiled[0].event_type == "presentation.emotion"
    assert compiled[0].args == {"name": "joy"}
    assert compiled[0].at == {"speech": "sp_1", "seg": 2, "phase": "start"}
    assert compiled[1].at["phase"] == "after"


def test_unsupported_kinds_are_dropped_by_caps():
    budget = CueBudget()
    compiled = compile_cues(
        [
            CueIntent(kind="gesture", name="nod"),
            _emotion("joy"),
        ],
        speech_id="sp_1",
        seg_idx=0,
        caps={"presentation.emotion": 1, "presentation.gesture": 0},
        budget=budget,
    )
    assert [c.args["name"] for c in compiled] == ["joy"]
    assert budget.stats.cues_dropped_unsupported == 1
    assert budget.stats.cues_emitted == 1


def test_gesture_and_gaze_emit_when_caps_enabled():
    budget = CueBudget()
    compiled = compile_cues(
        [
            CueIntent(kind="gesture", name="nod", params={"repeat": 1}, phase="after"),
            CueIntent(kind="gaze", name="look_user"),
            _emotion("joy"),
        ],
        speech_id="sp_1",
        seg_idx=1,
        caps={
            "presentation.emotion": 1,
            "presentation.gesture": 1,
            "presentation.gaze": 1,
        },
        budget=budget,
    )
    # 每段上限 2：第三条 emotion 被预算裁掉。
    assert [(c.event_type, c.args) for c in compiled] == [
        ("presentation.gesture", {"id": "nod", "repeat": 1}),
        ("presentation.gaze", {"name": "look_user"}),
    ]
    assert compiled[0].at == {"speech": "sp_1", "seg": 1, "phase": "after"}
    assert budget.stats.cues_emitted == 2
    assert budget.stats.cues_dropped_cap == 1


def test_per_segment_cap():
    intents = [_emotion(f"e{i}") for i in range(5)]
    budget = CueBudget()
    compiled = compile_cues(intents, speech_id="sp_1", seg_idx=0, budget=budget)
    assert len(compiled) == MAX_CUES_PER_SEG
    assert budget.stats.cues_dropped_cap >= 3


def test_per_turn_cap_shared_across_segments():
    budget = CueBudget()
    first = compile_cues(
        [_emotion("a"), _emotion("b")],
        speech_id="sp_1",
        seg_idx=0,
        budget=budget,
    )
    second = compile_cues(
        [_emotion("c"), _emotion("d"), _emotion("e")],
        speech_id="sp_1",
        seg_idx=1,
        budget=budget,
    )
    assert len(first) + len(second) == MAX_CUES_PER_TURN
    assert budget.remaining == 0


def test_overflow_payload_is_dropped():
    huge = CueIntent(kind="emotion", name="x" * 5000)
    budget = CueBudget()
    compiled = compile_cues([huge], speech_id="sp_1", seg_idx=0, budget=budget)
    assert compiled == []
    assert budget.stats.cues_dropped_overflow == 1
