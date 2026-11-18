"""协议 v2 的事件目录：每个 ``t`` 属于哪个 topic、哪个投递类、哪个方向。

这是一张**表**，不是逻辑。放进协议层的唯一理由是收发两侧都要按同一张表校验方向，
而方向校验是安全边界（§14.2）：房间里任何人（包括被邀请的第三方）都能往同一个
room 发数据包，不校验方向就等于允许别人伪造一条 ``presentation.emotion``，或者
伪造 ``control.response`` 去替用户应答一次确认。

新增一个 ``t`` 只需要在这里加一行；删掉或改名才需要动协议大版本（§8）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Delivery(StrEnum):
    """投递语义三分类（§6）。

    A 必须到达、B 有截止期、C 可丢。这里只做标记：真正决定走 RELIABLE 还是
    LOSSY 的是发送侧的 topic，而 ``cmp.tel`` 是四个 topic 里唯一的 LOSSY。
    """

    MUST = "A"
    DEADLINE = "B"
    DROPPABLE = "C"


class Side(StrEnum):
    """一条消息的「这一端」。服务端就是 agent 进程，客户端就是房间里的用户设备。"""

    SERVER = "server"
    CLIENT = "client"


TOPIC_CUE = "cmp.cue"
TOPIC_CTL = "cmp.ctl"
TOPIC_IN = "cmp.in"
TOPIC_TEL = "cmp.tel"

TOPICS = frozenset({TOPIC_CUE, TOPIC_CTL, TOPIC_IN, TOPIC_TEL})


@dataclass(frozen=True, slots=True)
class EventSpec:
    """一个 ``t`` 的静态属性。

    ``senders`` / ``receivers`` 分开写而不是合并成「方向」枚举：``control.ping``
    两个方向都合法，但它仍然只属于 ``cmp.ctl``，用一个集合表达双向比给枚举加一个
    ``BOTH`` 成员更直白。
    """

    topic: str
    delivery: Delivery
    senders: frozenset[Side]
    receivers: frozenset[Side]


def _spec(topic: str, delivery: Delivery, *, from_: Side | None = None) -> EventSpec:
    """单向事件的简写：``from_`` 是发送方，接收方自然是另一侧。

    ``from_=None`` 表示双向（只有 ping/pong）。
    """
    if from_ is None:
        return EventSpec(topic, delivery, frozenset(Side), frozenset(Side))
    other = Side.CLIENT if from_ is Side.SERVER else Side.SERVER
    return EventSpec(topic, delivery, frozenset({from_}), frozenset({other}))


_CLIENT = Side.CLIENT
_SERVER = Side.SERVER

EVENTS: dict[str, EventSpec] = {
    # ---- 控制面（cmp.ctl）----
    "control.hello": _spec(TOPIC_CTL, Delivery.MUST, from_=_CLIENT),
    "control.hello_ack": _spec(TOPIC_CTL, Delivery.MUST, from_=_SERVER),
    "control.ping": _spec(TOPIC_CTL, Delivery.MUST),
    "control.pong": _spec(TOPIC_CTL, Delivery.MUST),
    "control.cancel": _spec(TOPIC_CTL, Delivery.MUST, from_=_SERVER),
    "control.request": _spec(TOPIC_CTL, Delivery.MUST, from_=_SERVER),
    "control.response": _spec(TOPIC_CTL, Delivery.MUST, from_=_CLIENT),
    "control.barge_in": _spec(TOPIC_CTL, Delivery.MUST, from_=_CLIENT),
    # 触摸语义走数据包而不是文本流：建流的开销不值得（§15 迁移表）。
    "control.input": _spec(TOPIC_IN, Delivery.MUST, from_=_CLIENT),
    # ---- 表现面（cmp.cue）----
    "speech.seg": _spec(TOPIC_CUE, Delivery.MUST, from_=_SERVER),
    "speech.end": _spec(TOPIC_CUE, Delivery.MUST, from_=_SERVER),
    "presentation.state": _spec(TOPIC_CUE, Delivery.DEADLINE, from_=_SERVER),
    "presentation.emotion": _spec(TOPIC_CUE, Delivery.DEADLINE, from_=_SERVER),
    "presentation.gesture": _spec(TOPIC_CUE, Delivery.DEADLINE, from_=_SERVER),
    "presentation.gaze": _spec(TOPIC_CUE, Delivery.DEADLINE, from_=_SERVER),
    "presentation.resync": _spec(TOPIC_CUE, Delivery.MUST, from_=_SERVER),
    # ---- 感知与遥测（cmp.tel）----
    "perception.attention": _spec(TOPIC_TEL, Delivery.DROPPABLE, from_=_CLIENT),
    "telemetry.health": _spec(TOPIC_TEL, Delivery.DROPPABLE, from_=_CLIENT),
}


def spec_of(event_type: str) -> EventSpec | None:
    """按 ``t`` 取属性；不认识返回 None（调用方据此计 ``dropped_unknown``）。"""
    return EVENTS.get(event_type)


def allowed(topic: str, event_type: str, *, receiving: Side) -> bool:
    """这一端能不能收这条消息（§14.2 方向白名单）。

    三重条件缺一不可：topic 在白名单里、``t`` 认识、且这个 ``t`` 确实属于这个
    topic 并且是发给这一侧的。第二种与第三种合在一起挡的是「direction 对但
    topic 不对」——例如有人往 ``cmp.in`` 上塞一条 cue。
    """
    entry = EVENTS.get(event_type)
    if entry is None:
        return False
    if entry.topic != topic:
        return False
    return receiving in entry.receivers


def may_send(topic: str, event_type: str, *, sending: Side) -> bool:
    """这一端能不能发这条消息。发送侧的断言用，接收侧的 [allowed] 才是安全边界。"""
    entry = EVENTS.get(event_type)
    if entry is None or entry.topic != topic:
        return False
    return sending in entry.senders
