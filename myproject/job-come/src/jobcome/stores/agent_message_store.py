"""Agent message persistence."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.models.agent_message import AgentMessage


class AgentMessageStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def append(
        self,
        *,
        message_id: str,
        session_id: str,
        role: str,
        event_type: str,
        content: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AgentMessage:
        row = AgentMessage(
            id=message_id,
            session_id=session_id,
            role=role,
            event_type=event_type,
            content=content,
            payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
        )
        self._db.add(row)
        await self._db.flush()
        return row

    async def list_for_session(self, session_id: str, *, limit: int = 500) -> list[AgentMessage]:
        stmt = (
            select(AgentMessage)
            .where(AgentMessage.session_id == session_id)
            .order_by(AgentMessage.created_at.asc())
            .limit(limit)
        )
        return list((await self._db.execute(stmt)).scalars().all())
