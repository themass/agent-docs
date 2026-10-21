"""Agent message persistence."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jc.models.agent_message import AgentMessage


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

    async def has_prior_user_message(self, session_id: str) -> bool:
        """Whether this session already carries at least one `role=user, event_type=message` row.

        Used to decide whether a turn can send the pointer form of the coach's profile
        digest / methodology instead of the full text — the full text only needs to
        reach the model once per session, and "once" is defined by *this* table, not by
        a separate flag, so there is exactly one place that can disagree with itself
        about whether the first turn already happened.
        """
        stmt = (
            select(func.count())
            .select_from(AgentMessage)
            .where(
                AgentMessage.session_id == session_id,
                AgentMessage.role == "user",
                AgentMessage.event_type == "message",
            )
        )
        count = (await self._db.execute(stmt)).scalar_one()
        return count > 0

    async def first_user_titles(
        self, session_ids: list[str], *, max_len: int = 80
    ) -> dict[str, str]:
        """Earliest user message per session, trimmed for UI titles."""
        if not session_ids:
            return {}
        stmt = (
            select(AgentMessage.session_id, AgentMessage.content)
            .where(
                AgentMessage.session_id.in_(session_ids),
                AgentMessage.role == "user",
                AgentMessage.event_type == "message",
            )
            .order_by(AgentMessage.session_id, AgentMessage.created_at.asc())
        )
        rows = (await self._db.execute(stmt)).all()
        titles: dict[str, str] = {}
        for session_id, content in rows:
            if session_id in titles:
                continue
            text = (content or "").strip().replace("\n", " ")
            if not text:
                continue
            if len(text) > max_len:
                text = text[: max_len - 1].rstrip() + "…"
            titles[session_id] = text
        return titles

    async def list_for_session(self, session_id: str, *, limit: int = 500) -> list[AgentMessage]:
        stmt = (
            select(AgentMessage)
            .where(AgentMessage.session_id == session_id)
            .order_by(AgentMessage.created_at.asc())
            .limit(limit)
        )
        return list((await self._db.execute(stmt)).scalars().all())
