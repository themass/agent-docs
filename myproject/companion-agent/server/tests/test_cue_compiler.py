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


# ---------------------------------------------------------------- intensity（B7 / §18.6）


def test_intensity_passes_through_when_in_range():
    """合法的 0..1 值原样进 args：这是端侧微调表情强度的唯一通道。"""
    compiled = compile_cues(
        [CueIntent(kind="emotion", name="joy", params={"intensity": 0.4})],
        speech_id="sp_1",
        seg_idx=0,
    )
    assert compiled[0].args == {"name": "joy", "intensity": 0.4}


def test_intensity_is_clamped_into_range_not_dropped():
    """模型写 1.8 或 -0.2（§18.6 的滥用形态）时压回 0/1，而不是整条丢掉。

    钳制在编译期做：结构化与标签两条路径的 intensity 都从 params 到这里，
    一处看住两个入口。cue 本身仍然有效——过度兴奋的表情压成满格，
    好过让她的脸对这句话毫无反应。
    """
    compiled = compile_cues(
        [
            CueIntent(kind="emotion", name="joy", params={"intensity": 1.8}),
            CueIntent(kind="emotion", name="calm", params={"intensity": -0.2}),
        ],
        speech_id="sp_1",
        seg_idx=0,
    )
    assert compiled[0].args["intensity"] == 1.0
    assert compiled[1].args["intensity"] == 0.0


def test_non_numeric_intensity_is_dropped_the_cue_kept():
    """字符串 / null 这类坏值只丢参数，不丢 cue：端侧缺省 1.0 是合法语义。"""
    budget = CueBudget()
    compiled = compile_cues(
        [
            CueIntent(kind="emotion", name="joy", params={"intensity": "very high"}),
            CueIntent(kind="emotion", name="calm", params={"intensity": None}),
        ],
        speech_id="sp_1",
        seg_idx=0,
        budget=budget,
    )
    assert len(compiled) == 2
    assert all("intensity" not in c.args for c in compiled)
    assert budget.stats.cues_dropped_bad_intensity == 2
