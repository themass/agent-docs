"""打断输入：``control.barge_in`` → ``session.interrupt`` + ``speech.cancel``。

锁四件事：args 校验、冷却、cancel 与 interrupt 都走到、以及 bridge 真的把包交到消费者手里。
"""

from __future__ import annotations

from typing import Any

import pytest

from companion.agent.protocol import TOPIC_CTL, encode, new_envelope
from companion.api.livekit.barge_in import BargeInRelay, barge_args_ok
from companion.api.livekit.protocol_bridge import ProtocolBridge

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
        self.interrupts = 0
        self.fail = False

    def interrupt(self, *, force: bool = False) -> None:
        if self.fail:
            raise RuntimeError("nothing to interrupt")
        self.interrupts += 1


class _Speech:
    def __init__(self) -> None:
        self.cancels: list[str] = []
        self.played: list[int | None] = []
        self.fail = False
        self.prefix = None

    async def cancel(self, reason: str = "user_barge_in", played_ms: int | None = None) -> None:
        if self.fail:
            raise RuntimeError("cancel boom")
        self.cancels.append(reason)
        self.played.append(played_ms)
        return self.prefix


class _Pipeline:
    def __init__(self) -> None:
        self.cancels = 0
        self.fail = False

    async def cancel(self) -> None:
        if self.fail:
            raise RuntimeError("pipeline cancel boom")
        self.cancels += 1


class _Control:
    def __init__(self) -> None:
        self.prefixes: list[tuple[str, int]] = []

    async def note_spoken_prefix(self, *, turn_id: str, chars: int) -> None:
        self.prefixes.append((turn_id, chars))


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
                "caps": {"speech.v1": 1},
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


def test_barge_args_ok_accepts_dict_even_without_fields():
    assert barge_args_ok({})
    assert barge_args_ok({"speech_id": "sp_1", "played_ms": 120, "reason": "vad"})
    assert not barge_args_ok(None)
    assert not barge_args_ok(["not", "a", "dict"])  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_relay_interrupts_and_cancels_once():
    session = _Session()
    speech = _Speech()
    relay = BargeInRelay(session, speech, cooldown_s=60.0)

    await relay({"speech_id": "sp_1", "played_ms": 80, "reason": "vad"})
    await relay({"speech_id": "sp_1", "played_ms": 90, "reason": "vad"})  # 冷却内

    assert session.interrupts == 1
    assert speech.cancels == ["user_barge_in"]
    assert relay.accepted == 1
    assert relay.ignored == 1


@pytest.mark.asyncio
async def test_relay_still_cancels_when_interrupt_raises():
    session = _Session()
    session.fail = True
    speech = _Speech()
    relay = BargeInRelay(session, speech, cooldown_s=0.0)

    await relay({"reason": "vad"})

    assert session.interrupts == 0
    assert speech.cancels == ["user_barge_in"]
    assert relay.accepted == 1


@pytest.mark.asyncio
async def test_relay_survives_when_both_paths_fail():
    session = _Session()
    session.fail = True
    speech = _Speech()
    speech.fail = True
    relay = BargeInRelay(session, speech, cooldown_s=0.0)

    await relay({})

    assert relay.accepted == 0
    assert relay.ignored == 1


@pytest.mark.asyncio
async def test_relay_works_without_speech_publisher():
    session = _Session()
    relay = BargeInRelay(session, speech=None, cooldown_s=0.0)

    await relay({"reason": "vad"})

    assert session.interrupts == 1
    assert relay.accepted == 1


@pytest.mark.asyncio
async def test_relay_stops_generation_and_records_prefix():
    """契约 v2 §2.2：barge 必须停生成（pipeline.cancel），并把 played_ms 换的前缀写进回合。"""
    from companion.api.livekit.speech_publisher import SpokenPrefix

    session = _Session()
    speech = _Speech()
    speech.prefix = SpokenPrefix(speech_id="sp_1", turn_id="T7", text="听到了。", chars=4)
    pipeline = _Pipeline()
    control = _Control()
    relay = BargeInRelay(session, speech, pipeline=pipeline, control=control, cooldown_s=0.0)

    await relay({"speech_id": "sp_1", "played_ms": 730, "reason": "vad"})

    assert speech.played == [730]
    assert pipeline.cancels == 1
    assert control.prefixes == [("T7", 4)]


@pytest.mark.asyncio
async def test_relay_without_played_ms_sends_none_and_no_prefix_note():
    session = _Session()
    speech = _Speech()
    pipeline = _Pipeline()
    control = _Control()
    relay = BargeInRelay(session, speech, pipeline=pipeline, control=control, cooldown_s=0.0)

    await relay({"speech_id": "sp_1", "reason": "vad"})

    assert speech.played == [None]
    assert control.prefixes == []
    assert pipeline.cancels == 1


@pytest.mark.asyncio
async def test_relay_cancels_pipeline_even_when_speech_cancel_fails():
    session = _Session()
    speech = _Speech()
    speech.fail = True
    pipeline = _Pipeline()
    relay = BargeInRelay(session, speech, pipeline=pipeline, cooldown_s=0.0)

    await relay({"played_ms": 100})

    assert pipeline.cancels == 1
    assert relay.accepted == 1  # interrupt 成功了


@pytest.mark.asyncio
async def test_relay_survives_pipeline_cancel_failure():
    session = _Session()
    speech = _Speech()
    pipeline = _Pipeline()
    pipeline.fail = True
    relay = BargeInRelay(session, speech, pipeline=pipeline, cooldown_s=0.0)

    await relay({"played_ms": 100})

    assert speech.cancels == ["user_barge_in"]
    assert relay.accepted == 1


@pytest.mark.asyncio
async def test_bridge_delivers_barge_in_to_on_barge():
    sink = _Sink()
    bridge = _bridge(sink)
    await _feed(bridge, _hello_bytes(), topic=TOPIC_CTL)
    session = _Session()
    speech = _Speech()
    bridge.on_barge = BargeInRelay(session, speech, cooldown_s=0.0)

    # hello 已经用了 cmp.ctl 上的 seq=0；再发 seq=0 会被 Receiver 当成 stale。
    payload = encode(
        new_envelope(
            "control.barge_in",
            args={"speech_id": "sp_9", "played_ms": 200, "reason": "vad"},
            seq=1,
            ep="ep-a",
            ident="b-1",
        )
    )
    await _feed(bridge, payload, topic=TOPIC_CTL)

    assert session.interrupts == 1
    assert speech.cancels == ["user_barge_in"]
    assert bridge.unhandled == {}


@pytest.mark.asyncio
async def test_barge_in_without_handler_still_counts_unhandled():
    """没挂 on_barge 时，目录事件必须进 unhandled——这是 §14.3 的探针。"""
    bridge = _bridge()
    payload = encode(
        new_envelope(
            "control.barge_in",
            args={"speech_id": "s-1", "played_ms": 120, "reason": "vad"},
            seq=0,
            ep="e",
            ident="b-1",
        )
    )
    await _feed(bridge, payload, topic=TOPIC_CTL)
    assert bridge.unhandled == {"control.barge_in": 1}
