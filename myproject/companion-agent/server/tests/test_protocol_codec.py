"""协议 v2 信封编解码。

向量从 ``tests/fixtures/protocol_v2.json`` 读，客户端（Kotlin）读的是同一份内容的
拷贝。两端跑同一份向量，是唯一能挡住「各写各理解」的手段。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from companion.agent.protocol.catalog import (
    TOPIC_CUE,
    TOPIC_CTL,
    TOPIC_IN,
    TOPIC_TEL,
    Delivery,
    Side,
    allowed,
    may_send,
    spec_of,
)
from companion.agent.protocol.envelope import (
    MAX_PAYLOAD_BYTES,
    PROTOCOL_MAJOR,
    DecodeStatus,
    Envelope,
    Receiver,
    Verdict,
    decode,
    encode,
    new_envelope,
)

FIXTURE = Path(__file__).parent / "fixtures" / "protocol_v2.json"
VECTORS = json.loads(FIXTURE.read_text(encoding="utf-8"))

#: 客户端那份拷贝的 sha256 必须与这个值一致。两边对不上就说明契约被单边改过。
#: 换 fixture 时同时更新客户端 `ProtocolCodecTest.TEST_VECTOR_SHA256`。
TEST_VECTOR_SHA256 = "b5b8e7d3d2d300391e3262b7f695ea8b04ddc7b0297a272058c6177fb32e2662"


def _payload(case: dict) -> bytes:
    """把一条向量变成一个真的字节串。

    ``pad_to_bytes`` 是给体积上限用的：在 ``args`` 里塞一段填充，让整包正好落到
    指定字节数。pad 用 ASCII 空格，长度算得准。
    """
    if "raw" in case:
        return case["raw"].encode("utf-8")
    obj = case["json"]
    target = case.get("pad_to_bytes")
    if target is None:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # 先算出不加填充的体积，再把差额塞进 args.pad。
    probe = json.loads(json.dumps(obj))
    probe["args"] = {**probe["args"], "pad": ""}
    base = len(json.dumps(probe, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    probe["args"]["pad"] = "x" * (target - base)
    data = json.dumps(probe, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert len(data) == target, f"padding arithmetic is off: {len(data)} != {target}"
    return data


def test_fixture_and_client_copy_agree():
    """fixture 的内容指纹。

    客户端那份文件是逐字节拷贝，所以这里算的是「这份 fixture 本身」的 hash。
    它的作用不是防止手滑，而是让两端在 CI 里各自断言同一个常量：谁改了契约却只改
    一边，另一边的测试立刻红。
    """
    digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    if TEST_VECTOR_SHA256 == "__REPLACE_ME__":
        pytest.skip("fixture hash not pinned yet; run `sha256sum` and fill TEST_VECTOR_SHA256")
    assert digest == TEST_VECTOR_SHA256


@pytest.mark.parametrize("case", VECTORS["decode"], ids=[c["name"] for c in VECTORS["decode"]])
def test_decode_vectors(case):
    envelope, status = decode(_payload(case))
    assert status == case["outcome"], f"{case['name']}: got {status}"
    if case["outcome"] == DecodeStatus.OK:
        assert envelope is not None
        assert envelope.t == case["json"]["t"]
        assert envelope.id == case["json"]["id"]
        assert envelope.seq == case["json"]["seq"]
        assert envelope.ep == case["json"]["ep"]


def test_decode_is_total_never_raises():
    """任何字节串都不能让解码抛异常（§14.1：一条消息失败不得影响后续）。"""
    nasty = [
        b"", b"\x00", b"\xff\xfe", b"\x00" * 5000, b"{", b"}", b"[]", b"null",
        b'{"v":2}', b'{"v":2,"t":"x"}', b'{"v":2,"t":"x","id":"i","seq":0,"ep":"e","args":{}}',
        "表情".encode(), b'{"v":2,"t":"presentation.emotion","id":"i","seq":0,"ep":"e","args":{"emotion":"joy"}}',
        b'{"v":2,"t":"presentation.emotion","id":"i","seq":0,"ep":"e","args":{"emotion":"joy"}}\x00',
    ]
    for data in nasty:
        envelope, status = decode(data)
        assert isinstance(status, DecodeStatus)
        if status is not DecodeStatus.OK:
            assert envelope is None


def test_too_large_is_checked_before_parsing():
    """70 KB 的包应该在解析前就被挡掉——否则 JSON 解析器先跑了一遍。"""
    # 一个 70 KB 的合法 JSON：如果先解析，会成功；正确实现应该直接 too_large。
    big = b'{"v":2,"t":"presentation.emotion","id":"i","seq":0,"ep":"e","args":{"x":"' + b"a" * 71680 + b'"}}'
    assert len(big) > 65535
    _, status = decode(big)
    assert status is DecodeStatus.TOO_LARGE


def test_max_payload_boundary():
    """4096 收下，4097 拒收（§4.3）。"""
    cases = {c["name"]: c for c in VECTORS["decode"]}
    ok = next(c for c in cases.values() if c.get("pad_to_bytes") == MAX_PAYLOAD_BYTES)
    assert decode(_payload(ok))[1] is DecodeStatus.OK
    over = next(c for c in cases.values() if c.get("pad_to_bytes") == MAX_PAYLOAD_BYTES + 1)
    assert decode(_payload(over))[1] is DecodeStatus.TOO_LARGE


def test_encode_round_trips_chinese_without_escaping():
    """``ensure_ascii=False``：中文按 UTF-8 走，不是 ``\\uXXXX``。"""
    envelope = new_envelope(
        "presentation.emotion", args={"emotion": "开心"}, seq=3, ep="e", ident="i",
    )
    data = encode(envelope)
    assert "开心".encode() in data
    assert b"\\u" not in data
    back, status = decode(data)
    assert status is DecodeStatus.OK
    assert back is not None and back.args["emotion"] == "开心"


def test_encode_omits_none_optional_fields():
    envelope = new_envelope("presentation.emotion", args={}, seq=0, ep="e", ident="i")
    payload = json.loads(encode(envelope))
    assert "ts" not in payload and "at" not in payload and "dst" not in payload


def test_encode_refuses_oversized_payload():
    """发送侧断言失败（§14.1），而不是悄悄截断。"""
    envelope = new_envelope("presentation.emotion", args={"x": "a" * 5000}, seq=0, ep="e", ident="i")
    with pytest.raises(ValueError, match="exceeds"):
        encode(envelope)


def test_dst_matching():
    broadcast = new_envelope("presentation.emotion", args={}, seq=0, ep="e", ident="i")
    assert broadcast.is_for("anyone")
    targeted = new_envelope("presentation.emotion", args={}, seq=0, ep="e", ident="i", dst=["u-1"])
    assert targeted.is_for("u-1")
    assert not targeted.is_for("u-2")
    empty = new_envelope("presentation.emotion", args={}, seq=0, ep="e", ident="i", dst=[])
    assert empty.is_for("anyone")


# ---------------------------------------------------------------- 方向白名单


@pytest.mark.parametrize("case", VECTORS["direction"], ids=[c["name"] for c in VECTORS["direction"]])
def test_direction_vectors(case):
    side = Side.SERVER if case["role"] == "server" else Side.CLIENT
    got = "ok" if allowed(case["topic"], case["t"], receiving=side) else "wrong_direction"
    assert got == case["outcome"], case["name"]


def test_catalog_covers_every_spec_topic():
    """目录里每条事件的 topic 都得是四个之一，避免拼错字符串。"""
    for name in ("presentation.state", "presentation.emotion", "presentation.gesture",
                 "presentation.gaze", "speech.begin", "speech.segment", "speech.end",
                 "control.hello", "control.hello_ack", "control.ping", "control.pong",
                 "control.cancel", "control.request", "control.response", "control.barge_in",
                 "control.input", "perception.attention", "telemetry.health"):
        spec = spec_of(name)
        assert spec is not None, name
        assert spec.topic in {TOPIC_CUE, TOPIC_CTL, TOPIC_IN, TOPIC_TEL}


def test_speech_events_are_on_the_ordered_cue_topic():
    """保序需求集中在 cmp.cue 一条流上（§4.1），speech.* 不能散到别的 topic。"""
    for name in ("speech.begin", "speech.segment", "speech.end"):
        assert spec_of(name).topic == TOPIC_CUE


def test_delivery_classes_match_the_catalog():
    assert spec_of("presentation.emotion").delivery is Delivery.DEADLINE
    assert spec_of("speech.begin").delivery is Delivery.MUST
    assert spec_of("telemetry.health").delivery is Delivery.DROPPABLE
    assert spec_of("control.hello").delivery is Delivery.MUST


def test_may_send_mirrors_allowed():
    assert may_send(TOPIC_CTL, "control.hello", sending=Side.CLIENT)
    assert not may_send(TOPIC_CTL, "control.hello", sending=Side.SERVER)
    assert not may_send(TOPIC_CUE, "speech.begin", sending=Side.CLIENT)


# ---------------------------------------------------------------- 收侧状态机


@pytest.mark.parametrize("case", VECTORS["receiver"], ids=[c["name"] for c in VECTORS["receiver"]])
def test_receiver_vectors(case):
    receiver = Receiver(case.get("me"))
    results: list[str] = []
    for op in case["ops"]:
        if op.get("op") == "forget":
            receiver.forget_publisher(op["publisher"])
            continue
        envelope = new_envelope(
            "presentation.emotion", args={}, seq=op["seq"], ep=op["ep"], ident=op["id"],
            dst=op.get("dst"),
        )
        results.append(receiver.observe(envelope, publisher=op["publisher"], topic=op["topic"]).value)

    assert results == case["expect"], case["name"]
    assert receiver.state.gaps == case.get("gaps", 0), f"{case['name']}: gaps"


def test_dedup_is_bounded():
    """LRU 256：第 257 条会把最老的挤出去（§5 规则 4）。"""
    receiver = Receiver()
    for i in range(300):
        receiver.observe(
            new_envelope("presentation.emotion", args={}, seq=i, ep="e", ident=f"m{i}"),
            publisher="agent", topic=TOPIC_CUE,
        )
    assert len(receiver.state._seen["agent"]) == 256
    # 最老的已经不在表里了，但它也不会被当成重复而误杀——只是重复检测窗口外。
    assert "m0" not in receiver.state._seen["agent"]


def test_reconnect_clears_everything():
    """`RoomEvent.Reconnected` 上的清表（§5.1）。"""
    receiver = Receiver()
    for i in range(3):
        receiver.observe(
            new_envelope("presentation.emotion", args={}, seq=i, ep="e1", ident=f"m{i}"),
            publisher="agent", topic=TOPIC_CUE,
        )
    receiver.forget_all()
    assert receiver.state._last_seq == {}
    assert receiver.state._seen == {}
    # 清完之后同 id 重发会被当成新的（这是对的：重连后不知道对端看到了什么）。
    verdict = receiver.observe(
        new_envelope("presentation.emotion", args={}, seq=0, ep="e1", ident="m0"),
        publisher="agent", topic=TOPIC_CUE,
    )
    assert verdict is Verdict.ACCEPT


def test_receiver_never_raises_on_unknown_arguments():
    """收侧状态机不看 args，任何 args 都不该让它抛。"""
    receiver = Receiver()
    for args in ({}, {"weird": [1, 2, {"a": None}]}, {"x": 1e308}):
        envelope = new_envelope("presentation.emotion", args=args, seq=0, ep="e", ident="i")
        receiver.forget_all()
        assert receiver.observe(envelope, publisher="a", topic=TOPIC_CUE) is Verdict.ACCEPT


def test_protocol_major_is_two():
    assert PROTOCOL_MAJOR == 2
