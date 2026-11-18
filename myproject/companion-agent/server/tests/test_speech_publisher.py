"""分批声明（§9.3.1）：SpeechStream 段号、bridge 的 speech.extend 闸、SpeechPublisher 的发送顺序。

SpeechPublisher 只依赖 bridge 的几个方法，这里用假 bridge 记录调用序列，直接断言顺序。
"""

from __future__ import annotations

from typing import Any

from companion.agent.protocol import negotiate, parse_hello
from companion.agent.protocol.catalog import TOPIC_CUE
from companion.agent.protocol.handshake import SERVER_CAPS
from companion.agent.protocol.speech_plan import MAX_SEGMENTS, SpeechStream
from companion.api.livekit.protocol_bridge import ProtocolBridge
from companion.api.livekit.speech_publisher import SpeechPublisher

from test_protocol_speech import _Sink, _bridge, _v1_bridge, _v2_bridge


# ------------------------------------------------------------ SpeechStream


def test_stream_numbers_segments_contiguously_and_skips_blank():
    s = SpeechStream(turn_id="tn_1")
    assert s.push("   ") is None
    a = s.push("你好啊")
    b = s.push("今天天气不错")
    assert a is not None and b is not None
    assert (a.idx, b.idx) == (0, 1)
    assert s.declared == 2


def test_stream_stops_declaring_past_max_segments():
    s = SpeechStream(turn_id="tn_1")
    segs = [s.push(f"第{i}句。") for i in range(MAX_SEGMENTS + 3)]
    declared = [x for x in segs if x is not None]
    assert len(declared) == MAX_SEGMENTS
    assert s.declared == MAX_SEGMENTS


# ------------------------------------------------------------ bridge.speech_extend


async def test_speech_extend_goes_out_on_cue_topic_for_v2():
    sink = _Sink()
    bridge = _v2_bridge(sink)
    s = SpeechStream(turn_id="tn_1", speech_id="sp_1")
    first = s.push("你好")
    second = s.push("再见")
    assert first is not None and second is not None
    assert await bridge.speech_extend("sp_1", (second,))
    [(topic, t, args)] = sink.envelopes()
    assert (topic, t) == (TOPIC_CUE, "speech.extend")
    assert args == {
        "speech_id": "sp_1",
        "segments": [{"idx": 1, "chars": second.chars, "est_ms": second.est_ms}],
    }


async def test_speech_extend_blocked_on_v1():
    sink = _Sink()
    bridge = _v1_bridge(sink)
    assert not await bridge.speech_extend("sp_1", ())
    assert sink.sent == []


def test_can_batch_needs_both_timing_and_extend():
    sink = _Sink()
    bridge = _v2_bridge(sink)
    assert bridge.can_batch()

    timing_only = _bridge_with_caps(sink, {"speech.timing": 1})
    assert not timing_only.can_batch()

    assert not _v1_bridge(sink).can_batch()


def _bridge_with_caps(sink: _Sink, caps: dict[str, int]) -> ProtocolBridge:
    bridge = _bridge(sink)
    bridge.ack = negotiate(parse_hello({"proto": {"min": 2, "max": 2}, "caps": caps}), sid="s-1")
    return bridge


# ------------------------------------------------------------ SpeechPublisher 顺序


class _FakeBridge:
    """记录调用顺序的假 bridge。``begin_ok`` 控制 begin 是否被接受。"""

    def __init__(self, *, batch: bool = True, begin_ok: bool = True) -> None:
        self.calls: list[tuple[str, Any]] = []
        self._batch = batch
        self._begin_ok = begin_ok

    async def speech_begin(self, plan: Any) -> bool:
        self.calls.append(("begin", (plan.speech_id, [s.idx for s in plan.segments])))
        return self._begin_ok

    def can_batch(self) -> bool:
        return self._batch

    async def speech_extend(self, speech_id: str, segments: Any) -> bool:
        self.calls.append(("extend", (speech_id, [s.idx for s in segments])))
        return True

    async def speech_end(self, speech_id: str) -> bool:
        self.calls.append(("end", speech_id))
        return True

    async def cancel_speech(self, speech_id: str, reason: str = "user_barge_in") -> bool:
        self.calls.append(("cancel", (speech_id, reason)))
        return True


