"""主动消息收件箱：客户端轮询取走她主动发来的消息。

v1 通道是应用内收件箱（设计文档第 10 节）：推送未接前，它是唯一不会丢、也不
打断人的通道——用户打开应用才看到。取走即清空，客户端收到后就不会再拿到同一条。
"""


from typing import Any


class InboxApi:
    def __init__(self, *, delivery: Any) -> None:
        self._delivery = delivery

    async def take(self, user_id: str, *, limit: int = 20) -> list[dict]:
        receipts = await self._delivery.drain(user_id, limit=limit)
        return [
            {
                "id": r.id,
                "character_id": r.character_id,
                "text": r.text,
                "channel": getattr(r.channel, "value", str(r.channel)),
                "at": r.at.isoformat(),
                "trigger": (r.meta or {}).get("trigger", ""),
            }
            for r in receipts
        ]


def build_router(*, inbox: InboxApi, current_user: Any):
    from fastapi import APIRouter, Depends, Query

    router = APIRouter(prefix="/v1", tags=["companion"])

    @router.get("/inbox")
    async def take_inbox(
        limit: int = Query(20, ge=1, le=50),
        user_id: str = Depends(current_user),
    ) -> list[dict]:
        return await inbox.take(user_id, limit=limit)

    return router
