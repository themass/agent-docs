"""动作确认与偏好设置接口。

两个都是「用户对她的控制权」：动作确认决定她能不能替用户做事，偏好决定她能不能
主动开口。这两件事错了，信任就没了，所以接口本身要尽量不可误用。
"""


import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class ActionsApi:
    def __init__(self, *, executor: Any) -> None:
        self._executor = executor

    async def pending(self, user_id: str) -> list[dict]:
        """待确认动作。过滤在执行器里做（它持有确认存储），这里只做转交。"""
        return await self._executor.pending(user_id)

    async def confirm(self, user_id: str, confirmation_id: str, *, accepted: bool):
        if not accepted:
            # 拒绝也要消费掉这条确认，否则它会一直挂在待办里。
            await self._executor.discard(confirmation_id, user_id)
            return {"status": "declined"}
        outcome = await self._executor.confirm(confirmation_id, user_id)
        return {
            "status": getattr(outcome, "status", "unknown"),
            "reason": getattr(outcome, "reason", ""),
        }


class PreferencesApi:
    """主动性的偏好。默认值来自 InitiativePreferences，不是这里另定一套。"""

    def __init__(self, *, store: Any) -> None:
        self._store = store

    async def get(self, user_id: str) -> dict:
        return await self._store.load(user_id)

    async def update(self, user_id: str, patch: dict) -> dict:
        return await self._store.save(user_id, patch)


class InMemoryPreferencesStore:
    """进程内偏好。接口与真实存储一致，换 Redis/DB 时只换这个类。"""

    def __init__(self, defaults: Any) -> None:
        self._defaults = defaults
        self._items: dict[str, Any] = {}

    async def load(self, user_id: str) -> Any:
        return self._items.get(user_id, self._defaults)

    async def save(self, user_id: str, patch: dict) -> Any:
        current = self._items.get(user_id, self._defaults)
        updated = _apply_patch(current, patch)
        self._items[user_id] = updated
        return updated


def _apply_patch(preferences: Any, patch: dict) -> Any:
    """按字段打补丁。只接受 dataclass 上真实存在的字段。

    不认识字段就忽略而不是报错：客户端版本比服务端新时，不该整个设置页保存失败。
    """
    from dataclasses import fields, replace

    known = {f.name for f in fields(preferences)}
    values = {k: v for k, v in patch.items() if k in known}
    for key in ("quiet_start", "quiet_end"):
        if isinstance(values.get(key), str):
            from datetime import time

            hour, _, minute = values[key].partition(":")
            values[key] = time(int(hour), int(minute or 0))
    if isinstance(values.get("paused_until"), str):
        raw = values["paused_until"].strip()
        # 空串表示恢复。服务端把 null 当成「不修改」，所以恢复必须走显式的空串。
        values["paused_until"] = (
            datetime.fromisoformat(raw.replace("Z", "+00:00")) if raw else None
        )
    return replace(preferences, **values)


def build_router(
    *, actions: ActionsApi, preferences: PreferencesApi, current_user: Any
):
    from fastapi import APIRouter, Depends, HTTPException
    from pydantic import BaseModel

    class ConfirmIn(BaseModel):
        accepted: bool

    class PrefsPatch(BaseModel):
        events_enabled: bool | None = None
        greetings_enabled: bool | None = None
        call_enabled: bool | None = None
        quiet_start: str | None = None
        quiet_end: str | None = None
        max_per_day: int | None = None
        max_per_week: int | None = None
        paused_until: str | None = None

    # 确认动作已经统一到 /v1/actions（读的是同一份 Postgres 确认存储），
    # 这里只保留偏好——它是 /v1 下唯一还没有对应实现的资源。
    router = APIRouter(prefix="/v1", tags=["companion"])

    @router.get("/prefs")
    async def get_prefs(user_id: str = Depends(current_user)) -> dict:
        prefs = await preferences.get(user_id)
        return _prefs_to_dict(prefs)

    @router.put("/prefs")
    async def put_prefs(body: PrefsPatch, user_id: str = Depends(current_user)) -> dict:
        patch = {k: v for k, v in body.model_dump().items() if v is not None}
        updated = await preferences.update(user_id, patch)
        return _prefs_to_dict(updated)

    return router


def _prefs_to_dict(preferences: Any) -> dict:
    def fmt(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if hasattr(value, "strftime"):
            return value.strftime("%H:%M")
        return value

    return {
        name: fmt(getattr(preferences, name))
        for name in (
            "events_enabled",
            "greetings_enabled",
            "call_enabled",
            "quiet_start",
            "quiet_end",
            "max_per_day",
            "max_per_week",
            "paused_until",
        )
        if hasattr(preferences, name)
    }
