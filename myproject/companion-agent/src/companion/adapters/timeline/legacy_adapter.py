"""把旧 ``/companion`` 路由的 memory / timeline 调用接到 Postgres。

为什么需要它：陪伴页（客户端 ``feature-companion``）调的是 ``/companion/memory`` 与
``/companion/events``，这两个路由拿的是旧容器的内存存储——重启后「她记得的」就空了，
主动消息事件也全没了。新栈（``/api/agent/v1/facts`` 等）读的却是 Postgres，
同一份数据两个入口、两个结果。

这个适配层只做签名翻译，不复制业务逻辑：

- 记忆：新栈的 ``ScopedMemory`` 已经就是 ``list_for_user`` / ``delete_one``，直接用；
- 事件：旧路由要 ``list_for_user`` / ``add`` / ``update_status`` / ``delete_one`` 这几个旧名字，
  而 ``SqlTimelineStore`` 用的是 ``list_for_owner`` / ``upsert`` / ``set_status`` / ``delete``，
  这里把旧名字翻译过去。

翻译过程中有两处必须保持旧行为，否则客户端会看到变化：

1. 旧 ``list_for_user`` 是「这个人所有角色的事件」；新 ``list_for_owner`` 的 ``role_id``
   参数传 ``None`` 才表示不限角色，这里必须传 ``None`` 而不是空串。
2. 旧路由给用户手加的事件没有 role_id，新表该列非空——统一落成空串（语义是「用户级」，
   与 ``ca_timeline_event`` 里既有的约定一致）。
"""

from __future__ import annotations

from typing import Any

from companion.domain.timeline.models import EventStatus, TimelineEvent


class LegacyTimelineAdapter:
    """旧 ``InMemoryTimeline`` 的四个方法名 → ``SqlTimelineStore``。"""

    def __init__(self, timeline: Any) -> None:
        self._timeline = timeline

    async def list_for_user(self, user_id: str, *, limit: int = 50, include_past: bool = False
                            ) -> list[TimelineEvent]:
        # role_id=None 表示不限角色；旧路由本来就不按角色过滤
        return await self._timeline.list_for_owner(
            owner_id=user_id, role_id=None, include_past=include_past, limit=limit)

    async def add(self, event: TimelineEvent) -> TimelineEvent:
        if not event.source_character_id:
            # 用户手动添加的事件属于「所有角色」，空串是既有的约定
            event.source_character_id = ""
        return await self._timeline.upsert(event)

    async def update_status(self, user_id: str, event_id: str, status: EventStatus) -> bool:
        return await self._timeline.set_status(owner_id=user_id, public_id=event_id, status=status)

    async def delete_one(self, user_id: str, event_id: str) -> bool:
        return await self._timeline.delete(owner_id=user_id, public_id=event_id)
