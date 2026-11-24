"""``AnchoredCuePublisher`` 按客户端 ``degrade_level`` 节流（backlog B4）。

依据是端侧 ``DegradeController.shouldEmit`` 那张表：L1 起丢非 state/emotion 的
presentation，L2 起 presentation 全丢。客户端反正会丢，服务端继续发就是纯浪费——
而且浪费的恰好是弱网下最贵的带宽，挤的是真正要保的语音路径。所以这里把
「客户端会丢」翻译成「服务端不发」，并计入编译统计，账目才对得上。
"""

from __future__ import annotations

from types import SimpleNamespace

from companion.agent.protocol.cue_intent import CueIntent
from companion.api.livekit.anchored_cues import AnchoredCuePublisher

V2_CAPS = {"presentation.emotion": 1, "presentation.gesture": 1, "presentation.gaze": 1}


class _FakeBridge:
    """只要 ``ack`` / ``telemetry`` / ``publish`` 三样——publisher 的鸭子类型边界。"""

    def __init__(self, telemetry: dict | None = None) -> None:
        self.ack = SimpleNamespace(compat="v2", caps=dict(V2_CAPS))
        self.telemetry = telemetry
        self.sent: list[tuple[str, dict]] = []

    async def publish(self, event_type: str, args: dict, *, topic: str, at=None) -> bool:
        self.sent.append((event_type, args))
        return True


def _intents() -> list[CueIntent]:
    return [
        CueIntent(kind="emotion", name="joy"),
        CueIntent(kind="gesture", name="wave"),
    ]


async def _run(telemetry: dict | None):
    bridge = _FakeBridge(telemetry)
    pub = AnchoredCuePublisher(bridge)
    sent = await pub.publish_for_segment(_intents(), speech_id="s1", seg_idx=0)
    return sent, bridge.sent, pub.stats


# ---------------------------------------------------------------- 基线不动


async def test_l0_and_missing_health_send_everything():
    """没健康包 / L0：与 B4 之前的行为逐字节一致。

    老客户端、刚握手还没发过 health 的连接，都在这一档。
    """
    for telemetry in (None, {}, {"degrade_level": "L0"}):
        sent, wire, stats = await _run(telemetry)
        assert sent == 2, telemetry
        assert [t for t, _ in wire] == ["presentation.emotion", "presentation.gesture"]


async def test_unparseable_level_falls_back_to_l0():
    """字段是垃圾值时回退 L0：宁可照发，也不因解析失败把她整成哑巴。"""
    sent, wire, _ = await _run({"degrade_level": "degraded"})
    assert sent == 2


# ---------------------------------------------------------------- 分档节流


async def test_l1_keeps_emotion_drops_gesture():
    """L1 镜像端侧 shouldEmit：emotion 留（端上自己再半频），gesture/gaze 丢。"""
    sent, wire, _ = await _run({"degrade_level": "L1"})
    assert [t for t, _ in wire] == ["presentation.emotion"]
    assert sent == 1


async def test_l2_l3_l4_drop_all_presentation():
    """L2 起端侧 presentation 全丢——服务端一条都不该再发。"""
    for level in ("L2", "L3", "L4"):
        sent, wire, _ = await _run({"degrade_level": level})
        assert sent == 0 and wire == [], level


async def test_level_beyond_the_ladder_clamps_to_worst():
    """看不懂的档位数字（L9）按最坏处理：它只会来自真降级的怪值，不该多发。"""
    sent, wire, _ = await _run({"degrade_level": "L9"})
    assert sent == 0


# ---------------------------------------------------------------- 计数


async def test_degrade_drops_are_counted_in_stats():
    """丢的必须看得见：§14.3 的账里要有 cues_dropped_degrade 这一项。"""
    sent, _, stats = await _run({"degrade_level": "L1"})
    assert sent == 1
    assert stats.cues_dropped_degrade == 1
    assert stats.cues_emitted == 1


# ---------------------------------------------------------------- 可观测性（emotion-cue RCA 20261124）


async def test_successful_send_is_logged(caplog):
    """「服务端到底发没发 cue」必须能从 voice.log 直接 grep 出来。

    11-23 对账用 `grep presentation.emotion` 判服务端没发——但 publish 成功本来就是
    静默的，这个 grep 对正常通话也永远是空。不发一条发出行，下次排障还得猜。
    """
    import logging

    bridge = _FakeBridge({"degrade_level": "L0"})
    pub = AnchoredCuePublisher(bridge)
    with caplog.at_level(logging.INFO, logger="companion.api.livekit.anchored_cues"):
        sent = await pub.publish_for_segment(
            [CueIntent(kind="emotion", name="joy")], speech_id="s1", seg_idx=0)
    assert sent == 1
    lines = [r.getMessage() for r in caplog.records if "cue sent" in r.getMessage()]
    assert any("presentation.emotion" in m and "s1" in m for m in lines)


async def test_degrade_gate_drop_is_logged(caplog):
    """降级闸丢的 cue 要留一行：三个生产 job 全窗 degrade=L3、cue 一条没发，
    日志里却没有任何「闸掉了几条」——没这行，闸掉和没生成在日志里长得一样。
    """
    import logging

    bridge = _FakeBridge({"degrade_level": "L3"})
    pub = AnchoredCuePublisher(bridge)
    with caplog.at_level(logging.INFO, logger="companion.api.livekit.anchored_cues"):
        sent = await pub.publish_for_segment(_intents(), speech_id="s2", seg_idx=1)
    assert sent == 0
    lines = [r.getMessage() for r in caplog.records if "cue gate" in r.getMessage()]
    assert any("L3" in m and "s2" in m for m in lines)
