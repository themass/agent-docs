"""触摸输入：``control.input`` → 用户句 → ``generate_reply``。

锁三件事：字段校验、冷却、以及 bridge 真的把包交到消费者手里。
"""

from __future__ import annotations

from typing import Any

import pytest

from companion.agent.protocol import TOPIC_CTL, TOPIC_IN, encode, new_envelope
from companion.api.livekit.protocol_bridge import ProtocolBridge
from companion.api.livekit.touch_input import TouchInputRelay, touch_user_message

CLIENT = "user-1002"
AGENT = "agent-linche"


class _Sink:
    def __init__(self) -> None:
        self.sent: list[tuple[str, bytes]] = []

    async def __call__(self, topic: str, payload: bytes) -> None:
        self.sent.append((topic, payload))


class _Publisher:
    def __init__(self, identity: str, kind: Any) -> None:
        self.identity = identity
        self.kind = kind


class _Session:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail = False

    def generate_reply(self, *, user_input: str) -> None:
        if self.fail:
            raise RuntimeError("boom")
        self.calls.append(user_input)


def _bridge(sink: _Sink | None = None) -> ProtocolBridge:
    return ProtocolBridge(
        send=sink or _Sink(),
        identity=AGENT,
        local_identity=AGENT,
        sid="s-test",
        legacy_timeout=0.05,
    )


def _hello_bytes() -> bytes:
    return encode(
        new_envelope(
            "control.hello",
            args={
                "proto": {"min": 2, "max": 2},
                "caps": {"presentation.emotion": 1},
                "limits": {"max_payload_bytes": 4096},
                "client": {"app": "companion", "version": "1.0", "sdk": "2.29.0"},
            },
            seq=0,
            ep="ep-a",
            ident="h-1",
        )
    )


async def _feed(bridge: ProtocolBridge, data: bytes, *, topic: str, identity: str = CLIENT,
                kind: Any = "STANDARD"):
    publisher = _Publisher(identity, kind)
    return await bridge.on_data(
        data,
        topic=topic,
        publisher_identity=publisher.identity,
        publisher_kind=publisher.kind,
    )


def test_touch_user_message_maps_known_regions():
    assert touch_user_message({"kind": "touch", "region": "head"}) == "摸了摸她的头"
    assert touch_user_message({"kind": "touch", "region": "hand_r"}) == "碰了碰她的右手"
    assert touch_user_message({"kind": "touch", "region": "unknown_zone"}) == "碰了她一下"


@pytest.mark.parametrize(
    "args",
    [
        None,
        {},
        {"kind": "swipe", "region": "head"},
        {"kind": "touch"},
        {"kind": "touch", "region": ""},
        {"kind": "touch", "region": 3},
        {"kind": "touch", "region": "   "},
    ],
)
def test_touch_user_message_rejects_bad_args(args: Any):
    assert touch_user_message(args) is None


def test_relay_forwards_first_touch_and_cools_down():
    session = _Session()
    relay = TouchInputRelay(session, cooldown_s=60.0)
    relay({"kind": "touch", "region": "head"})
    relay({"kind": "touch", "region": "body"})  # 冷却内
    assert session.calls == ["摸了摸她的头"]
    assert relay.accepted == 1
    assert relay.ignored == 1


def test_relay_ignores_non_touch_without_calling_session():
    session = _Session()
    relay = TouchInputRelay(session, cooldown_s=0.0)
    relay({"kind": "swipe", "region": "head"})
    assert session.calls == []
    assert relay.ignored == 1
    assert relay.accepted == 0


def test_relay_survives_generate_reply_failure():
    session = _Session()
    session.fail = True
    relay = TouchInputRelay(session, cooldown_s=0.0)
    relay({"kind": "touch", "region": "head"})
    assert relay.accepted == 0
    assert relay.ignored == 1


@pytest.mark.asyncio
async def test_bridge_delivers_control_input_to_on_input():
    sink = _Sink()
    bridge = _bridge(sink)
    await _feed(bridge, _hello_bytes(), topic=TOPIC_CTL)
    session = _Session()
    bridge.on_input = TouchInputRelay(session, cooldown_s=0.0)

    payload = encode(
        new_envelope(
            "control.input",
            args={"kind": "touch", "region": "head"},
            seq=0,
            ep="ep-a",
            ident="in-1",
        )
    )
    await _feed(bridge, payload, topic=TOPIC_IN)

    assert session.calls == ["摸了摸她的头"]
    assert bridge.unhandled == {}
