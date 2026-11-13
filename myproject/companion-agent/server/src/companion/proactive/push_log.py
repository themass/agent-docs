"""推送通道的开发实现：只记日志。接入 FCM / 厂商通道时换成真实实现，接口不变。"""

from __future__ import annotations

import logging

from companion.proactive.push_port import PushMessage

log = logging.getLogger("companion.push")


class LogPush:
    async def send(self, message: PushMessage) -> bool:
        log.info("push", extra={"owner_id": message.owner_id, "title": message.title, "data": message.data})
        return True
