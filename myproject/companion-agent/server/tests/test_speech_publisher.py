"""逐句声明（§9.3）：SpeechStream 段号、SpeechPublisher 的发送顺序与收尾。

SpeechPublisher 只依赖 bridge 的几个方法，这里用假 bridge 记录调用序列，直接断言顺序。
"""

from __future__ import annotations

from typing import Any

from companion.agent.protocol.speech_plan import MAX_SEGMENTS, SpeechStream
from companion.api.livekit.speech_publisher import SpeechPublisher


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


# ------------------------------------------------------------ SpeechPublisher 顺序


class _FakeBridge:
    """记录调用顺序的假 bridge。``seg_ok`` 控制 speech.seg 是否被接受。"""

    def __init__(self, *, seg_ok: bool = True) -> None:
        self.calls: list[tuple[str, Any]] = []
        self._seg_ok = seg_ok

    async def speech_seg(self, speech_id: str, seg: Any) -> bool:
        self.calls.append(("seg", (speech_id, seg.idx)))
        return self._seg_ok

    async def speech_end(self, speech_id: str) -> bool:
        self.calls.append(("end", speech_id))
        return True

    async def cancel_speech(self, speech_id: str, reason: str = "user_barge_in") -> bool:
        self.calls.append(("cancel", (speech_id, reason)))
        return True


async def test_every_sentence_is_declared_in_order_under_one_speech():
    fake = _FakeBridge()
    pub = SpeechPublisher(fake)  # type: ignore[arg-type]
    await pub.start_reply()
    await pub.say("你好啊", turn_id="tn_1")
    await pub.say("今天天气不错", turn_id="tn_1")
    await pub.say("再见", turn_id="tn_1")

    assert [k for k, _ in fake.calls] == ["seg", "seg", "seg"]
    speech_id = fake.calls[0][1][0]
    assert [v for _, v in fake.calls] == [(speech_id, 0), (speech_id, 1), (speech_id, 2)]


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


async def test_start_reply_cancels_open_speech_before_new_seg():
    fake = _FakeBridge()
    pub = SpeechPublisher(fake)  # type: ignore[arg-type]
    await pub.say("上一回合", turn_id="tn_1")
    old_id = fake.calls[0][1][0]

    await pub.start_reply()
    await pub.say("新回合", turn_id="tn_2")

    kinds = [k for k, _ in fake.calls]
    assert kinds == ["seg", "cancel", "seg"]
    assert fake.calls[1][1] == (old_id, "user_barge_in")
    assert fake.calls[2][1][0] != old_id
    assert fake.calls[2][1][1] == 0            # 新 speech 段号从 0 开始


async def test_rejected_first_seg_resets_so_next_sentence_starts_fresh():
    fake = _FakeBridge(seg_ok=False)
    pub = SpeechPublisher(fake)  # type: ignore[arg-type]
    await pub.say("第一句", turn_id="tn_1")
    await pub.say("第二句", turn_id="tn_1")

    segs = [args for kind, args in fake.calls if kind == "seg"]
    assert len(segs) == 2
    assert segs[0][0] != segs[1][0]            # 新 speech_id
    assert segs[1][1] == 0                     # 段号重新从 0 开始
    assert pub.open_speech_id is None


async def test_blank_sentence_is_not_declared():
    fake = _FakeBridge()
    pub = SpeechPublisher(fake)  # type: ignore[arg-type]
    await pub.say("   ", turn_id="tn_1")
    assert fake.calls == []


async def test_bridge_failure_never_raises():
    class _Boom(_FakeBridge):
        async def speech_seg(self, speech_id: str, seg: Any) -> bool:
            raise RuntimeError("socket gone")

    pub = SpeechPublisher(_Boom())  # type: ignore[arg-type]
    await pub.say("你好", turn_id="tn_1")   # 不抛
    assert pub.open_speech_id is None


async def test_overflow_sentences_are_spoken_but_not_declared_past_max():
    fake = _FakeBridge()
    pub = SpeechPublisher(fake)  # type: ignore[arg-type]
    for i in range(MAX_SEGMENTS + 5):
        await pub.say(f"第{i}句。", turn_id="tn_1")

    assert len([k for k, _ in fake.calls if k == "seg"]) == MAX_SEGMENTS
