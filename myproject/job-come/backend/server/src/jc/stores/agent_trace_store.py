"""Agent trace ledger persistence — append-only, ordered by (session_id, seq)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jc.models.agent import AgentSession
from jc.models.agent_trace import AgentTrace


class AgentTraceStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def lock_session(self, session_id: str) -> None:
        """Acquire before flushing child rows, avoiding FK lock upgrades."""
        await self._db.execute(
            select(AgentSession.id).where(AgentSession.id == session_id).with_for_update()
        )

    async def next_seq(self, session_id: str) -> int:
        """Allocate under a short, database-backed session-local append lock.

        Frontend queues cannot serialize multiple tabs/instances. The parent row
        also exists before the first trace, so the empty-ledger case is locked.
        Use a locking/current read of the tail (not COUNT, nor an older repeatable
        read snapshot) so deleted sequence gaps cannot produce duplicate numbers.
        Caller commits immediately after an event, never across model latency.
        """
        await self.lock_session(session_id)
        last = await self._db.scalar(
            select(AgentTrace.seq).where(AgentTrace.session_id == session_id)
            .order_by(AgentTrace.seq.desc()).limit(1).with_for_update()
        )
        return int(last) + 1 if last is not None else 0

    async def append(
        self,
        *,
        trace_id_pk: str,
        session_id: str,
        event_type: str,
        role: str,
        payload: dict[str, Any],
        seq: int | None = None,
        user_id: str | None = None,
        profile_id: str | None = None,
        job_id: str | None = None,
        mock_session_id: str | None = None,
        trace_id: str | None = None,
        llm_call_id: str | None = None,
        ui_event: str | None = None,
        content: str | None = None,
    ) -> AgentTrace:
        if seq is None:
            seq = await self.next_seq(session_id)
        row = AgentTrace(
            id=trace_id_pk,
            session_id=session_id,
            seq=seq,
            user_id=user_id,
            profile_id=profile_id,
            job_id=job_id,
            mock_session_id=mock_session_id,
            trace_id=trace_id,
            llm_call_id=llm_call_id,
            event_type=event_type,
            ui_event=ui_event,
            role=role,
            content=content,
            payload=payload,
        )
        self._db.add(row)
        await self._db.flush()
        return row

    async def list_for_session(self, session_id: str, *, limit: int = 5000) -> list[AgentTrace]:
        stmt = (
            select(AgentTrace)
            .where(AgentTrace.session_id == session_id)
            .order_by(AgentTrace.seq.asc())
            .limit(limit)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def latest_mock_session_id(self, session_id: str) -> str | None:
        """The interview this chat was last recorded against, if any. A chat resumed from the
        history list arrives without the interview in its UI context; its own ledger still knows."""
        stmt = (
            select(AgentTrace.mock_session_id)
            .where(AgentTrace.session_id == session_id, AgentTrace.mock_session_id.isnot(None))
            .order_by(AgentTrace.seq.desc())
            .limit(1)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def list_ui_for_session(
        self, session_id: str, *, limit: int = 500
    ) -> list[AgentTrace]:
        """The rows the chat UI renders, in order.

        Filters on `ui_event IS NOT NULL` rather than on a list of event types:
        the whole point of that column is that "does the UI draw this" is decided
        once, where the row is written, and the reader cannot drift from it.
        """
        stmt = (
            select(AgentTrace)
            .where(
                AgentTrace.session_id == session_id,
                AgentTrace.ui_event.isnot(None),
            )
            .order_by(AgentTrace.seq.asc())
            .limit(limit)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def first_ui_content(self, session_ids: list[str]) -> dict[str, str]:
        """Earliest user-visible user message per session, for the chat list title."""
        if not session_ids:
            return {}
        stmt = (
            select(AgentTrace.session_id, AgentTrace.content)
            .where(
                AgentTrace.session_id.in_(session_ids),
                AgentTrace.event_type == "user_message",
                AgentTrace.ui_event.isnot(None),
            )
            .order_by(AgentTrace.session_id, AgentTrace.seq.asc())
        )
        rows = (await self._db.execute(stmt)).all()
        titles: dict[str, str] = {}
        for session_id, content in rows:
            if session_id in titles:
                continue
            text = (content or "").strip().replace("\n", " ")
            if text:
                titles[session_id] = text[:79].rstrip() + "…" if len(text) > 80 else text
        return titles

    async def find_confirm(self, session_id: str, confirm_id: str) -> AgentTrace | None:
        """The `confirm` row for one card, read from the ledger rather than a client payload.

        Scans the session's confirm rows: there are a handful per session and the
        alternative — a JSON field lookup — would need a JSONB index on a table
        whose payload is deliberately opaque text.
        """
        rows = (
            await self._db.execute(
                select(AgentTrace)
                .where(
                    AgentTrace.session_id == session_id,
                    AgentTrace.event_type.in_(
                        ["confirm", "confirm_applied", "confirm_rejected"]
                    ),
                )
                .order_by(AgentTrace.seq.asc())
            )
        ).scalars().all()
        for row in rows:
            if (row.payload or {}).get("confirm_id") == confirm_id:
                return row
        return None

    async def has_system_prompt(self, session_id: str) -> bool:
        """Whether this session already carries its one `system_prompt` row.

        "Once per session" is defined by querying this table, not by a separate
        flag that could disagree with what was actually written.
        """
        stmt = (
            select(func.count())
            .select_from(AgentTrace)
            .where(
                AgentTrace.session_id == session_id,
                AgentTrace.event_type == "system_prompt",
            )
        )
        count = (await self._db.execute(stmt)).scalar_one()
        return count > 0
