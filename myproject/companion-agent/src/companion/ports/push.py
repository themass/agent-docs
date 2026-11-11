"""推送通知端口：用户不在线时，把「角色有新消息」送到设备上。

实现可以是 FCM、厂商通道，或者只记日志（开发环境）。推送只是提醒，消息本体仍从会话历史与 SSE 读取。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class PushMessage:
    owner_id: int
    title: str
    body: str
    data: dict[str, str] = field(default_factory=dict)   # 例如 session_id、turn_id，供客户端跳转


class PushPort(Protocol):
    async def send(self, message: PushMessage) -> bool:
        """返回是否已交给推送通道；失败不抛异常。"""
        ...
