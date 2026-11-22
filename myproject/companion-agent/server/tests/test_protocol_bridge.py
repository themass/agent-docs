"""协议 v2 接线层：收包、握手、身份白名单（§5 / §7 / §14.1 / §14.2）。

这里锁的是**接线**而不是纯逻辑：纯逻辑已经由 ``test_protocol_codec`` 与
``test_protocol_handshake`` 覆盖。这一层最容易出的错是「逻辑都对，但没人调用它」
——服务端原来没有任何 ``data_received`` 处理器，客户端发什么都落不到地上。
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from companion.agent.protocol import (
    TOPIC_CTL,
    TOPIC_CUE,
    TOPIC_TEL,
    decode,
    encode,
    new_envelope,
)
from companion.api.livekit import protocol_bridge
from companion.api.livekit.protocol_bridge import ProtocolBridge, attach

CLIENT = "user-1002"
AGENT = "agent-linche"


class _Sink:
    """把 bridge 发出的消息收进列表。"""

    def __init__(self) -> None:
        self.sent: list[tuple[str, bytes]] = []

    async def __call__(self, topic: str, payload: bytes) -> None:
        self.sent.append((topic, payload))

    def types(self) -> list[str]:
        return [decode(payload)[0].t for _, payload in self.sent]

    def last_args(self) -> dict[str, Any]:
        _, payload = self.sent[-1]
        envelope, status = decode(payload)
        assert envelope is not None, status
        return envelope.args


def _bridge(sink: _Sink | None = None, *, legacy_timeout: float = 0.05) -> ProtocolBridge:
    return ProtocolBridge(
        send=sink or _Sink(),
        identity=AGENT,
        local_identity=AGENT,
        sid="s-test",
        legacy_timeout=legacy_timeout,
    )


def _hello_bytes(proto_min: int = 2, proto_max: int = 2, caps: dict[str, int] | None = None,
                 seq: int = 0, ep: str = "ep-a", ident: str = "h-1") -> bytes:
    return encode(
        new_envelope(
            "control.hello",
            args={
                "proto": {"min": proto_min, "max": proto_max},
                "caps": caps if caps is not None else {"presentation.emotion": 1},
                "limits": {"max_payload_bytes": 4096},
                "client": {"app": "companion", "version": "1.0", "sdk": "2.29.0"},
            },
            seq=seq,
            ep=ep,
            ident=ident,
        )
    )


def _packet(data: bytes, *, identity: str | None = "kind-standard", kind: Any = "STANDARD",
            topic: str | None = TOPIC_CTL) -> dict[str, Any]:
    """假的 DataPacket。``identity`` 与 ``kind`` 是两件事：前者是谁，后者是哪类进程。"""
    identity_value = None if identity == "kind-standard" else identity
    publisher = None if identity_value is None else _Publisher(identity_value, kind)
    return {"data": data, "topic": topic, "participant": publisher}


class _Publisher:
    def __init__(self, identity: str, kind: Any) -> None:
        self.identity = identity
        self.kind = kind


async def _feed(bridge: ProtocolBridge, packet: dict[str, Any]):
    publisher = packet["participant"]
    return await bridge.on_data(
        packet["data"],
        topic=packet["topic"],
        publisher_identity=getattr(publisher, "identity", None),
        publisher_kind=getattr(publisher, "kind", None),
    )


# ---------------------------------------------------------------- 握手

async def test_hello_gets_an_ack_with_the_intersection():
    sink = _Sink()
    bridge = _bridge(sink)
    await _feed(bridge, _packet(_hello_bytes(caps={"presentation.emotion": 1, "speech.v1": 3}),
                               identity=CLIENT))

    assert sink.types() == ["control.hello_ack"]
    args = sink.last_args()
    assert args["compat"] == "v2"
    assert args["sid"] == "s-test"
    # 交集：客户端报了 3，服务端只有 1，取小。
    assert args["caps"]["speech.v1"] == 1
    # 客户端没报的能力不该出现在交集里。
    assert "presentation.state" not in args["caps"]


async def test_media_image_negotiates_when_the_client_declares_it():
    """图片消息（P1）：客户端报 ``media.image`` → ack 里有它。

    键名是契约本身：客户端 ``CLIENT_CAPS`` 里拼的是 "media.image"，我们这边写成
    别的任何拼法，交集里就永远少这一项，而握手看不出任何异常。
    """
    sink = _Sink()
    bridge = _bridge(sink)
    await _feed(bridge, _packet(_hello_bytes(caps={"media.image": 1}), identity=CLIENT))

    assert sink.last_args()["caps"] == {"media.image": 1}


async def test_an_older_client_without_media_image_still_completes_the_handshake():
    """老客户端不报这一项：能力缺席，握手照常成功（negotiate 丢弃能力项、不拒握手）。"""
    sink = _Sink()
    bridge = _bridge(sink)
    await _feed(bridge, _packet(_hello_bytes(caps={"presentation.emotion": 1}), identity=CLIENT))

    args = sink.last_args()
    assert args["compat"] == "v2"
    assert "media.image" not in args["caps"]


async def test_no_hello_within_the_window_means_v1():
    bridge = _bridge(legacy_timeout=0.01)
    ack = await bridge.wait_for_hello()
    assert ack.compat == "v1"
    assert ack.caps == {}
    assert bridge.legacy


async def test_a_hello_inside_the_window_wins_over_the_v1_fallback():
    bridge = _bridge(legacy_timeout=1.0)
    await _feed(bridge, _packet(_hello_bytes(), identity=CLIENT))
    ack = await bridge.wait_for_hello()
    assert ack.compat == "v2"
    assert not bridge.legacy


async def test_a_resent_hello_after_reconnect_is_renegotiated():
    """重发不是错误（§7）：服务端在连接期内任意时刻都要重新协商。"""
    sink = _Sink()
    bridge = _bridge(sink)
    await _feed(bridge, _packet(_hello_bytes(ident="h-1"), identity=CLIENT))
    await _feed(bridge, _packet(_hello_bytes(ident="h-2", ep="ep-b", seq=0), identity=CLIENT))
    assert sink.types() == ["control.hello_ack", "control.hello_ack"]
    assert bridge.ack is not None and bridge.ack.compat == "v2"


async def test_an_incompatible_hello_gets_an_explicit_ack_instead_of_silence():
    sink = _Sink()
    bridge = _bridge(sink)
    await _feed(bridge, _packet(_hello_bytes(proto_min=3, proto_max=3), identity=CLIENT))

    assert sink.types() == ["control.hello_ack"]
    assert sink.last_args()["compat"] == "incompatible"
    # 协商没成功：之后一条 cmp.cue 都不该发出去。
    assert not await bridge.publish("presentation.emotion", {}, topic=TOPIC_CUE)


async def test_v1_connections_get_no_cmp_messages():
    bridge = _bridge()
    await bridge.wait_for_hello()
    assert not await bridge.publish("presentation.emotion", {}, topic=TOPIC_CUE)


# ---------------------------------------------------------------- 身份白名单

async def test_another_client_cannot_forge_user_input():
    """§14.2：``cmp.tel`` 只能由客户端发——但「客户端」指用户设备，不是另一个 agent。"""
    bridge = _bridge()
    payload = encode(
        new_envelope("telemetry.health", args={}, seq=0, ep="ep", ident="t-1")
    )
    await _feed(bridge, _packet(payload, identity=AGENT, kind="AGENT", topic=TOPIC_TEL))
    assert bridge.receiver.dropped_unauthorized == 1
    assert bridge.receiver.applied == 0


async def test_our_own_packets_are_never_user_input():
    sink = _Sink()
    bridge = _bridge(sink)
    payload = encode(
        new_envelope("control.hello", args={"proto": {"min": 2, "max": 2}, "caps": {}},
                     seq=0, ep="ep", ident="h")
    )
    await _feed(bridge, _packet(payload, identity=AGENT, kind="STANDARD"))
    assert bridge.receiver.dropped_unauthorized == 1
    assert sink.sent == []


@pytest.mark.parametrize("kind", ["AGENT", "EGRESS"])
async def test_server_side_kinds_are_refused_as_senders(kind):
    bridge = _bridge()
    payload = encode(new_envelope("control.hello", args={"proto": {"min": 2, "max": 2}, "caps": {}},
                                 seq=0, ep="ep", ident="h"))
    await _feed(bridge, _packet(payload, identity="someone", kind=kind))
    assert bridge.receiver.dropped_unauthorized == 1


@pytest.mark.parametrize("kind", ["STANDARD", "SIP", "CONNECTOR", "UNKNOWN"])
async def test_human_backed_kinds_can_send(kind):
    """SIP 与 CONNECTOR 背后是真人；拒掉它们等于让电话用户用不了。"""
    bridge = _bridge()
    payload = encode(new_envelope("control.hello", args={"proto": {"min": 2, "max": 2},
                                                         "caps": {}}, seq=0, ep="ep", ident="h"))
    await _feed(bridge, _packet(payload, identity=CLIENT, kind=kind))
    assert bridge.receiver.dropped_unauthorized == 0


async def test_enum_kind_names_are_understood():
    """``Participant.kind`` 在不同版本里是枚举、整型或字符串。"""
    sink = _Sink()
    bridge = _bridge(sink)

    class _Kind:
        name = "agent"

    await _feed(bridge, _packet(_hello_bytes(), identity="x", kind=_Kind()))
    assert bridge.receiver.dropped_unauthorized == 1


# ---------------------------------------------------------------- 方向

async def test_a_cue_sent_by_a_client_is_refused():
    """客户端不能往 ``cmp.cue`` 发。方向不对要单独计数，不能和「坏包」混在一起。"""
    bridge = _bridge()
    payload = encode(new_envelope("presentation.emotion", args={}, seq=0, ep="ep", ident="c-1"))
    await _feed(bridge, _packet(payload, identity=CLIENT, topic=TOPIC_CUE))
    assert bridge.receiver.dropped_unauthorized == 1
    assert bridge.receiver.applied == 0


# ---------------------------------------------------------------- 健壮性

async def test_a_packet_without_a_topic_is_counted_not_crashed():
    bridge = _bridge()
    await _feed(bridge, _packet(_hello_bytes(), identity=CLIENT, topic=None))
    assert bridge.receiver.dropped_bad == 1
    assert bridge.receiver.received == 1


async def test_garbage_does_not_stop_the_next_message():
    """§14.1：一条坏消息不能影响后续消息。"""
    sink = _Sink()
    bridge = _bridge(sink)
    for bad in (b"", b"{", b"\xff\xfe", b"[]", b'{"v":2}'):
        await _feed(bridge, _packet(bad, identity=CLIENT))
    assert bridge.receiver.dropped_bad == 5

    await _feed(bridge, _packet(_hello_bytes(), identity=CLIENT))
    assert sink.types() == ["control.hello_ack"]


async def test_an_unknown_event_type_is_counted_separately():
    """陌生 ``t`` 不是「坏包」：消息是好的，只是这一版不认识（§5 规则 2）。"""
    bridge = _bridge()
    payload = json.dumps({
        "v": 2, "t": "presentation.teleport", "id": "x", "seq": 0, "ep": "e", "args": {},
    }).encode()
    await _feed(bridge, _packet(payload, identity=CLIENT, topic=TOPIC_CUE))
    assert bridge.receiver.dropped_unknown == 1
    assert bridge.receiver.dropped_bad == 0


async def test_a_failing_handler_is_isolated():
    bridge = _bridge()

    async def _boom(envelope, topic):
        raise RuntimeError("handler bug")

    bridge._dispatch = _boom  # type: ignore[method-assign]
    await _feed(bridge, _packet(_hello_bytes(), identity=CLIENT))
    assert bridge.receiver.dropped_bad == 1
    # 下一条仍然能进来：收侧状态机没有被那次失败污染。
    assert bridge.receiver.applied == 1


async def test_a_catalogued_event_without_a_handler_is_counted():
    """目录里有、代码里还没有消费者的 t，必须单独计数。

    没有这个桶，``control.barge_in`` 会被计进 ``received`` 然后什么都不做，
    两端日志都干净——「声明了但没实现」看起来跟「处理成功」一模一样。
    """
    bridge = _bridge()
    payload = new_envelope(
        "control.barge_in",
        args={"speech_id": "s-1", "played_ms": 120, "reason": "vad"},
        seq=0,
        ep="e",
        ident="b-1",
    )
    await _feed(bridge, _packet(encode(payload), identity=CLIENT, topic=TOPIC_CTL))

    assert bridge.receiver.applied == 1            # 信封层是干净的
    assert bridge.unhandled == {"control.barge_in": 1}
    assert bridge.receiver.dropped_bad == 0


async def test_hello_and_health_are_not_counted_as_unhandled():
    """有处理器的 t 不该落进 unhandled——否则这个桶就失去意义了。"""
    bridge = _bridge()
    await _feed(bridge, _packet(_hello_bytes(), identity=CLIENT))
    health = new_envelope(
        "telemetry.health", args={"degrade_level": "L0"}, seq=0, ep="e", ident="t-1"
    )
    await _feed(bridge, _packet(encode(health), identity=CLIENT, topic=TOPIC_TEL))

    assert bridge.unhandled == {}


# ---------------------------------------------------------------- seq

async def test_published_messages_carry_increasing_seq():
    sink = _Sink()
    bridge = _bridge(sink)
    await _feed(bridge, _packet(_hello_bytes(), identity=CLIENT))
    await bridge.publish("presentation.emotion", {"emotion": "开心"}, topic=TOPIC_CUE)
    await bridge.publish("presentation.emotion", {"emotion": "难过"}, topic=TOPIC_CUE)

    seqs = []
    for _, payload in sink.sent:
        envelope, status = decode(payload)
        assert envelope is not None, status
        seqs.append(envelope.seq)
    # cmp.ctl 与 cmp.cue 各走各的序号空间（§5.1 按 topic 计）。
    assert seqs == [0, 0, 1]


async def test_chinese_is_not_escaped_on_the_wire():
    sink = _Sink()
    bridge = _bridge(sink)
    await _feed(bridge, _packet(_hello_bytes(), identity=CLIENT))
    await bridge.publish("presentation.emotion", {"emotion": "开心"}, topic=TOPIC_CUE)
    assert "开心" in sink.sent[-1][1].decode("utf-8")


# ---------------------------------------------------------------- attach

async def test_attach_wires_the_room_event():
    sink = _Sink()
    bridge = _bridge(sink)
    handlers: dict[str, Any] = {}

    class _Room:
        def on(self, event, callback):
            handlers[event] = callback

    attach(_Room(), bridge)
    assert "data_received" in handlers
    assert protocol_bridge.attach is not None


# ---------------------------------------------------------------- 表现指令（P0.5 冒烟闭环）

async def test_cue_emotion_uses_name_not_emotion():
    """§11.1 的 args 键是 ``name``。写成 ``emotion`` 客户端会当成未知情绪映射成 neutral。"""
    sink = _Sink()
    bridge = _bridge(sink)
    await _feed(bridge, _packet(_hello_bytes(), identity=CLIENT))

    assert await bridge.cue_emotion("joy", 0.7) is True
    topic, payload = sink.sent[-1]
    envelope, status = decode(payload)
    assert envelope is not None, status
    assert topic == TOPIC_CUE
    assert envelope.t == "presentation.emotion"
    assert envelope.args == {"name": "joy", "intensity": 0.7}


async def test_cue_emotion_at_round_trips_on_envelope():
    """P3：``at`` 挂在信封上，端侧靠它锚 speech.seg。"""
    sink = _Sink()
    bridge = _bridge(sink)
    await _feed(bridge, _packet(_hello_bytes(), identity=CLIENT))
    at = {"speech": "sp_1", "seg": 0, "phase": "start"}

    assert await bridge.cue_emotion("joy", at=at) is True
    _, payload = sink.sent[-1]
    envelope, status = decode(payload)
    assert envelope is not None, status
    assert envelope.at == at


async def test_cue_emotion_without_intensity_omits_the_key():
    sink = _Sink()
    bridge = _bridge(sink)
    await _feed(bridge, _packet(_hello_bytes(), identity=CLIENT))

    await bridge.cue_emotion("calm")
    assert sink.last_args() == {"name": "calm"}


async def test_cue_emotion_is_not_sent_before_negotiation():
    """v1 与未握手连接只走 companion.avatar；多发一条只会让老客户端日志里多一条解不开的包。"""
    sink = _Sink()
    bridge = _bridge(sink)

    assert await bridge.cue_emotion("joy") is False
    assert sink.sent == []


async def test_cue_emotion_is_not_sent_when_capability_missing():
    sink = _Sink()
    bridge = _bridge(sink)
    await _feed(bridge, _packet(_hello_bytes(caps={"speech.v1": 1}), identity=CLIENT))

    assert await bridge.cue_emotion("joy") is False
    # 只有握手回来的那条 ack，没有 cue。
    assert sink.types() == ["control.hello_ack"]


# ---------------------------------------------------------------- telemetry.health

async def test_health_is_recorded_without_raising():
    sink = _Sink()
    bridge = _bridge(sink)
    await _feed(bridge, _packet(_hello_bytes(), identity=CLIENT))
    before_bad = bridge.receiver.dropped_bad

    health = encode(
        new_envelope(
            "telemetry.health",
            args={"applied": 12, "dropped_bad": 1, "gap_count": 2, "degrade_level": "L1"},
            seq=0,
            ep="ep-a",
            ident="t-1",
        )
    )
    await _feed(bridge, _packet(health, identity=CLIENT, topic=TOPIC_TEL))

    assert bridge.telemetry is not None
    assert bridge.telemetry["degrade_level"] == "L1"
    assert bridge.telemetry["applied"] == 12
    # 不是 bad：这是它本来就该发的东西。
    assert bridge.receiver.dropped_bad == before_bad


async def test_health_with_odd_args_does_not_break_the_next_message():
    """§14.1：一个字段缺失的健康包不得影响后续消息。"""
    sink = _Sink()
    bridge = _bridge(sink)
    await _feed(bridge, _packet(_hello_bytes(), identity=CLIENT))

    health = encode(new_envelope("telemetry.health", args={}, seq=0, ep="ep-a", ident="t-1"))
    await _feed(bridge, _packet(health, identity=CLIENT, topic=TOPIC_TEL))
    assert bridge.telemetry == {}

    # 之后的一条 cue 照常发得出去。
    assert await bridge.cue_emotion("joy") is True
