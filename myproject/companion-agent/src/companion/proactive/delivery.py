"""投递：把「她决定开口」变成用户真的看到的一条消息。

调度决定什么时候判断，策略判断要不要说，这里负责说出去并且留下记录。分开的理由
是三者失败的方式不同：调度错于时间，策略错于分寸，投递错于通道。

三条不可让步的约束写在这里而不是文档里：

- 一次成功投递必须留下 [SendRecord]，否则下一轮频控看不见它，就会连发；
- 失败不重试，也不计入频控——用户没收到，就不该占他的额度；
- 去重不在这一层，在 [companion.proactive.loop]：只有循环知道一次「发生」的边界。

通道是变量，其余是不变量。所以这一层是对 [DeliveryPort] 的适配，不是 if 分支。
"""

from __future__ import annotations

import logging
import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from companion.proactive.models import Channel, InitiativeState, SendRecord

logger = logging.getLogger(__name__)


class DeliveryError(Exception):
    """投递失败。调用方记日志后放弃这一次，不重试。"""


def _iso(value: datetime) -> str:
    # 时间一律按 UTC 序列化；没带时区的按 UTC 解释，不让客户端猜。
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class DeliveryReceipt:
    """一次投递的凭据。成功才产生，失败只有异常。

    ``id`` 是客户端用来确认已读的句柄；``meta`` 带上触发原因与回合 id，
    用来回答「你为什么给我发这条」（设计文档第 10 节）。
    """

    id: str
    user_id: str
    character_id: str
    text: str
    channel: Channel
    at: datetime
    meta: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "character_id": self.character_id,
            "text": self.text,
            "channel": self.channel.value,
            "at": _iso(self.at),
            "meta": dict(self.meta),
        }


class DeliveryPort(Protocol):
    """一个输出通道。

    实现有两种失败方式，都必须明确：抛 [DeliveryError] 表示这次没发出去；
    静默返回表示发出去了。不允许「返回 False 表示失败」——调用方会忘。

    ``at`` 由调用方给，而不是取 ``datetime.now()``：频控记录与测试要用同一个时钟。
    """

    async def deliver(
        self,
        *,
        user_id: str,
        character_id: str,
        text: str,
        channel: Channel,
        at: datetime,
        meta: dict[str, Any] | None = None,
    ) -> DeliveryReceipt: ...


class SendRecorder(Protocol):
    """记下一次成功投递。频控下一轮靠它。"""

    async def record(self, user_id: str, record: SendRecord) -> None: ...


class InMemorySendLedger:
    """投递账本。现在只在进程内，换数据库只换实现。

    它同时是 [InitiativeScheduler] 的 ``state_loader`` 来源——装配时必须把
    ``ledger.state_for`` 传给调度器，否则每一轮都从空记录开始判断，频控形同虚设。
    """

    def __init__(self) -> None:
        self._sent: dict[str, list[SendRecord]] = {}

    async def record(self, user_id: str, record: SendRecord) -> None:
        self._sent.setdefault(user_id, []).append(record)

    async def state_for(self, user_id: str) -> InitiativeState:
        # 返回快照：策略只读，不能改到账本本身。
        return InitiativeState(sent=list(self._sent.get(user_id, [])))

    async def records_for(self, user_id: str) -> list[SendRecord]:
        return list(self._sent.get(user_id, []))


class InAppDelivery:
    """v1 的应用内通道：写进内存收件箱，客户端轮询取走。

    为什么先有它：推送未接之前，应用内消息是唯一不会丢的通道，而且它不打断人——
    用户打开应用才看到。进程内有效、重启即丢，单实例够用；多副本部署要换共享存储，
    换的是注入的实例，不是调用方。
    """

    def __init__(self, *, history: int = 200) -> None:
        if history < 1:
            raise ValueError("history must be positive")
        self._history = history
        self._boxes: dict[str, list[DeliveryReceipt]] = {}

    async def deliver(
        self,
        *,
        user_id: str,
        character_id: str,
        text: str,
        channel: Channel,
        at: datetime,
        meta: dict[str, Any] | None = None,
    ) -> DeliveryReceipt:
        receipt = DeliveryReceipt(
            id=f"inapp-{secrets.token_urlsafe(12)}",
            user_id=user_id,
            character_id=character_id,
            text=text,
            channel=channel,
            at=at,
            meta=dict(meta or {}),
        )
        box = self._boxes.setdefault(user_id, [])
        box.append(receipt)
        # 有界：一个长期不打开应用的用户不该把内存吃满。
        if len(box) > self._history:
            del box[: len(box) - self._history]
        return receipt

    async def inbox(self, user_id: str) -> list[DeliveryReceipt]:
        """尚未被取走的消息，按时间正序。"""
        return list(self._boxes.get(user_id, []))

    async def drain(self, user_id: str, *, limit: int = 50) -> list[DeliveryReceipt]:
        """取走并清空，客户端确认收到后调用。"""
        box = self._boxes.get(user_id, [])
        taken, rest = box[: max(0, limit)], box[max(0, limit) :]
        if rest:
            self._boxes[user_id] = rest
        else:
            self._boxes.pop(user_id, None)
        return list(taken)


