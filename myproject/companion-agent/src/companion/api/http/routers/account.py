"""账号注销接口（chat-agent-ops-design.md §3）。前缀 /api/agent/v1。不用 __future__ 注解。

App 的注销流程先调这里、再调 Java 的注销接口：反过来的话 token 先失效，就再也证明不了身份。
返回 202：会话已经关闭，跨存储删除由 worker 的 ``account.purge`` 任务完成。重复调用只入队一次。
"""

from typing import Any

from companion.api.http.routers.chat import _owner_id
from companion.app.account.purge import AccountPurgeService

PREFIX = "/api/agent/v1"


def build_router(service: AccountPurgeService, current_user):
    from fastapi import APIRouter, Depends

    router = APIRouter(prefix=PREFIX, tags=["account"])

    @router.delete("/me", status_code=202)
    async def delete_me(user_id: str = Depends(current_user)) -> dict[str, Any]:
        await service.request(owner_id=_owner_id(user_id))
        return {"status": "accepted"}

    return router
