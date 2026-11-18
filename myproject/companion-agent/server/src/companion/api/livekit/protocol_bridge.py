"""把协议 v2 的纯逻辑接到一个真实房间上（§5 / §7 / §14.2）。

这一层只做三件在房外做不了的事：

1. **收**：从 ``Room`` 的 ``data_received`` 里取出 topic、字节和发布者，交给
   :class:`Receiver` 判定，再按 ``t`` 分派。
2. **握**：``control.hello`` 进来时算交集、回去一条 ``control.hello_ack``；
   3 秒内没等到 hello 就按 ``compat:"v1"`` 走旧 topic（§7.3）。
3. **发**：给每条外发消息维护 ``(ep, topic)`` 内单调递增的 ``seq``（§5.1）。

**所有入向处理都不许抛。** §14.1 要求单条消息的失败既不影响后续消息，也不冒到
事件循环顶层——一个被伪造的包不该让整个房间的 agent 掉线。所以这里每个出口都是
"记一个计数桶然后返回"，没有一处 ``raise``。

不 import ``livekit``：房间对象按鸭子类型用（只要有 ``on`` / ``publish_data``），
这样单测直接喂假对象就行，不需要装整个语音栈。
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from companion.agent.protocol import (
    LEGACY_WAIT_SECONDS,
    DecodeStatus,
    Receiver,
    Side,
    Verdict,
    allowed,
    decode,
    encode,
    legacy_ack,
    negotiate,
    new_envelope,
    parse_hello,
    supports,
)
from companion.agent.protocol.catalog import TOPIC_CTL, TOPIC_CUE
from companion.agent.protocol.handshake import HelloAck, NegotiationError
from companion.agent.protocol.speech_plan import PlannedSegment

logger = logging.getLogger(__name__)

#: 这些 kind 的参与者代表「服务端自己」，不是用户设备。它们发来的客户端消息一律拒。
#: AGENT 是另一个 agent 进程（多 agent 场景下会出现在同一个房间）；EGRESS 是录制端。
#: 其余（STANDARD / SIP / CONNECTOR / BRIDGE / INGRESS / UNKNOWN）都按用户设备对待：
#: SIP 与 CONNECTOR 背后是真人，拒掉它们等于让电话用户用不了。
_SERVER_KINDS = frozenset({"AGENT", "EGRESS"})


def _kind_name(kind: Any) -> str:
    """``Participant.kind`` 在不同版本里是枚举、整型或字符串，统一成大写名字。"""
    name = getattr(kind, "name", None)
    if isinstance(name, str):
        return name.upper()
    return str(kind).rsplit(".", 1)[-1].upper()


class ProtocolBridge:
    """一条连接的协议状态。一个房间一个。

    ``send`` 是 ``(topic, payload_bytes) -> Awaitable``，由调用方接上
    ``LocalParticipant.publish_data``。测试里换成一个把消息存进列表的假函数即可。
    """

    def __init__(
        self,
        *,
        send: Callable[[str, bytes], Awaitable[None]],
        identity: str | None = None,
        local_identity: str | None = None,
        sid: str | None = None,
        legacy_timeout: float = LEGACY_WAIT_SECONDS,
    ) -> None:
        self.receiver = Receiver(identity)
        self.ack: HelloAck | None = None
        self.legacy = False
        # 客户端最近一次自报的 §14.3 计数快照。只留最后一份：这是诊断信息，
        # 不是需要累积的账本——累积会把内存变成一台没人读的日志。
        self.telemetry: dict[str, Any] | None = None
        # 每次连接换一个新 epoch：客户端据此判断「旧流的 seq 和我不可比」（§5.1）。
        self.epoch = uuid.uuid4().hex[:16]
        self.sid = sid or uuid.uuid4().hex[:12]
        self.legacy_timeout = legacy_timeout
        self.local_identity = local_identity
        self._send = send
        self._seq: dict[str, int] = {}
        self._hello_seen = asyncio.Event()
        #: 因未协商而没发出去的外发消息，按 ``t`` 计数（§14.3）。
        self.unsent: dict[str, int] = {}
        #: 过了信封层、却没有任何处理器的 ``t``，按名字计数（§14.3）。
        #:
        #: 没有这个桶，一条 ``control.barge_in`` 会被计进 ``received`` 然后什么都不做，
        #: 两端日志都干净——「目录里声明了、代码里没有」这种缺口就永远查不出来。
        self.unhandled: dict[str, int] = {}
        #: ``control.input``（端侧触摸等即时输入）的消费者。None 表示还没有人接。
        #: 见 §15 迁移表：``companion.touch`` 文本流迁移到这里。
        self.on_input: Callable[[dict[str, Any]], None] | None = None
        #: ``control.barge_in``（端侧检测到用户开口）的消费者。可以是同步或 async。
        #: None 时计入 ``unhandled``——目录声明了、代码没接上，必须看得见（§14.3）。
        self.on_barge: Callable[[dict[str, Any]], Any] | None = None

    # ------------------------------------------------------------------ 发送

    async def publish(
        self, event_type: str, args: dict[str, Any], *, topic: str, force: bool = False
    ) -> bool:
        """组一封带 seq 的信发出去。返回是否真的发了。

        ``cmp.*`` 只在协商出 v2 之后才发：v1 连接不认识这些 topic，发了只是在
        空转，还会让客户端日志里多出一条解不开的消息。``force`` 只给握手本身用
        ——协商失败的 ack 必须发出去，否则客户端只能干等超时，日志里看不出是
        谁的错。
        """
        if not force and not self._may_send(event_type):
            # §14.3：握手前或能力未协商时的静默丢弃要可见，否则「表情没出来」无从查起。
            self.unsent[event_type] = self.unsent.get(event_type, 0) + 1
            return False
        seq = self._seq.get(topic, 0)
        envelope = new_envelope(
            event_type,
            args=args,
            seq=seq,
            ep=self.epoch,
            ident=uuid.uuid4().hex[:12],
        )
        try:
            await self._send(topic, encode(envelope))
        except Exception as exc:  # noqa: BLE001
            # 发不出去只记日志：表现层断掉不该拽停整条会话。
            logger.warning("publish %s to %s failed: %s", event_type, topic, exc)
            return False
        self._seq[topic] = seq + 1
        return True

    def _may_send(self, event_type: str) -> bool:
        if self.ack is None:
            return False
        return supports(self.ack, event_type)

    # ------------------------------------------------------------------ 接收

    async def on_data(
        self,
        data: bytes,
        *,
        topic: str | None,
        publisher_identity: str | None,
        publisher_kind: Any = None,
    ) -> Verdict | None:
        """一条数据包进来了。永不抛异常。

        返回 ``None`` 表示这条消息在信封层就被拒了（没有可归属的判定）。
        """
        # 计数口径：走到 observe 的消息由它自己计入 received，提前返回的在这里记，
        # 两者相加才是「收到的全部」。
        envelope, status = decode(data)
        if envelope is None:
            self.receiver.received += 1
            if status is DecodeStatus.UNKNOWN_TYPE:
                # 不是失败：这一版还不认识这个 t，忽略即可（§5 规则 2）。
                self.receiver.dropped_unknown += 1
            else:
                self.receiver.dropped_bad += 1
            return None

        if not topic:
            # 没有 topic 的数据包不可能是协议 v2 的信封：四个 topic 是唯一的入口。
            self.receiver.received += 1
            self.receiver.dropped_bad += 1
            return None

        if not self._publisher_allowed(publisher_identity, publisher_kind):
            self.receiver.received += 1
            self.receiver.dropped_unauthorized += 1
            return None

        if not allowed(topic, envelope.t, receiving=Side.SERVER):
            self.receiver.received += 1
            self.receiver.dropped_unauthorized += 1
            return None

        verdict = self.receiver.observe(
            envelope, publisher=publisher_identity or "", topic=topic
        )
        if verdict is not Verdict.ACCEPT:
            return verdict

        try:
            await self._dispatch(envelope, topic)
        except Exception as exc:  # noqa: BLE001
            # 处理器写错不能让下一条消息进不来（§14.1）。
            self.receiver.dropped_bad += 1
            logger.warning("handler for %s failed: %s", envelope.t, exc)
        return verdict

    def _publisher_allowed(self, identity: str | None, kind: Any) -> bool:
        """§14.2 的身份白名单。

        方向白名单（``allowed``）只看 ``t`` 与 topic，挡不住「另一个 agent 冒充客户端」。
        真正能挡住的是发布者的身份：自己发的包、以及服务端 kind 的参与者发来的客户端
        消息，都不该被当成用户输入——否则一个被注入的 agent 就能替用户按确认。
        """
        if not identity:
            return False
        if self.local_identity is not None and identity == self.local_identity:
            return False
        return _kind_name(kind) not in _SERVER_KINDS

    async def _dispatch(self, envelope: Any, topic: str) -> None:
        if envelope.t == "control.hello":
            await self._on_hello(envelope)
        elif envelope.t == "telemetry.health":
            self._on_health(envelope)
        elif envelope.t == "control.input":
            self._on_input(envelope)
        elif envelope.t == "control.barge_in":
            await self._on_barge(envelope)
        else:
            # 目录里有、代码里还没有消费者的 t。收侧已经把它计进 received 了，
            # 所以这里必须单独记一笔，否则「声明了但没实现」看起来跟「处理成功」一样。
            first = envelope.t not in self.unhandled
            self.unhandled[envelope.t] = self.unhandled.get(envelope.t, 0) + 1
            if first:
                logger.info("unhandled event type %s on %s (no handler)", envelope.t, topic)

    async def _on_barge(self, envelope: Any) -> None:
        """``control.barge_in``（§10.1）：端侧检测到用户开口。

        没有消费者时只记 ``unhandled``。处理器可以是同步或 async（``BargeInRelay``
        是 async，因为它要 ``await speech.cancel()``）。
        """
        handler = self.on_barge
        if handler is None:
            self.unhandled[envelope.t] = self.unhandled.get(envelope.t, 0) + 1
            return
        args = envelope.args if isinstance(envelope.args, dict) else {}
        try:
            result = handler(args)
            if hasattr(result, "__await__"):
                await result  # type: ignore[misc]
        except Exception as exc:  # noqa: BLE001 —— §14.1：处理器写错不拖停消息链
            logger.warning("control.barge_in handler failed: %s", exc)

    def _on_input(self, envelope: Any) -> None:
        """``control.input``（§15 迁移表）：端侧的即时输入，目前是触摸。

        没有消费者时只记 ``unhandled``，不抛也不吞——触摸是低价值输入，丢一条不该
        影响会话，但丢的次数必须看得见。
        """
        handler = self.on_input
        if handler is None:
            self.unhandled[envelope.t] = self.unhandled.get(envelope.t, 0) + 1
            return
        args = envelope.args if isinstance(envelope.args, dict) else {}
        try:
            handler(args)
        except Exception as exc:  # noqa: BLE001 —— §14.1：处理器写错不拖停消息链
            logger.warning("control.input handler failed: %s", exc)

    def _on_health(self, envelope: Any) -> None:
        """收下客户端自报的 §14.3 计数与降级档位。

        只留最后一份并打日志：服务端拿它区分「全网问题还是单个客户端问题」
        （文档 §8 ``telemetry.health`` 那一行的用途）。不抛——一个字段缺失的
        健康包不值得把整条消息链记成 bad。
        """
        args = envelope.args if isinstance(envelope.args, dict) else {}
        self.telemetry = args
        logger.info(
            "client health sid=%s degrade=%s applied=%s dropped_bad=%s gaps=%s",
            self.sid,
            args.get("degrade_level"),
            args.get("applied"),
            args.get("dropped_bad"),
            args.get("gap_count"),
        )

    # ------------------------------------------------------------------ 表现指令

    async def cue_emotion(self, name: str, intensity: float | None = None) -> bool:
        """给客户端发一条 ``presentation.emotion``（§11.1）。

        args 的键是 ``name`` 而不是 ``emotion``——这是 v2 与 v1 旧事件唯一不兼容的
        地方，写错了客户端会静默当成未知情绪映射成 neutral。

        v1 连接由 ``_may_send`` 挡掉：它们本来就在收 ``companion.avatar`` 上的同一个
        情绪，多发一条只会让老客户端的日志里多一条解不开的包。
        """
        args: dict[str, Any] = {"name": name}
        if intensity is not None:
            args["intensity"] = intensity
        return await self.publish("presentation.emotion", args, topic=TOPIC_CUE)

    # ------------------------------------------------------------------ 语音时间线

    async def speech_seg(self, speech_id: str, seg: PlannedSegment) -> bool:
        """``speech.seg``：声明一句（§9.3）。必须先于引用它的 cue 与它的 TTS 发出（§13 不变量 1）。"""
        return await self.publish(
            "speech.seg", seg.seg_args(speech_id), topic=TOPIC_CUE
        )

    async def speech_end(self, speech_id: str) -> bool:
        return await self.publish("speech.end", {"speech_id": speech_id}, topic=TOPIC_CUE)

    async def cancel_speech(self, speech_id: str, reason: str = "user_barge_in") -> bool:
        """``control.cancel``：该 speech 作废（§10.2），端侧墓碑化（§10.3）。"""
        return await self.publish(
            "control.cancel", {"speech_id": speech_id, "reason": reason}, topic=TOPIC_CTL
        )

    async def _on_hello(self, envelope: Any) -> None:
        try:
            hello = parse_hello(envelope.args)
            ack = negotiate(hello, sid=self.sid)
        except NegotiationError as exc:
            # 谈不拢不是「退回到默认能力集」的理由：猜一个能力集会让服务端发
            # 客户端收不了的消息。一个明确的 ack 比让客户端等超时有用。
            logger.warning("hello rejected: %s", exc)
            await self._send_failure_ack("incompatible")
            return
        self.ack = ack
        self._hello_seen.set()
        await self.publish("control.hello_ack", ack.args(), topic=TOPIC_CTL, force=True)
        logger.info(
            "protocol negotiated sid=%s compat=%s caps=%d client=%s/%s",
            ack.sid, ack.compat, len(ack.caps), hello.client.app, hello.client.version,
        )

    async def _send_failure_ack(self, compat: str) -> None:
        ack = HelloAck(sid=self.sid, caps={}, limits={}, compat=compat)
        await self.publish("control.hello_ack", ack.args(), topic=TOPIC_CTL, force=True)

    async def wait_for_hello(self) -> HelloAck:
        """等握手，超时按 v1 处理（§7.3）。老客户端从不发 hello。"""
        if self.ack is not None:
            return self.ack
        try:
            await asyncio.wait_for(self._hello_seen.wait(), timeout=self.legacy_timeout)
            assert self.ack is not None
            return self.ack
        except TimeoutError:
            self.legacy = True
            self.ack = legacy_ack(sid=self.sid)
            logger.info("no hello within %.1fs, treating as v1 sid=%s", self.legacy_timeout, self.sid)
            return self.ack


def attach(room: Any, bridge: ProtocolBridge) -> None:
    """把 bridge 挂到一个真实房间上。

    ``data_received`` 的回调是同步的（LiveKit 直接调用），协程要自己起 task——
    在回调里 ``await`` 会让 SDK 的事件循环卡住。

    包的发布者对象在收到时才有，所以身份检查放在 ``on_data`` 里做而不是这里。
    """

    def _on_data(packet: Any) -> None:
        publisher = getattr(packet, "participant", None)
        asyncio.get_running_loop().create_task(
            bridge.on_data(
                getattr(packet, "data", b"") or b"",
                topic=getattr(packet, "topic", None),
                publisher_identity=getattr(publisher, "identity", None),
                publisher_kind=getattr(publisher, "kind", None),
            )
        )

    room.on("data_received", _on_data)


def local_sender(room: Any) -> Callable[[str, bytes], Awaitable[None]]:
    """把 ``LocalParticipant.publish_data`` 包成 bridge 期望的 ``(topic, bytes)``。"""

    async def _send(topic: str, payload: bytes) -> None:
        await room.local_participant.publish_data(payload, topic=topic)

    return _send


def json_bytes(payload: dict[str, Any]) -> bytes:
    """``ensure_ascii=False``：中文按 UTF-8 走，不转义成 \\uXXXX。"""
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")
