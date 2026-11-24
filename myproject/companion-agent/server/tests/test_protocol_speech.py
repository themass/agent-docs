"""语音时间线的服务端发送侧：能力闸、段号、bridge 的 speech 方法（§9.3 / §10 / §13）。"""

from __future__ import annotations

from typing import Any

from companion.agent.protocol import decode, legacy_ack, negotiate, parse_hello, supports
from companion.agent.protocol.catalog import TOPIC_CTL, TOPIC_CUE
from companion.agent.protocol.handshake import SERVER_CAPS
from companion.agent.protocol.speech_plan import SpeechStream, estimate_ms
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


def test_speech_events_are_gated_by_speech_v1_capability():
    """caps 的键是能力名；speech.* 必须经 CAP_FOR_EVENT 映射到 speech.v1 才能发。"""
    ack = negotiate(parse_hello({"proto": {"min": 2, "max": 2}, "caps": {"speech.v1": 1}}), sid="s")
    assert supports(ack, "speech.seg")
    assert supports(ack, "speech.end")
    assert supports(ack, "control.cancel")
    assert not supports(ack, "presentation.emotion")


def test_speech_events_blocked_when_client_lacks_speech_v1():
    ack = negotiate(parse_hello({"proto": {"min": 2, "max": 2}, "caps": {"presentation.state": 1}}), sid="s")
    assert not supports(ack, "speech.seg")


def test_speech_events_blocked_on_v1():
    bridge = _v1_bridge(_Sink())
    assert not supports(bridge.ack, "speech.seg")


# ------------------------------------------------------------ 段号


def test_stream_assigns_contiguous_idx_and_estimates():
    s = SpeechStream(turn_id="tn_1", speech_id="sp_1")
    a = s.push("你好啊")
    b = s.push("今天天气不错")
    assert a is not None and b is not None
    assert [a.idx, b.idx] == [0, 1]
    assert a.est_ms == estimate_ms("你好啊")
    # turn_id 进 args（契约 v2 §2.3）：端侧与历史侧都靠它把段对回回合。
    assert a.seg_args("sp_1") == {"speech_id": "sp_1", "idx": 0, "chars": 3,
                                  "est_ms": estimate_ms("你好啊"), "turn_id": "tn_1"}


def test_seg_args_omits_dur_ms_when_unset_and_includes_when_set():
    from companion.agent.protocol.speech_plan import PlannedSegment

    plain = PlannedSegment(idx=0, text="你好", est_ms=400)
    assert "dur_ms" not in plain.seg_args("sp_1")
    with_dur = PlannedSegment(idx=0, text="你好", est_ms=400, dur_ms=380)
    assert with_dur.seg_args("sp_1")["dur_ms"] == 380


def test_stream_skips_blank_without_consuming_idx():
    s = SpeechStream(turn_id="tn_1")
    assert s.push("  ") is None
    assert s.push("") is None
    assert s.push("嗯").idx == 0  # type: ignore[union-attr]
    assert s.push("好").idx == 1  # type: ignore[union-attr]


def test_stream_speech_id_has_ulid_shape_when_not_given():
    s = SpeechStream(turn_id="tn_1")
    assert s.speech_id.startswith("sp_") and len(s.speech_id) == 3 + 26


# ------------------------------------------------------------ bridge 发送


async def test_speech_seg_goes_out_on_cue_topic_for_v2():
    sink = _Sink()
    bridge = _v2_bridge(sink)
    seg = SpeechStream(turn_id="tn_1").push("你好")
    assert seg is not None
    assert await bridge.speech_seg("sp_1", seg)
    [(topic, t, args)] = sink.envelopes()
    assert (topic, t) == (TOPIC_CUE, "speech.seg")
    assert args == {"speech_id": "sp_1", "idx": 0, "chars": 2,
                    "est_ms": estimate_ms("你好"), "turn_id": "tn_1"}


async def test_speech_end_carries_speech_id():
    sink = _Sink()
    bridge = _v2_bridge(sink)
    assert await bridge.speech_end("sp_1")
    [(topic, t, args)] = sink.envelopes()
    assert (topic, t) == (TOPIC_CUE, "speech.end")
    assert args == {"speech_id": "sp_1"}


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
    seg = SpeechStream(turn_id="tn_1").push("你好")
    assert seg is not None
    assert not await bridge.speech_seg("sp_1", seg)
    assert not await bridge.speech_end("sp_1")
    assert sink.sent == []
    assert bridge.unsent == {"speech.seg": 1, "speech.end": 1}


async def test_speech_on_v1_connection_is_not_sent():
    sink = _Sink()
    bridge = _v1_bridge(sink)
    assert not await bridge.cancel_speech("sp_1")
    assert not await bridge.speech_end("sp_1")
    assert sink.sent == []
