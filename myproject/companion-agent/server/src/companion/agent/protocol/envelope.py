"""协议 v2 信封的编解码（§5）。

纯字符串进出，不依赖 LiveKit、不依赖事件循环，所以可以在真正接线之前就把
「两端是不是同一个理解」用单测锁住。接线是 P0b 的事；这里只负责：

* 校验（必填字段、类型、版本、体积上限）
* 序列化（``ensure_ascii=False``，中文不转义）
* 去重 / 序号 / gap 的状态机（``Receiver``）

**为什么把解析失败分类而不是抛一个异常**：§14.1 要求每一种失败都进不同的计数桶，
运维靠这些桶区分「是网络还是我的编译器」。抛一个 ``ValueError`` 上层就只能知道
「坏了」，说不出坏在哪。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

PROTOCOL_MAJOR = 2

#: 单条消息的硬限。SDK 强限 65535 B（§4.3），但 4 KiB 以上一律视为实现缺陷，
#: 由编解码层直接拒收并计数，而不是让它走到网络层。
MAX_PAYLOAD_BYTES = 4096

#: 自限口径（§4.3），比硬限小得多。发送侧断言用，接收侧不看这个值。
SOFT_PAYLOAD_BYTES = 12288


class DecodeStatus(StrEnum):
    """一条消息的解析结果。前四种是失败，分别对应 §14.1 的一个计数桶。"""

    OK = "ok"
    BAD_JSON = "bad_json"
    MISSING_FIELD = "missing_field"
    BAD_VALUE = "bad_value"
    VERSION = "version"
    TOO_LARGE = "too_large"
    UNKNOWN_TYPE = "unknown_type"


#: 解析成功但不是 `ok` 的那一种：`t` 不认识。它**不算失败**——消息本身是好的，
#: 只是这一端还没有这个能力，忽略即可（§5 规则 2）。
_UNKNOWN = DecodeStatus.UNKNOWN_TYPE

_REQUIRED = ("v", "t", "id", "seq", "ep", "args")


@dataclass(frozen=True, slots=True)
class Envelope:
    """解开之后的一封信。``args`` 不做任何类型加工，交给各事件的处理器自己读。

    ``raw_bytes`` 留着是为了埋点：``payload_bytes_hist`` 要的是原始体积，不是
    重新序列化之后的体积。
    """

    v: int
    t: str
    id: str
    seq: int
    ep: str
    args: dict[str, Any]
    ts: int | None = None
    at: dict[str, Any] | None = None
    dst: tuple[str, ...] | None = None
    raw_bytes: int = 0

    def is_for(self, identity: str) -> bool:
        """``dst`` 为空/缺省即广播；非空时只有列出的 identity 该处理（§5 规则 6）。"""
        return self.dst is None or not self.dst or identity in self.dst


def _is_int(value: Any) -> bool:
    # bool 是 int 的子类，`{"v": true}` 不该被当成版本 1。
    return isinstance(value, int) and not isinstance(value, bool)


def _encode_compact(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def decode(data: bytes | str) -> tuple[Envelope | None, DecodeStatus]:
    """解一封信。

    返回 ``(信封, 状态)``。状态不是 ``ok`` / ``unknown_type`` 时信封为 None；
    ``unknown_type`` 时信封**不返回**也是可以的，但这里选择不返回——调用方要的是
    「认识就给我、不认识就计数」，一个半解开的信封没有用处。
    """
    if isinstance(data, str):
        raw = data.encode("utf-8")
    else:
        raw = data

    # 先看体积再解析：70 KB 的恶意包不该让 JSON 解析器先跑一遍。
    if len(raw) > MAX_PAYLOAD_BYTES:
        return None, DecodeStatus.TOO_LARGE
    if not raw.strip():
        return None, DecodeStatus.BAD_JSON

    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, DecodeStatus.BAD_JSON

    if not isinstance(obj, dict):
        return None, DecodeStatus.BAD_JSON

    for key in _REQUIRED:
        if key not in obj:
            return None, DecodeStatus.MISSING_FIELD

    v = obj["v"]
    if not _is_int(v):
        return None, DecodeStatus.BAD_VALUE
    if v != PROTOCOL_MAJOR:
        # 只支持一个版本。`v > 2` 是未来版本，整条忽略不尝试部分理解（规则 1）；
        # `v < 2` 不可能出现在 cmp.* 上——旧客户端根本不发 cmp.*。
        return None, DecodeStatus.VERSION

    t = obj["t"]
    if not isinstance(t, str) or not t:
        return None, DecodeStatus.BAD_VALUE

    ident = obj["id"]
    if not isinstance(ident, str) or not ident:
        return None, DecodeStatus.BAD_VALUE

    seq = obj["seq"]
    if not _is_int(seq) or seq < 0:
        return None, DecodeStatus.BAD_VALUE

    ep = obj["ep"]
    if not isinstance(ep, str) or not ep:
        return None, DecodeStatus.BAD_VALUE

    args = obj["args"]
    if not isinstance(args, dict):
        return None, DecodeStatus.BAD_VALUE

    ts = obj.get("ts")
    if ts is not None and not _is_int(ts):
        return None, DecodeStatus.BAD_VALUE

    at = obj.get("at")
    if at is not None and not isinstance(at, dict):
        return None, DecodeStatus.BAD_VALUE

    dst_raw = obj.get("dst")
    dst: tuple[str, ...] | None = None
    if dst_raw is not None:
        if not isinstance(dst_raw, list) or not all(isinstance(x, str) for x in dst_raw):
            return None, DecodeStatus.BAD_VALUE
        dst = tuple(dst_raw)

    envelope = Envelope(
        v=v, t=t, id=ident, seq=seq, ep=ep, args=args,
        ts=ts, at=at, dst=dst, raw_bytes=len(raw),
    )

    # 方向与类型的校验放在 catalog；这里只管信封本身。但「t 不认识」是这一层
    # 就能判断的失败，早点返回比让调用方再查一次表更省事。
    from companion.agent.protocol.catalog import spec_of

    if spec_of(t) is None:
        return None, _UNKNOWN
    return envelope, DecodeStatus.OK


def encode(envelope: Envelope | dict[str, Any]) -> bytes:
    """序列化。`ts` / `at` / `dst` 为 None 时不写进 JSON——少几个字节，也少一处歧义。"""
    if isinstance(envelope, Envelope):
        payload: dict[str, Any] = {
            "v": envelope.v, "t": envelope.t, "id": envelope.id,
            "seq": envelope.seq, "ep": envelope.ep, "args": envelope.args,
        }
        if envelope.ts is not None:
            payload["ts"] = envelope.ts
        if envelope.at is not None:
            payload["at"] = envelope.at
        if envelope.dst is not None:
            payload["dst"] = list(envelope.dst)
    else:
        payload = dict(envelope)

    data = _encode_compact(payload)
    if len(data) > MAX_PAYLOAD_BYTES:
        # 发送侧断言失败（§14.1）：能编出来就说明上游在拼一条不该存在的消息，
        # 悄悄截断或分批会让接收方收到半条指令。
        raise ValueError(f"payload {len(data)} B exceeds {MAX_PAYLOAD_BYTES} B")
    return data


def new_envelope(
    event_type: str,
    *,
    args: dict[str, Any],
    seq: int,
    ep: str,
    ident: str,
    ts: int | None = None,
    at: dict[str, Any] | None = None,
    dst: list[str] | None = None,
) -> Envelope:
    """组一封新信。``id`` 由发送方给，不在这里生成——重发时 id 必须不变（§5 规则 4）。"""
    return Envelope(
        v=PROTOCOL_MAJOR, t=event_type, id=ident, seq=seq, ep=ep, args=args,
        ts=ts, at=at, dst=tuple(dst) if dst is not None else None,
    )


class Verdict(StrEnum):
    """接收状态机的判定。"""

    ACCEPT = "accept"
    DUPLICATE = "duplicate"
    STALE = "stale"
    NOT_FOR_ME = "not_for_me"


@dataclass
class ReceiverState:
    """去重与序号的簿记，按 ``(publisher, topic)`` 维度拆开。

    §5 说序号空间是 ``(publisher, ep, topic)``；把 ``ep`` 放进 key 里也成立，但
    换来的是每次重连都要多扫一遍旧 key。这里按 ``(publisher, topic)`` 记 last_seq
    并在 **ep 变化时重置**，效果等价且表不会随重连次数增长。

    去重表按 ``(publisher, ep)`` 记，同样在 ep 变化时清空——旧 epoch 的 id 与新的
    不可比，留着只会误杀新 id。
    """

    #: LRU 上限（§5 规则 4：256 条或 10 秒，取先到者）。
    dedup_capacity: int = 256

    _last_seq: dict[tuple[str, str], int] = field(default_factory=dict)
    _epoch: dict[tuple[str, str], str] = field(default_factory=dict)
    _seen: dict[str, dict[str, None]] = field(default_factory=dict)  # publisher -> 有序 id 集
    _seen_epoch: dict[str, str] = field(default_factory=dict)
    gaps: int = 0


class Receiver:
    """收侧状态机：去重 → 序号 → 定向 → 交给回调。

    只管信封层的判定，不看 ``args``。这样任何一个事件处理器写错，都不会影响
    「下一条消息还能不能进来」——§14.1 的统一原则。
    """

    def __init__(self, identity: str | None = None, *, state: ReceiverState | None = None) -> None:
        self.identity = identity
        self.state = state or ReceiverState()
        # 计数（§14.3）。按 topic × 结果分开记，运维才能区分「是网络还是我的编译器」。
        self.received = 0
        self.applied = 0
        self.dropped_dup = 0
        self.dropped_stale = 0
        self.dropped_expired = 0
        self.dropped_unknown = 0
        self.dropped_unauthorized = 0
        self.dropped_bad = 0

    def forget_publisher(self, publisher: str) -> None:
        """重连后清空某个发布者的全部簿记（§5.1）。"""
        for key in [k for k in self.state._last_seq if k[0] == publisher]:
            del self.state._last_seq[key]
            self.state._epoch.pop(key, None)
        self.state._seen.pop(publisher, None)
        self.state._seen_epoch.pop(publisher, None)

    def forget_all(self) -> None:
        """`RoomEvent.Reconnected` 上调用。"""
        self.state._last_seq.clear()
        self.state._epoch.clear()
        self.state._seen.clear()
        self.state._seen_epoch.clear()

    def _remember(self, publisher: str, ep: str, ident: str) -> None:
        seen = self.state._seen.setdefault(publisher, {})
        if self.state._seen_epoch.get(publisher) != ep:
            # 新 epoch：旧 id 与新 id 不可比，整张表作废。
            seen.clear()
            self.state._seen_epoch[publisher] = ep
        seen[ident] = None
        while len(seen) > self.state.dedup_capacity:
            # dict 保插入顺序，pop 第一个 key 就是最老的。
            seen.pop(next(iter(seen)))

    def _is_dup(self, publisher: str, ep: str, ident: str) -> bool:
        if self.state._seen_epoch.get(publisher) != ep:
            return False
        return ident in self.state._seen.get(publisher, {})

    def observe(self, envelope: Envelope, *, publisher: str, topic: str) -> Verdict:
        """按 §5 规则 3/4 与 §5.2 给一封信定性，并更新簿记。"""
        self.received += 1

        if not envelope.is_for(self.identity or ""):
            # dst 不是我：静默丢弃，不记 gap（我本来就不该看见它）。
            return Verdict.NOT_FOR_ME

        if self._is_dup(publisher, envelope.ep, envelope.id):
            self.dropped_dup += 1
            return Verdict.DUPLICATE

        key = (publisher, topic)
        previous_ep = self.state._epoch.get(key)
        last = self.state._last_seq.get(key)

        if previous_ep is not None and previous_ep != envelope.ep:
            # 换了 epoch：新流的 seq 从 0 开始，与旧的不可比（F4）。
            last = None

        if last is not None:
            if envelope.seq <= last:
                self.dropped_stale += 1
                self._remember(publisher, envelope.ep, envelope.id)
                return Verdict.STALE
            if envelope.seq > last + 1:
                # 跳号：计数，**不请求重传**（§5.2）。表现指令的价值窗口太短，
                # 等重传的空档比丢失更伤。
                self.state.gaps += 1

        elif envelope.seq != 0:
            # 流的第一条不是 0：开头就断了。同样只计数。
            self.state.gaps += 1

        self.state._last_seq[key] = envelope.seq
        self.state._epoch[key] = envelope.ep
        self._remember(publisher, envelope.ep, envelope.id)
        self.applied += 1
        return Verdict.ACCEPT