async def test_first_sentence_begins_later_sentences_extend_in_order():
    fake = _FakeBridge()
    pub = SpeechPublisher(fake)  # type: ignore[arg-type]
    await pub.start_reply()
    await pub.say("你好啊", turn_id="tn_1")
    await pub.say("今天天气不错", turn_id="tn_1")
    await pub.say("再见", turn_id="tn_1")

    kinds = [k for k, _ in fake.calls]
    assert kinds == ["begin", "extend", "extend"]
    speech_id = fake.calls[0][1][0]
    assert fake.calls[0][1][1] == [0]
    assert fake.calls[1][1] == (speech_id, [1])
    assert fake.calls[2][1] == (speech_id, [2])


async def test_finish_sends_end_once_and_resets():
    fake = _FakeBridge()
    pub = SpeechPublisher(fake)  # type: ignore[arg-type]
    await pub.say("你好", turn_id="tn_1")
    speech_id = fake.calls[0][1][0]

    await pub.finish()
    await pub.finish()  # 第二次是空操作

    assert fake.calls[-1] == ("end", speech_id)
    assert [k for k, _ in fake.calls].count("end") == 1
    assert pub.open_speech_id is None


async def test_cancel_is_idempotent_and_carries_reason():
    fake = _FakeBridge()
    pub = SpeechPublisher(fake)  # type: ignore[arg-type]
    await pub.say("你好", turn_id="tn_1")
    speech_id = fake.calls[0][1][0]

    await pub.cancel()
    await pub.cancel()

    cancels = [c for c in fake.calls if c[0] == "cancel"]
    assert cancels == [("cancel", (speech_id, "user_barge_in"))]


async def test_start_reply_cancels_open_speech_before_new_begin():
    fake = _FakeBridge()
    pub = SpeechPublisher(fake)  # type: ignore[arg-type]
    await pub.say("上一回合", turn_id="tn_1")
    old_id = fake.calls[0][1][0]

    await pub.start_reply()
    await pub.say("新回合", turn_id="tn_2")

    kinds = [k for k, _ in fake.calls]
    assert kinds == ["begin", "cancel", "begin"]
    assert fake.calls[1][1] == (old_id, "user_barge_in")
    assert fake.calls[2][1][0] != old_id


async def test_rejected_begin_resets_so_next_sentence_starts_fresh():
    fake = _FakeBridge(begin_ok=False)
    pub = SpeechPublisher(fake)  # type: ignore[arg-type]
    await pub.say("第一句", turn_id="tn_1")
    await pub.say("第二句", turn_id="tn_1")

    begins = [args for kind, args in fake.calls if kind == "begin"]
    assert len(begins) == 2
    assert begins[0][0] != begins[1][0]           # 新 speech_id
    assert begins[1][1] == [0]                    # 段号重新从 0 开始
    assert [k for k, _ in fake.calls] == ["begin", "begin"]


async def test_no_batch_means_sentences_are_spoken_but_not_declared():
    fake = _FakeBridge(batch=False)
    pub = SpeechPublisher(fake)  # type: ignore[arg-type]
    await pub.say("第一句", turn_id="tn_1")
    await pub.say("第二句", turn_id="tn_1")
    await pub.finish()

    assert [k for k, _ in fake.calls] == ["begin", "end"]


async def test_blank_sentence_is_not_declared():
    fake = _FakeBridge()
    pub = SpeechPublisher(fake)  # type: ignore[arg-type]
    await pub.say("   ", turn_id="tn_1")
    assert fake.calls == []


async def test_bridge_failure_never_raises():
    class _Boom(_FakeBridge):
        async def speech_begin(self, plan: Any) -> bool:
            raise RuntimeError("socket gone")

    pub = SpeechPublisher(_Boom())  # type: ignore[arg-type]
    await pub.say("你好", turn_id="tn_1")   # 不抛
    assert pub.open_speech_id is None


async def test_overflow_sentences_are_not_declared_past_max():
    fake = _FakeBridge()
    pub = SpeechPublisher(fake)  # type: ignore[arg-type]
    for i in range(MAX_SEGMENTS + 5):
        await pub.say(f"第{i}句。", turn_id="tn_1")

    declared = [k for k, _ in fake.calls if k in ("begin", "extend")]
    assert len(declared) == MAX_SEGMENTS
