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
        """Acquire before flushing child rows, avoiding FK lock upgrades.

        `FOR NO KEY UPDATE`, not `FOR UPDATE`, and the difference is a production
        outage rather than a nicety.

        PostgreSQL's row lock modes are not a simple strength ladder. An insert into
        a child table takes `FOR KEY SHARE` on the referenced parent row, and
        `FOR KEY SHARE` conflicts with exactly one mode: `FOR UPDATE`. Every other
        mode — including `FOR NO KEY UPDATE` — is compatible with it.

        This method is called from inside the streaming loop, and the lock is not
        released until the next commit, which can be most of a turn away. So while
        an agent turn was running, the API process held `FOR UPDATE` on the
        `jc_agent_session` row, and the MCP subprocess — a separate process, a
        separate connection — could not insert into `jc_profile_patch_confirm`,
        which carries a foreign key to that session. Measured: `jc_profile_patch`
        blocked until its 120 s client timeout, every time, while `jc_profile_get`
        (no child insert) answered in under a second. Reproduced deliberately by
        holding `FOR UPDATE` on the session row from a second connection:
        `baseline OK 4.4s` → `while-locked TIMEOUT >20s` → `after-release OK 2.4s`.

        `FOR NO KEY UPDATE` still excludes other writers, which is all `next_seq`
        needs — two concurrent appends cannot allocate the same sequence number —
        while leaving foreign-key checks free to proceed.
        """
        await self._db.execute(
            select(AgentSession.id)
            .where(AgentSession.id == session_id)
            # postgresql: key_share=True with read=False renders FOR NO KEY UPDATE.
            .with_for_update(key_share=True)
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
            .order_by(AgentTrace.seq.desc()).limit(1)
            # Same reasoning as `lock_session`: the tail row does not need to block
            # foreign-key checks either.
            .with_for_update(key_share=True)
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
        client_message_id: str | None = None,
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
            client_message_id=client_message_id,
        )
        self._db.add(row)
        await self._db.flush()
        return row

    async def append_batch(
        self,
        items: list[dict[str, Any]],
        *,
        session_id: str,
    ) -> list[AgentTrace]:
        """Append several rows with ONE sequence allocation and one flush.

        Why this exists: `append` allocates a sequence (lock the parent row + read
        the tail) and flushes per row. Against a database 166 ms away that is three
        round-trips per event, and a turn with tool calls emits dozens of events —
        so the ledger alone cost seconds per turn.

        Continuity is preserved by allocating `seq` ONCE for the batch and walking
        it upward. That is the same guarantee `append` gives (the allocation is
        under the parent row's lock), just amortised: two concurrent turns still
        serialise on that lock, and neither can observe a gap.

        The caller commits. Batching inside one transaction keeps the rows atomic
        with respect to a reader: a chat that reloads mid-turn sees a prefix, never
        a hole.
        """
        if not items:
            return []
        start = await self.next_seq(session_id)
        rows: list[AgentTrace] = []
        for offset, item in enumerate(items):
            seq = item.get("seq")
            row = AgentTrace(
                id=item["trace_id_pk"],
                session_id=session_id,
                seq=start + offset if seq is None else seq,
                user_id=item.get("user_id"),
                profile_id=item.get("profile_id"),
                job_id=item.get("job_id"),
                mock_session_id=item.get("mock_session_id"),
                trace_id=item.get("trace_id"),
                llm_call_id=item.get("llm_call_id"),
                event_type=item["event_type"],
                ui_event=item.get("ui_event"),
                role=item["role"],
                content=item.get("content"),
                payload=item.get("payload") or {},
            )
            self._db.add(row)
            rows.append(row)
        await self._db.flush()
        return rows

    async def find_user_message(
        self, session_id: str, client_message_id: str
    ) -> AgentTrace | None:
        """The user row already written under this client id, if any.

        The idempotency lookup for (session_id, client_message_id) (R2 G2).
        The partial unique index makes this a single-index lookup and — the
        part no service-level check can do — makes two simultaneous resends
        of the same id one insert and one IntegrityError rather than two rows.
        """
        stmt = (
            select(AgentTrace)
            .where(
                AgentTrace.session_id == session_id,
                AgentTrace.event_type == "user_message",
                AgentTrace.client_message_id == client_message_id,
            )
            .order_by(AgentTrace.seq.asc())
            .limit(1)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def has_assistant_reply_after(self, session_id: str, seq: int) -> bool:
        """Whether a user row at `seq` already reached a committed answer.

        Decides what a resend of the same `client_message_id` IS (R2 G2):

        * False — the previous attempt died before `assistant_message` was
          committed (it is batched with the turn's end, so any abort, timeout
          or worker death leaves it absent). This is the retry-button case,
          and the turn must re-run: TECH-API: 模型仍会再跑一轮，因为第一次
          可能根本没跑完.
        * True — the first attempt completed. Another run would cost the
          model twice and print the answer twice; that resend is refused
          with a 409 instead.

        An `error` row after the user row does NOT count: a turn that ended
        in a visible error is exactly the one the user is allowed to retry.
        """
        stmt = (
            select(AgentTrace.id)
            .where(
                AgentTrace.session_id == session_id,
                AgentTrace.seq > seq,
                AgentTrace.event_type == "assistant_message",
            )
            .limit(1)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none() is not None

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
