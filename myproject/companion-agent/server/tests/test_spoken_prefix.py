"""已说话前缀（契约 v2 §2.2）：纯函数 + SpeechPublisher 快照 + 状态时序。

前缀计算是离线可验的核心：输入 = 我们声明过的段（est_ms 估计）+ 端侧上报的
played_ms（真实播放时钟），输出 = 她实际说出口的那段文本。它决定打断后写进
对话线程的内容，所以按纯函数逐边界断言。
"""

from __future__ import annotations

from companion.agent.protocol.speech_plan import PlannedSegment, estimate_ms, spoken_prefix
from companion.api.livekit.speech_publisher import SpeechPublisher

SEG = "听到了。"          # 4 字 → est 727 ms
SEG2 = "累了就先歇会儿吧。"  # 9 字 → est 1636 ms


def _segments() -> list[PlannedSegment]:
    return [
        PlannedSegment(idx=0, text=SEG, est_ms=estimate_ms(SEG)),
        PlannedSegment(idx=1, text=SEG2, est_ms=estimate_ms(SEG2)),
    ]


# ------------------------------------------------------------ 纯函数边界


def test_no_play_or_no_segments_yields_empty_prefix():
    assert spoken_prefix([], 1234) == ("", 0)
    assert spoken_prefix(_segments(), 0) == ("", 0)
    assert spoken_prefix(_segments(), -5) == ("", 0)


def test_exactly_at_segment_boundary_counts_full_segment_only():
    est0 = estimate_ms(SEG)
    prefix, chars = spoken_prefix(_segments(), est0)
    assert prefix == SEG
    assert chars == len(SEG)


def test_mid_second_segment_takes_proportional_chars():
    est0 = estimate_ms(SEG)
    est1 = estimate_ms(SEG2)
    # 第二句播到一半：前缀 = 第一句全文 + 第二句约一半字符。
    prefix, chars = spoken_prefix(_segments(), est0 + est1 // 2)
    assert prefix.startswith(SEG)
    assert len(prefix) == len(SEG) + round(len(SEG2) / 2)
    assert SEG2.startswith(prefix[len(SEG):])


def test_played_past_everything_prefixes_all_declared_text():
    prefix, chars = spoken_prefix(_segments(), 99_999)
    assert prefix == SEG + SEG2
    assert chars == len(SEG) + len(SEG2)


def test_prefix_never_exceeds_declared_text():
    for played in range(0, 6000, 7):
        prefix, chars = spoken_prefix(_segments(), played)
        assert (SEG + SEG2).startswith(prefix)
        assert chars == len(prefix)


# ------------------------------------------------------------ Publisher 快照


class _FakeBridge:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def speech_seg(self, speech_id: str, seg: object) -> bool:
        self.calls.append(("seg", seg))
        return True

    async def speech_end(self, speech_id: str) -> bool:
        self.calls.append(("end", speech_id))
        return True

    async def cancel_speech(self, speech_id: str, reason: str = "user_barge_in") -> bool:
        self.calls.append(("cancel", (speech_id, reason)))
        return True


async def test_cancel_without_played_ms_returns_no_prefix():
    """没上报播放位置时不猜：返回 None，上层退回全量（与改动前一致）。"""
    pub = SpeechPublisher(_FakeBridge())  # type: ignore[arg-type]
    await pub.say(SEG, turn_id="T1")
    assert await pub.cancel() is None


async def test_cancel_with_played_ms_snapshots_prefix_and_turn():
    pub = SpeechPublisher(_FakeBridge())  # type: ignore[arg-type]
    await pub.say(SEG, turn_id="T1")
    await pub.say(SEG2, turn_id="T1")

    snapshot = await pub.cancel(played_ms=estimate_ms(SEG) + 400)
    assert snapshot is not None
    assert snapshot.turn_id == "T1"
    assert snapshot.text == SEG + SEG2[: round(len(SEG2) * 400 / estimate_ms(SEG2))]
    assert snapshot.chars == len(snapshot.text)
    # 快照之后回合已关闭：再 cancel 是空操作。
    assert await pub.cancel(played_ms=10) is None


async def test_seg_args_carries_turn_id():
    pub = SpeechPublisher(_FakeBridge())  # type: ignore[arg-type]
    declared = await pub.say(SEG, turn_id="T9")
    assert declared is not None
    _, seg = declared
    args = seg.seg_args("sp_1")
    assert args["turn_id"] == "T9"
    assert args["chars"] == len(SEG)


# ------------------------------------------------------------ 状态时序（契约 v2 §1）


class _StateBridge(_FakeBridge):
    def __init__(self) -> None:
        super().__init__()
        self.states: list[str] = []

    def presentation_state(self, state: str) -> bool:  # 同步假 sink：鸭子约定
        self.states.append(state)
        return True


async def test_turn_boundary_states_follow_the_contract_order():
    bridge = _StateBridge()
    pub = SpeechPublisher(bridge, state_sink=bridge.presentation_state)  # type: ignore[arg-type]

    await pub.start_reply()                      # thinking
    await pub.say(SEG, turn_id="T1")             # speaking → seg
    await pub.say(SEG2, turn_id="T1")            # speaking → seg
    await pub.finish()                           # idle → end

    assert bridge.states == ["thinking", "speaking", "speaking", "idle"]
    kinds = [k for k, _ in bridge.calls]
    assert kinds == ["seg", "seg", "end"]


async def test_barge_cancel_sends_interrupted_state():
    bridge = _StateBridge()
    pub = SpeechPublisher(bridge, state_sink=bridge.presentation_state)  # type: ignore[arg-type]

    await pub.start_reply()
    await pub.say(SEG, turn_id="T1")
    await pub.cancel(played_ms=100)

    assert bridge.states == ["thinking", "speaking", "interrupted"]


async def test_finish_without_any_declared_seg_still_closes_state_to_idle():
    """thinking 发出去了但一段都没声明（未握手 / 全空白）：状态不能卡在 thinking。"""
    bridge = _StateBridge()
    pub = SpeechPublisher(bridge, state_sink=bridge.presentation_state)  # type: ignore[arg-type]

    await pub.start_reply()
    await pub.finish()

    assert bridge.states == ["thinking", "idle"]
    assert bridge.calls == []                   # 没有打开的 speech：不发孤儿 end


async def test_no_state_sink_keeps_previous_publisher_behavior():
    bridge = _FakeBridge()
    pub = SpeechPublisher(bridge)  # type: ignore[arg-type]
    await pub.start_reply()
    await pub.say(SEG, turn_id="T1")
    await pub.finish()
    kinds = [k for k, _ in bridge.calls]
    assert kinds == ["seg", "end"]
