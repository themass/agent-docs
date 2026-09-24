"""In-app notification inbox (computed + persisted read/dismiss state)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from agentkit.web.auth import Actor, UserActor
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.schemas.notification import (
    NotificationAction,
    NotificationDismissRequest,
    NotificationItem,
    NotificationListResponse,
    NotificationReadRequest,
)
from jobcome.stores.profile_store import ProfileStore
from jobcome.stores.user_store import UserStore


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._users = UserStore(db)
        self._profiles = ProfileStore(db)

    async def list_for_actor(self, *, actor: Actor) -> NotificationListResponse:
        if not isinstance(actor, UserActor):
            return NotificationListResponse(items=[], unread_count=0)

        state = await self._load_state(actor.user_id)
        items = await self._build_items(actor.user_id, state)
        unread = sum(1 for i in items if not i.read)
        return NotificationListResponse(items=items, unread_count=unread)

    async def mark_read(self, *, actor: UserActor, body: NotificationReadRequest) -> NotificationListResponse:
        state = await self._load_state(actor.user_id)
        read_at = datetime.now(UTC).isoformat()
        for nid in body.notification_ids:
            state.setdefault("read", {})[nid] = read_at
        await self._save_state(actor.user_id, state)
        return await self.list_for_actor(actor=actor)

    async def dismiss(self, *, actor: UserActor, body: NotificationDismissRequest) -> NotificationListResponse:
        state = await self._load_state(actor.user_id)
        dismissed_at = datetime.now(UTC).isoformat()
        for nid in body.notification_ids:
            state.setdefault("dismissed", {})[nid] = dismissed_at
        await self._save_state(actor.user_id, state)
        return await self.list_for_actor(actor=actor)

    async def _build_items(self, user_id: str, state: dict[str, Any]) -> list[NotificationItem]:
        now = datetime.now(UTC)
        read_map = state.get("read", {})
        dismissed_map = state.get("dismissed", {})
        items: list[NotificationItem] = []

        user = await self._users.get_by_id(user_id)
        if user and not user.email_verified_at:
            nid = "email_verify"
            if nid not in dismissed_map:
                items.append(
                    NotificationItem(
                        id=nid,
                        type="email_verify",
                        priority="high",
                        title="邮箱尚未验证",
                        body="验证邮箱后可解锁导出等完整功能。",
                        created_at=user.created_at or now,
                        read=nid in read_map,
                        dismissed=False,
                        dismiss_policy="auto_when_resolved",
                        action=NotificationAction(label="重发验证邮件", action="resend_verification"),
                        metadata={"tone": "amber"},
                    )
                )

        profile = await self._profiles.get_active_for_user(user_id)
        if profile:
            if profile.status == "draft":
                nid = f"profile_confirm_{profile.id}"
                if nid not in dismissed_map:
                    items.append(
                        NotificationItem(
                            id=nid,
                            type="profile_action",
                            priority="normal",
                            title="档案待确认",
                            body="核对工作经历与要点后确认，方可生成拔高预览。",
                            created_at=profile.updated_at or now,
                            read=nid in read_map,
                            dismissed=False,
                            dismiss_policy="auto_when_resolved",
                            action=NotificationAction(label="去核对", href="/resume-agent"),
                            metadata={"tone": "blue"},
                        )
                    )

            source_profile = await self._profiles.get_by_id(profile.id, with_sources=True)
            source = source_profile.sources[0] if source_profile and source_profile.sources else None
            if source and source.parse_error:
                nid = f"parse_warn_{profile.id}"
                if nid not in dismissed_map:
                    items.append(
                        NotificationItem(
                            id=nid,
                            type="parse_quality",
                            priority="high",
                            title="简历解析未走完整链路",
                            body=source.parse_error[:240],
                            created_at=source.created_at or now,
                            read=nid in read_map,
                            dismissed=False,
                            dismiss_policy="manual",
                            action=NotificationAction(label="查看档案", href="/resume-agent"),
                            metadata={"tone": "rose"},
                        )
                    )

        priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        items.sort(
            key=lambda i: (priority_order.get(i.priority, 9), i.created_at),
        )
        return items

    async def _load_state(self, user_id: str) -> dict[str, Any]:
        meta = await self._users.get_or_create_meta(user_id)
        if not meta.inbox_state_json:
            return {"read": {}, "dismissed": {}}
        try:
            data = json.loads(meta.inbox_state_json)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        return {"read": {}, "dismissed": {}}

    async def _save_state(self, user_id: str, state: dict[str, Any]) -> None:
        meta = await self._users.get_or_create_meta(user_id)
        meta.inbox_state_json = json.dumps(state, ensure_ascii=False)
        await self._db.commit()
