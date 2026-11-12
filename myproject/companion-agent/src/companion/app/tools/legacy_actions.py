"""旧 ``/companion`` 的确认动作接口改由 Postgres 提供服务。

为什么：陪伴页调 ``/companion/actions/pending`` 与 ``/companion/actions/{id}/confirm``，
这两个原来走旧容器的 ``ActionExecutor``——它把确认记录存在进程内，重启就没了，
而 ``/api/agent/v1/actions/*`` 读的是 Postgres。同一次「她请求你授权」的动作，
两个入口看到的结果不同，用户点完也可能因为进程重启而「没有发生过」。

适配层只做签名与形状转换，不复制授权逻辑：权限判断、幂等、过期都在
``ConfirmationService`` 里，和 ``/api/agent/v1`` 用的是同一份实现。

两个必须保留的旧行为：
1. 响应字段。旧客户端读 ``confirmation_id / action / description / arguments``，
   新服务只给 ``id / title / summary / expires_at``，这里补齐旧名字，不去改客户端。
2. 拒绝也要消费掉确认。旧的 ``ActionsApi.confirm`` 明确这么写：不然这条会一直挂在待办里。
"""

from __future__ import annotations

from typing import Any


class LegacyActionsAdapter:
    """旧 ``ActionsApi`` 的两个方法 → ``ConfirmationService``。"""

    def __init__(self, service: Any, *, descriptions: Any = None) -> None:
        self._service = service
        self._descriptions = descriptions

    async def pending(self, user_id: str) -> list[dict]:
        rows = await self._service.pending(owner_id=int(user_id))
        out: list[dict] = []
        for r in rows:
            out.append({
                "confirmation_id": r.id,
                "user_id": user_id,
                "character_id": getattr(r, "role_id", "") or "",
                "action": r.tool,
                "description": r.summary or r.title,
                "arguments": dict(r.args or {}),
                # 客户端目前不读这两个，但带上不影响旧解析，方便排查
                "title": r.title,
                "expires_at": r.expires_at.isoformat() if r.expires_at else "",
            })
        return out

    async def confirm(self, user_id: str, confirmation_id: str, *, accepted: bool) -> dict:
        # accept=False 也走决定接口：它会消费掉这条确认，避免永久挂在待办里。
        result = await self._service.decide(owner_id=int(user_id), confirmation_id=confirmation_id,
                                            accept=accepted)
        if result is None:
            # 与 /api/agent/v1 一致：不存在、不属于本人、或已处理都当作没有
            return {"status": "not_found"}
        return {
            "status": getattr(result, "status", "unknown"),
            "reason": getattr(result, "reason", ""),
        }
