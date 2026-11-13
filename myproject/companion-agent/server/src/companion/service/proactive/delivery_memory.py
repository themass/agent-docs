from __future__ import annotations

import logging
import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from companion.service.proactive.delivery_port import DeliveryError, DeliveryReceipt
from companion.service.proactive.models import Channel, InitiativeState, SendRecord


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
