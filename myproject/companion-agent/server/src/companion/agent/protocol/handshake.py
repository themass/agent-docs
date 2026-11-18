"""握手与能力协商（§7 / §12.1）。

这一段决定「这条连接之后能收到什么」，所以它必须能脱离房间独立跑：P0b 接线时
出现问题，最可能的原因就是协商结果不对，而不是网络。

三条规则值得在这里重复：

* **交集取低版本**：``hello_ack.caps`` = 服务端 ∩ 客户端，每个能力取两边较小的
  版本号（§12.1）。服务端之后不得发交集外的 ``t``。
* **3 秒兼容窗口**：老客户端从不发 hello。``ParticipantConnected`` 后等 3 秒，
  收不到就按 ``compat:"v1"`` 走旧 ``companion.*`` topic（§7.3）。
* **重发不是错误**：重连后客户端会再发一次 hello，服务端在连接期内任意时刻都必须
  重新协商，而不是「已经握过手就不再理」。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from companion.agent.protocol.envelope import PROTOCOL_MAJOR

#: 收不到 hello 时的等待时长（§7.3）。老客户端不会发。
LEGACY_WAIT_SECONDS = 3.0

#: 我们认识的每一项能力及其自身版本号。0 表示「知道但未启用」。
#: 与客户端 `ProtocolCaps.kt` 里那张表必须一致，否则交集会少一项。
SERVER_CAPS: dict[str, int] = {
    "presentation.state": 1,
    "presentation.emotion": 1,
    "presentation.gesture": 1,
    "presentation.gaze": 1,
    "speech.timing": 1,
    # 分批声明（§9.3.1）：必须与 speech.timing 同时协商出，才能发 speech.extend。
    "speech.extend": 1,
    "perception.attention": 1,
}

#: 服务端自报的上限。客户端据此裁剪自己的发送节奏。
SERVER_LIMITS: dict[str, int] = {
    "max_payload_bytes": 12288,
    "max_cue_per_sec": 8,
    "clock_skew_ms": 0,
}


class NegotiationError(ValueError):
    """hello 载荷不合法。调用方应拒绝协商，而不是退回一个默认能力集。"""


@dataclass(frozen=True, slots=True)
class ClientInfo:
    app: str = ""
    version: str = ""
    sdk: str = ""


@dataclass(frozen=True, slots=True)
class HelloRequest:
    """客户端 hello 的解析结果。"""

    proto_min: int
    proto_max: int
    caps: dict[str, int]
    limits: dict[str, int] = field(default_factory=dict)
    client: ClientInfo = field(default_factory=ClientInfo)


@dataclass(frozen=True, slots=True)
class HelloAck:
    """要回给客户端的 hello_ack。"""

    sid: str
    caps: dict[str, int]
    limits: dict[str, int]
    compat: str

    def args(self) -> dict[str, Any]:
        """塞进信封 ``args`` 的形状（§7.1）。"""
        return {
            "sid": self.sid,
            "caps": dict(self.caps),
            "limits": dict(self.limits),
            "compat": self.compat,
        }


def _int_or(value: Any, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def parse_hello(args: dict[str, Any]) -> HelloRequest:
    """解析 ``control.hello`` 的 ``args``。

    缺字段走默认值，但类型错了直接拒绝：一个把 ``proto.min`` 写成字符串的客户端，
    我们无法判断它到底支持哪个版本，猜一个会导致之后发它收不了的消息。
    """
    if not isinstance(args, dict):
        raise NegotiationError("hello args must be an object")

    proto = args.get("proto")
    if not isinstance(proto, dict):
        raise NegotiationError("hello.proto missing")
    proto_min = proto.get("min")
    proto_max = proto.get("max")
    if not isinstance(proto_min, int) or isinstance(proto_min, bool):
        raise NegotiationError("hello.proto.min must be an integer")
    if not isinstance(proto_max, int) or isinstance(proto_max, bool):
        raise NegotiationError("hello.proto.max must be an integer")
    if proto_min > proto_max:
        raise NegotiationError("hello.proto.min > max")

    raw_caps = args.get("caps")
    if not isinstance(raw_caps, dict):
        raise NegotiationError("hello.caps missing")
    caps: dict[str, int] = {}
    for name, version in raw_caps.items():
        if not isinstance(name, str) or not name:
            raise NegotiationError("hello.caps key must be a non-empty string")
        if not isinstance(version, int) or isinstance(version, bool) or version < 0:
            raise NegotiationError(f"hello.caps[{name}] must be a non-negative integer")
        caps[name] = version

    raw_limits = args.get("limits")
    limits: dict[str, int] = {}
    if isinstance(raw_limits, dict):
        for name, value in raw_limits.items():
            if isinstance(name, str) and isinstance(value, int) and not isinstance(value, bool):
                limits[name] = value

    raw_client = args.get("client")
    client = ClientInfo()
    if isinstance(raw_client, dict):
        client = ClientInfo(
            app=str(raw_client.get("app") or ""),
            version=str(raw_client.get("version") or ""),
            sdk=str(raw_client.get("sdk") or ""),
        )

    return HelloRequest(proto_min=proto_min, proto_max=proto_max, caps=caps, limits=limits, client=client)


def negotiate(hello: HelloRequest, *, sid: str) -> HelloAck:
    """算交集（§12.1）。

    ``hello_ack.caps`` 每一项取两边较小的版本号；客户端报了但服务端不认识的直接
    丢弃（服务端发不了），服务端有但客户端没报的也丢弃（客户端收不了）。值为 0
    的项**保留**——0 的意思是「知道但未启用」，删掉它会让客户端以为服务端根本不
    支持这个能力，从而永久降级。
    """
    if not (hello.proto_min <= PROTOCOL_MAJOR <= hello.proto_max):
        raise NegotiationError(
            f"no common protocol version: client {hello.proto_min}..{hello.proto_max}, "
            f"server {PROTOCOL_MAJOR}"
        )

    caps: dict[str, int] = {}
    for name, server_version in SERVER_CAPS.items():
        client_version = hello.caps.get(name)
        if client_version is None:
            continue
        caps[name] = min(server_version, client_version)

    # 上限取两边更保守的那个：客户端说它最多吃 1 KiB，我们就不能发 1.2 KiB。
    limits = dict(SERVER_LIMITS)
    if "max_payload_bytes" in hello.limits:
        limits["max_payload_bytes"] = min(SERVER_LIMITS["max_payload_bytes"], hello.limits["max_payload_bytes"])
    if "max_cue_per_sec" in hello.limits:
        limits["max_cue_per_sec"] = min(SERVER_LIMITS["max_cue_per_sec"], hello.limits["max_cue_per_sec"])

    return HelloAck(sid=sid, caps=caps, limits=limits, compat="v2")


def legacy_ack(*, sid: str) -> HelloAck:
    """3 秒内没等到 hello：按 v1 兼容处理（§7.3）。

    ``caps`` 为空表示「这一条连接不发任何 cmp.*」，服务端只走旧的 companion.*
    topic。这条路径只保留两个发布周期，之后删除。
    """
    return HelloAck(sid=sid, caps={}, limits=dict(SERVER_LIMITS), compat="v1")


#: 某些 ``t`` 不以自己的名字协商，而是挂在一个能力名下。``caps`` 的键是能力名
#: （``speech.timing``），不是消息类型；按消息类型直接查会让 ``speech.*`` 永远发不出去。
CAP_FOR_EVENT: dict[str, str] = {
    "speech.begin": "speech.timing",
    "speech.segment": "speech.timing",
    "speech.end": "speech.timing",
    # 取消只对带时间线的 speech 有意义；没谈成 speech.timing 的端侧没有可取消的东西。
    "control.cancel": "speech.timing",
}


def supports(ack: HelloAck, event_type: str) -> bool:
    """服务端能不能往这条连接发某个 ``t``。

    值为 0 的能力视为未启用。未知类型也返回 False——这是防止「不小心发了一条
    客户端没协商过的消息」的最后一道闸。
    """
    if ack.compat != "v2":
        return False
    cap = CAP_FOR_EVENT.get(event_type, event_type)
    return ack.caps.get(cap, 0) > 0