class PushDelivery:
    """FCM 通道（**未接**）。

    真实实现要做的事，按顺序：

    1. 从环境变量读服务账号：``COMPANION_FCM_PROJECT_ID``、
       ``COMPANION_FCM_CLIENT_EMAIL``、``COMPANION_FCM_PRIVATE_KEY``
       （多行私钥用 ``\\n`` 转义）。凭证只从环境来，不进代码、配置与仓库。
    2. 用 google-auth 换 OAuth2 access token，POST
       ``https://fcm.googleapis.com/v1/projects/<project>/messages:send``，
       消息体 ``{"message": {"token": <设备 token>, "notification": {...},
       "data": {"character_id": ..., "channel": "push"}}}``。
    3. 设备 token 由客户端注册接口写入，按 ``user_id`` 查；一个用户多台设备时
       逐台发，全部失败才算失败。
    4. 401/404（token 失效）删掉该设备注册；5xx 也不重试。重发比漏发烦人得多。
    5. 权限：Google Play 要求这是服务性消息，必须带退订入口（设计文档第 16 节）。

    在此之前它只抛 [NotImplementedError]。接了一半的推送比没有推送更危险——
    它会在半夜把一条只写了一半的消息发出去。
    """

    ENV_PROJECT_ID = "COMPANION_FCM_PROJECT_ID"
    ENV_CLIENT_EMAIL = "COMPANION_FCM_CLIENT_EMAIL"
    ENV_PRIVATE_KEY = "COMPANION_FCM_PRIVATE_KEY"

    def __init__(self, *, environ: Mapping[str, str] | None = None) -> None:
        env = os.environ if environ is None else environ
        self._credentials = {
            name: (env.get(name) or "").strip()
            for name in (self.ENV_PROJECT_ID, self.ENV_CLIENT_EMAIL, self.ENV_PRIVATE_KEY)
        }

    @property
    def configured(self) -> bool:
        return all(self._credentials.values())

    async def deliver(
        self,
        *,
        user_id: str,
        character_id: str,
        text: str,
        channel: Channel,
        at: datetime,
        meta: dict[str, Any] | None = None,
    ) -> DeliveryReceipt:
        missing = [name for name, value in self._credentials.items() if not value]
        if missing:
            raise NotImplementedError(
                "push 通道未配置：缺少环境变量 "
                + "、".join(missing)
                + "。配置方式见 PushDelivery 文档字符串；本次不投递。"
            )
        raise NotImplementedError(
            "push 通道尚未实现：凭证已就位，但 FCM 客户端还没接上。"
            "这里不假装发送——半条消息比没有消息更糟。"
        )


class RecordingDelivery:
    """测试与本地联调用的通道：记住发了什么，可以让前几次失败。

    ``fail_times`` 递减而不是一个布尔，是为了覆盖「失败一次之后恢复正常」——
    那正是「失败不重试但下一件事照发」要验证的路径。
    """

    def __init__(self, *, fail_times: int = 0, channel: Channel = Channel.IN_APP) -> None:
        self.attempts = 0
        self.deliveries: list[DeliveryReceipt] = []
        self._fail_remaining = fail_times
        self._channel = channel

    async def deliver(
        self,
        *,
        user_id: str,
        character_id: str,
        text: str,
        channel: Channel,
        at: datetime,
        meta: dict[str, Any] | None = None,
    ) -> DeliveryReceipt:
        self.attempts += 1
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            raise DeliveryError(f"scripted failure for {user_id}")
        receipt = DeliveryReceipt(
            id=f"rec-{len(self.deliveries) + 1}",
            user_id=user_id,
            character_id=character_id,
            text=text,
            channel=channel,
            at=at,
            meta=dict(meta or {}),
        )
        self.deliveries.append(receipt)
        return receipt


class ChannelRouter:
    """按决策选的通道投递，成功才记账。

    通道缺实现时降级到应用内而不是丢弃：用户打开了「重要事件提醒」，那件事就该
    至少出现在应用里；电话要等通道接上才有。降级失败才算投递失败。
    """

    def __init__(
        self,
        ports: Mapping[Channel, DeliveryPort],
        *,
        recorder: SendRecorder | None = None,
        fallback: Channel = Channel.IN_APP,
    ) -> None:
        self._ports = dict(ports)
        self._recorder = recorder
        self._fallback = fallback

    async def send(
        self,
        *,
        user_id: str,
        character_id: str,
        text: str,
        channel: Channel,
        trigger: str = "",
        at: datetime,
        meta: dict[str, Any] | None = None,
    ) -> DeliveryReceipt:
        actual = channel
        port = self._ports.get(channel)
        if port is None:
            actual = self._fallback
            port = self._ports.get(actual)
            if port is None:
                raise DeliveryError(f"no delivery port for channel {channel.value!r}")
            logger.info(
                "channel %s has no port, falling back to %s", channel.value, actual.value
            )

        receipt = await port.deliver(
            user_id=user_id,
            character_id=character_id,
            text=text,
            channel=actual,
            at=at,
            meta=meta,
        )

        if self._recorder is not None:
            # 记账用实际通道：降级之后发的是应用内消息，就按应用内记。
            # 记账失败会抛出去——宁可把这次记成失败，也不能让频控以为没发过。
            await self._recorder.record(
                user_id,
                SendRecord(at=receipt.at, channel=receipt.channel, trigger=trigger),
            )
        return receipt


__all__ = [
    "ChannelRouter",
    "DeliveryError",
    "DeliveryPort",
    "DeliveryReceipt",
    "InAppDelivery",
    "InMemorySendLedger",
    "PushDelivery",
    "RecordingDelivery",
    "SendRecorder",
]
