from __future__ import annotations

import logging
import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from companion.service.proactive.models import Channel, InitiativeState, SendRecord
from companion.service.proactive.delivery_port import DeliveryError, DeliveryPort, DeliveryReceipt, SendRecorder

logger = logging.getLogger(__name__)


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
