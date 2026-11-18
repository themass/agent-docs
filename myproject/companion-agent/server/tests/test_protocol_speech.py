"""语音时间线的服务端发送侧：能力闸、段计划、bridge 的 speech 方法（§9.3 / §10 / §13）。"""

from __future__ import annotations

from typing import Any

from companion.agent.protocol import decode, legacy_ack, negotiate, parse_hello, supports
from companion.agent.protocol.catalog import TOPIC_CTL, TOPIC_CUE
from companion.agent.protocol.handshake import SERVER_CAPS
from companion.agent.protocol.speech_plan import MAX_SEGMENTS, estimate_ms, plan_speech
from companion.api.livekit.protocol_bridge import ProtocolBridge


class _Sink:
    def __init__(self) -> None:
        self.sent: list[tuple[str, bytes]] = []

    async def __call__(self, topic: str, payload: bytes) -> None:
        self.sent.append((topic, payload))

    def envelopes(self) -> list[tuple[str, str, dict[str, Any]]]:
        out = []
        for topic, payload in self.sent:
            env, _ = decode(payload)
            assert env is not None
            out.append((topic, env.t, env.args))
        return out


def _bridge(sink: _Sink) -> ProtocolBridge:
    return ProtocolBridge(send=sink, identity="agent", local_identity="agent", sid="s-1", legacy_timeout=0.01)


def _v2_bridge(sink: _Sink) -> ProtocolBridge:
    bridge = _bridge(sink)
    bridge.ack = negotiate(parse_hello({"proto": {"min": 2, "max": 2}, "caps": dict(SERVER_CAPS)}), sid="s-1")
    return bridge


def _v1_bridge(sink: _Sink) -> ProtocolBridge:
    bridge = _bridge(sink)
    bridge.ack = legacy_ack(sid="s-1")
    return bridge


# ------------------------------------------------------------ 能力闸


def test_speech_events_are_gated_by_speech_timing_capability():
    """caps 的键是能力名；speech.* 必须经 CAP_FOR_EVENT 映射到 speech.timing 才能发。"""
    ack = negotiate(parse_hello({"proto": {"min": 2, "max": 2}, "caps": {"speech.timing": 1}}), sid="s")
    assert supports(ack, "speech.begin")
    assert supports(ack, "speech.segment")
    assert supports(ack, "speech.end")
    assert not supports(ack, "presentation.emotion")


def test_speech_events_blocked_when_client_lacks_speech_timing():
    ack = negotiate(parse_hello({"proto": {"min": 2, "max": 2}, "caps": {"presentation.state": 1}}), sid="s")
    assert not supports(ack, "speech.begin")


def test_speech_events_blocked_on_v1():
    bridge = _v1_bridge(_Sink())
    assert not supports(bridge.ack, "speech.begin")


# ------------------------------------------------------------ 段计划


def test_plan_assigns_contiguous_idx_and_estimates():
    plan = plan_speech(["你好啊", "今天天气不错"], turn_id="tn_1", voice="zh_female_1")
    assert plan is not None
    assert [s.idx for s in plan.segments] == [0, 1]
    assert plan.segments[0].est_ms == estimate_ms("你好啊")
    assert plan.total_est_ms == sum(s.est_ms for s in plan.segments)
    assert plan.speech_id.startswith("sp_") and len(plan.speech_id) == 3 + 26


def test_plan_skips_blank_segments_without_consuming_idx():
    plan = plan_speech(["嗯", "  ", "", "好"], turn_id="tn_1")
    assert plan is not None
    assert [s.idx for s in plan.segments] == [0, 1]
    assert [s.text for s in plan.segments] == ["嗯", "好"]


def test_plan_returns_none_when_nothing_to_say():
    assert plan_speech(["", "  "], turn_id="tn_1") is None


def test_plan_bounds_segment_count_by_merging_tail():
    texts = [f"第{i}句" for i in range(MAX_SEGMENTS + 10)]
    plan = plan_speech(texts, turn_id="tn_1")
    assert plan is not None
    assert len(plan.segments) == MAX_SEGMENTS
    assert "".join(s.text for s in plan.segments) == "".join(texts)


def test_begin_args_match_spec_shape():
    plan = plan_speech(["你好"], turn_id="tn_1", speech_id="sp_fixed", voice="v")
    assert plan is not None
    args = plan.begin_args()
    assert args["speech_id"] == "sp_fixed"
    assert args["turn_id"] == "tn_1"
    assert args["voice"] == "v"
    assert args["segments"] == [{"idx": 0, "chars": 2, "est_ms": estimate_ms("你好")}]
    assert "dur_ms" not in args["segments"][0]


# ------------------------------------------------------------ bridge 发送


async def test_speech_begin_goes_out_on_cue_topic_for_v2():
    sink = _Sink()
    bridge = _v2_bridge(sink)
    plan = plan_speech(["你好"], turn_id="tn_1", speech_id="sp_1")
    assert plan is not None
    assert await bridge.speech_begin(plan)
    [(topic, t, args)] = sink.envelopes()
    assert (topic, t) == (TOPIC_CUE, "speech.begin")
    assert args["speech_id"] == "sp_1"


async def test_speech_segment_and_end_carry_speech_id():
    sink = _Sink()
    bridge = _v2_bridge(sink)
    assert await bridge.speech_segment("sp_1", 2, 900, start_boundary=True)
    assert await bridge.speech_end("sp_1")
    seg, end = sink.envelopes()
    assert seg[1] == "speech.segment"
    assert seg[2] == {"speech_id": "sp_1", "idx": 2, "dur_ms": 900, "start_boundary": True}
    assert end[2] == {"speech_id": "sp_1"}


async def test_cancel_speech_goes_out_on_ctl_topic():
    sink = _Sink()
    bridge = _v2_bridge(sink)
    assert await bridge.cancel_speech("sp_1")
    [(topic, t, args)] = sink.envelopes()
    assert (topic, t) == (TOPIC_CTL, "control.cancel")
    assert args == {"speech_id": "sp_1", "reason": "user_barge_in"}


async def test_speech_before_handshake_is_not_sent_and_is_counted():
    sink = _Sink()
    bridge = _bridge(sink)
    plan = plan_speech(["你好"], turn_id="tn_1", speech_id="sp_1")
    assert plan is not None
    assert not await bridge.speech_begin(plan)
    assert not await bridge.speech_end("sp_1")
    assert sink.sent == []
    assert bridge.unsent == {"speech.begin": 1, "speech.end": 1}


async def test_speech_on_v1_connection_is_not_sent():
    sink = _Sink()
    bridge = _v1_bridge(sink)
    assert not await bridge.cancel_speech("sp_1")
    assert not await bridge.speech_end("sp_1")
    assert sink.sent == []
