"""握手与能力协商（§7 / §12.1）。

这一层最容易出的错不是异常，而是**静默地少协商一项**：客户端之后再也收不到
``presentation.emotion``，而两边日志都干净。所以这里逐条断言交集表的内容。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from companion.agent.protocol.envelope import PROTOCOL_MAJOR
from companion.agent.protocol.handshake import (
    LEGACY_WAIT_SECONDS,
    SERVER_CAPS,
    SERVER_LIMITS,
    HelloAck,
    NegotiationError,
    legacy_ack,
    negotiate,
    parse_hello,
    supports,
)

FIXTURE = Path(__file__).parent / "fixtures" / "protocol_v2.json"


def _hello_args() -> dict:
    """向量里那条客户端 hello 的 args。两端用的是同一段 JSON。"""
    vectors = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for case in vectors["decode"]:
        if case["json"]["t"] == "control.hello":
            return case["json"]["args"]
    raise AssertionError("fixture 里没有 control.hello 的向量")


# ---------------------------------------------------------------- 解析


def test_parse_the_fixture_hello():
    hello = parse_hello(_hello_args())
    assert hello.proto_min == 2
    assert hello.proto_max == 2
    assert hello.caps
    assert hello.client.app


def test_parse_rejects_missing_proto():
    with pytest.raises(NegotiationError, match="proto"):
        parse_hello({"caps": {}})


def test_parse_rejects_non_integer_proto():
    """``proto.min`` 写成字符串时无法判断它支持哪个版本，猜一个会发它收不了的消息。"""
    with pytest.raises(NegotiationError):
        parse_hello({"proto": {"min": "2", "max": 2}, "caps": {}})


def test_parse_rejects_bool_as_version():
    """``True`` 是 ``int`` 子类，不能当成版本 1。"""
    with pytest.raises(NegotiationError):
        parse_hello({"proto": {"min": True, "max": 2}, "caps": {}})


def test_parse_rejects_inverted_range():
    with pytest.raises(NegotiationError, match="min"):
        parse_hello({"proto": {"min": 3, "max": 2}, "caps": {}})


def test_parse_rejects_missing_caps():
    with pytest.raises(NegotiationError, match="caps"):
        parse_hello({"proto": {"min": 2, "max": 2}})


def test_parse_rejects_negative_cap_version():
    with pytest.raises(NegotiationError, match="non-negative"):
        parse_hello({"proto": {"min": 2, "max": 2}, "caps": {"presentation.gaze": -1}})


def test_parse_accepts_cap_version_zero():
    """0 是「知道但未启用」，是合法值（§12.1）。"""
    hello = parse_hello({"proto": {"min": 2, "max": 2}, "caps": {"presentation.gaze": 0}})
    assert hello.caps["presentation.gaze"] == 0


def test_parse_tolerates_unknown_or_malformed_limits():
    """limits 是提示性的：多一个不认识的键、或者类型不对，都不该让握手失败。

    解析阶段保留所有 str -> int 的项（未来新增的键不必改解析器）；真正生效的只有
    [negotiate] 读的那几个，未知键在那里自然被忽略。类型不对的直接丢掉。
    """
    hello = parse_hello({
        "proto": {"min": 2, "max": 2},
        "caps": {},
        "limits": {"max_payload_bytes": 1024, "weird_future_limit": 7, "bad": "x"},
    })
    assert hello.limits["max_payload_bytes"] == 1024
    assert hello.limits.get("weird_future_limit") == 7
    assert "bad" not in hello.limits


def test_parse_tolerates_missing_client_info():
    hello = parse_hello({"proto": {"min": 2, "max": 2}, "caps": {}})
    assert hello.client.app == "" and hello.client.version == "" and hello.client.sdk == ""


# ---------------------------------------------------------------- 协商


def test_negotiate_takes_the_lower_version_per_capability():
    hello = parse_hello({
        "proto": {"min": 2, "max": 2},
        "caps": {"presentation.emotion": 3, "presentation.gaze": 1},
    })
    ack = negotiate(hello, sid="s-1")
    # emotion 取 min(1, 3) = 1；gaze 两边都是 1，取 1。
    assert ack.caps == {"presentation.emotion": 1, "presentation.gaze": 1}
    assert supports(ack, "presentation.emotion")
    assert supports(ack, "presentation.gaze")


def test_negotiate_keeps_zero_versions():
    """丢掉 0 会让客户端以为服务端根本不支持这个能力，从而永久降级。"""
    hello = parse_hello({"proto": {"min": 2, "max": 2}, "caps": {"speech.v1": 0}})
    ack = negotiate(hello, sid="s-1")
    assert ack.caps == {"speech.v1": 0}
    # 但值为 0 的能力不可发送。
    assert not supports(ack, "speech.seg")


def test_negotiate_drops_caps_the_client_never_mentioned():
    hello = parse_hello({"proto": {"min": 2, "max": 2}, "caps": {"presentation.state": 1}})
    ack = negotiate(hello, sid="s-1")
    # 服务端对 state 标的是 0：交集会保留 0，但不能发。
    assert ack.caps == {"presentation.state": 0}
    assert "presentation.emotion" not in ack.caps
    assert not supports(ack, "presentation.state")


def test_negotiate_drops_caps_the_server_does_not_know():
    hello = parse_hello({"proto": {"min": 2, "max": 2}, "caps": {"future.teleport": 1}})
    ack = negotiate(hello, sid="s-1")
    assert ack.caps == {}


def test_negotiate_full_intersection_matches_server_table():
    hello = parse_hello({"proto": {"min": 2, "max": 2}, "caps": dict(SERVER_CAPS)})
    ack = negotiate(hello, sid="s-1")
    assert ack.caps == SERVER_CAPS


def test_negotiate_rejects_incompatible_protocol_range():
    """``v`` 只增不减；区间不重叠就没有共同版本，必须拒绝而不是降级猜测。"""
    hello = parse_hello({"proto": {"min": 3, "max": 9}, "caps": {}})
    with pytest.raises(NegotiationError, match="no common protocol version"):
        negotiate(hello, sid="s-1")


def test_negotiate_accepts_a_range_that_spans_the_server_version():
    hello = parse_hello({"proto": {"min": 1, "max": 5}, "caps": {}})
    ack = negotiate(hello, sid="s-1")
    assert ack.compat == "v2"
    assert PROTOCOL_MAJOR == 2


def test_negotiate_picks_the_more_conservative_limit():
    hello = parse_hello({
        "proto": {"min": 2, "max": 2},
        "caps": {},
        "limits": {"max_payload_bytes": 1024, "max_cue_per_sec": 99},
    })
    ack = negotiate(hello, sid="s-1")
    # 客户端最多吃 1 KiB；它报的 99/s 超过我们的 8/s，取 8。
    assert ack.limits["max_payload_bytes"] == 1024
    assert ack.limits["max_cue_per_sec"] == 8


def test_negotiate_leaves_limits_alone_when_client_omits_them():
    hello = parse_hello({"proto": {"min": 2, "max": 2}, "caps": {}})
    ack = negotiate(hello, sid="s-1")
    assert ack.limits == SERVER_LIMITS


def test_hello_ack_args_shape():
    """``args()`` 的形状就是 §7.1 的载荷，键名不能漂。"""
    ack = HelloAck(sid="s-1", caps={"presentation.emotion": 1}, limits=dict(SERVER_LIMITS), compat="v2")
    args = ack.args()
    assert set(args) == {"sid", "caps", "limits", "compat"}
    assert args["sid"] == "s-1"
    assert args["compat"] == "v2"
    # 必须是拷贝：改了返回的 dict 不能污染 ack 自己。
    args["caps"]["presentation.emotion"] = 9
    assert ack.caps["presentation.emotion"] == 1


# ---------------------------------------------------------------- v1 兼容


def test_legacy_ack_has_no_capabilities():
    ack = legacy_ack(sid="s-1")
    assert ack.caps == {}
    assert ack.compat == "v1"
    assert not supports(ack, "presentation.emotion")


def test_legacy_wait_is_three_seconds():
    """§7.3 的值是协议的一部分：老客户端在 3 秒后才被当成 v1。"""
    assert LEGACY_WAIT_SECONDS == 3.0


def test_v1_connection_can_send_nothing_from_the_v2_catalog():
    ack = legacy_ack(sid="s-1")
    for event_type in SERVER_CAPS:
        assert not supports(ack, event_type), event_type


def test_supports_is_false_for_anything_not_negotiated():
    """哪怕对端「应该有」这个能力，只要这次握手没协商出来就不能发。

    ``SERVER_CAPS`` 里保留了未启用的名字（值为 0），所以整表协商后那些项仍在
    ``ack.caps`` 里，但 ``supports`` 必须是 False；没进交集的类型一律 False。
    """
    ack = negotiate(parse_hello({"proto": {"min": 2, "max": 2}, "caps": dict(SERVER_CAPS)}), sid="s-1")
    assert not supports(ack, "presentation.teleport")
    assert not supports(ack, "telemetry.health")  # 在目录里，但服务端不协商它
    assert not supports(ack, "presentation.state")
    assert supports(ack, "presentation.gesture")
    assert supports(ack, "presentation.gaze")
    assert not supports(ack, "perception.attention")

    partial = negotiate(parse_hello({"proto": {"min": 2, "max": 2}, "caps": {"presentation.state": 1}}), sid="s-1")
    assert partial.caps == {"presentation.state": 0}
    assert not supports(partial, "presentation.state")
    assert not supports(partial, "presentation.emotion")


def test_handshake_is_repeatable_within_a_connection():
    """重连后客户端会再发一次 hello；同一个 sid 再协商一次结果应完全相同（幂等）。"""
    hello = parse_hello({"proto": {"min": 2, "max": 2}, "caps": dict(SERVER_CAPS)})
    first = negotiate(hello, sid="s-1")
    second = negotiate(hello, sid="s-1")
    assert first == second


# ---------------------------------------------------------------- 能力兑现


def test_server_caps_only_enable_what_we_can_ship():
    """SERVER_CAPS 的 1 必须对应实际发送/消费路径，否则协商会虚报。

    现在能兑现的：
    * ``presentation.emotion`` / ``presentation.gesture`` / ``presentation.gaze``
      —— ``AnchoredCuePublisher`` + 端侧 B 类路径
    * ``speech.v1`` —— ``speech_seg`` / ``speech_end`` / ``cancel_speech``

    目录里仍保留 state / attention 的名字，所以表里也要有它们，但版本必须是 0：
    客户端会看到「知道但未启用」，而不是「会收到」。
    """
    assert SERVER_CAPS["presentation.emotion"] == 1
    assert SERVER_CAPS["presentation.gesture"] == 1
    assert SERVER_CAPS["presentation.gaze"] == 1
    assert SERVER_CAPS["speech.v1"] == 1
    for name in (
        "presentation.state",
        "perception.attention",
    ):
        assert name in SERVER_CAPS, name
        assert SERVER_CAPS[name] == 0, name

    ack = negotiate(parse_hello({"proto": {"min": 2, "max": 2}, "caps": {
        # 客户端把未实现项报成 1 也没关系——交集取低版本后仍是 0。
        "presentation.state": 1,
        "presentation.emotion": 1,
        "presentation.gesture": 1,
        "presentation.gaze": 1,
        "speech.v1": 1,
        "perception.attention": 1,
    }}), sid="s-1")
    assert supports(ack, "presentation.emotion")
    assert supports(ack, "presentation.gesture")
    assert supports(ack, "presentation.gaze")
    assert supports(ack, "speech.seg")
    assert supports(ack, "speech.end")
    assert supports(ack, "control.cancel")
    for name in (
        "presentation.state",
        "perception.attention",
    ):
        assert ack.caps[name] == 0, name
        assert not supports(ack, name), name
