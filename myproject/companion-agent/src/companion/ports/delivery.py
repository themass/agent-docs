from __future__ import annotations

import logging
import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from companion.domain.proactive.models import Channel, InitiativeState, SendRecord


class DeliveryError(Exception):
    """投递失败。调用方记日志后放弃这一次，不重试。"""


def _iso(value: datetime) -> str:
    # 时间一律按 UTC 序列化；没带时区的按 UTC 解释，不让客户端猜。
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


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
