"""LiveKit 建房：把会话的身份写进房间 metadata。

agent 入场时从 ``ctx.room.metadata`` 读 user_id / character_id，读不到就拒绝。
这份 metadata 只能由服务端写：客户端拿到的 token 无权改房间元数据。
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable


def livekit_room_provisioner(
    *, url: str, api_key: str, api_secret: str
) -> Callable[[str, dict[str, str]], Awaitable[None]]:
    """返回一个建房函数，供 ``SessionService.provision_room`` 使用。"""

    async def provision(room_name: str, metadata: dict[str, str]) -> None:
        from livekit import api

        client = api.LiveKitAPI(url=url, api_key=api_key, api_secret=api_secret)
        try:
            await client.room.create_room(
                api.CreateRoomRequest(
                    name=room_name,
                    metadata=json.dumps(metadata, ensure_ascii=False),
                )
            )
        finally:
            await client.aclose()

    return provision
