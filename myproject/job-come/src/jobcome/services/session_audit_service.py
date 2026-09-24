"""Admin session audit — MySQL timeline + LangGraph checkpoint reads."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.adapters.deerflow_client import _client_config
from jobcome.adapters.deerflow_harness_client import _get_embedded_client
from jobcome.exceptions import NotFoundError
from jobcome.models.agent_message import AgentMessage
from jobcome.schemas.admin_session import (
    AdminCheckpointMessage,
    AdminCheckpointResponse,
    AdminCheckpointSummary,
    AdminSessionDetailResponse,
    AdminSessionListItem,
    AdminSessionListResponse,
    AdminTimelineResponse,
    AdminTimelineTurn,
)
from jobcome.stores.agent_message_store import AgentMessageStore
from jobcome.stores.agent_store import AgentStore


def _parse_payload(row: AgentMessage) -> dict[str, Any] | None:
    if not row.payload_json:
        return None
    try:
        return json.loads(row.payload_json)
    except json.JSONDecodeError:
        return None


def _serialize_lc_message(msg: Any, index: int) -> AdminCheckpointMessage:
    if hasattr(msg, "model_dump"):
        data = msg.model_dump()
    elif isinstance(msg, dict):
        data = msg
    else:
        return AdminCheckpointMessage(index=index, role="unknown", content=str(msg))

    role = str(data.get("type") or data.get("role") or "unknown")
    tool_calls = data.get("tool_calls") or []
    if tool_calls and not isinstance(tool_calls, list):
        tool_calls = [tool_calls]

    return AdminCheckpointMessage(
        index=index,
        role=role,
        content=data.get("content"),
        tool_calls=[tc if isinstance(tc, dict) else getattr(tc, "model_dump", lambda: tc)() for tc in tool_calls],
        tool_name=data.get("name"),
        tool_call_id=data.get("tool_call_id"),
        additional_kwargs=data.get("additional_kwargs") or {},
        usage_metadata=data.get("usage_metadata"),
    )


def _build_turns(rows: list[AgentMessage]) -> list[AdminTimelineTurn]:
    turns: list[AdminTimelineTurn] = []
    current: AdminTimelineTurn | None = None
    turn_idx = 0

    def start_turn() -> AdminTimelineTurn:
        nonlocal turn_idx, current
        current = AdminTimelineTurn(turn_index=turn_idx, events=[])
        turn_idx += 1
        turns.append(current)
        return current

    for row in rows:
        payload = _parse_payload(row)
        if row.event_type == "message" and row.role == "user":
            turn = start_turn()
            turn.user_message = row.content
            turn.user_attachments = list((payload or {}).get("attachments") or [])
            turn.started_at = row.created_at
            continue

        if current is None:
            turn = start_turn()
        else:
            turn = current

        if row.event_type == "message" and row.role == "assistant":
            turn.assistant_message = row.content
            turn.ended_at = row.created_at
            continue

        event = {
            "id": row.id,
            "event_type": row.event_type,
            "role": row.role,
            "content": row.content,
            "payload": payload,
            "created_at": row.created_at.isoformat(),
        }
        turn.events.append(event)
        if turn.ended_at is None or row.created_at > turn.ended_at:
            turn.ended_at = row.created_at

    return turns


class SessionAuditService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._sessions = AgentStore(db)
        self._messages = AgentMessageStore(db)

    async def list_sessions(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        user_id: str | None = None,
    ) -> AdminSessionListResponse:
        rows, total = await self._sessions.list_all(
            limit=min(limit, 200),
            offset=offset,
            user_id=user_id,
        )
        counts = await self._sessions.message_counts([s.id for s in rows])
        sessions = [
            AdminSessionListItem(
                id=s.id,
                user_id=s.user_id,
                profile_id=s.profile_id,
                job_id=s.job_id,
                kind=s.kind,
                status=s.status,
                skill_hint=s.skill_hint,
                deerflow_thread_id=s.deerflow_thread_id,
                trace_id=s.trace_id,
                message_count=counts.get(s.id, 0),
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in rows
        ]
        return AdminSessionListResponse(
            sessions=sessions,
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_session(self, session_id: str) -> AdminSessionDetailResponse:
        session = await self._sessions.get_by_id(session_id)
        if session is None:
            raise NotFoundError("Session not found", code="session_not_found")
        counts = await self._sessions.message_counts([session.id])
        return AdminSessionDetailResponse(
            id=session.id,
            user_id=session.user_id,
            profile_id=session.profile_id,
            job_id=session.job_id,
            kind=session.kind,
            status=session.status,
            skill_hint=session.skill_hint,
            deerflow_thread_id=session.deerflow_thread_id,
            trace_id=session.trace_id,
            message_count=counts.get(session.id, 0),
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    async def get_timeline(self, session_id: str, *, limit: int = 2000) -> AdminTimelineResponse:
        session = await self._sessions.get_by_id(session_id)
        if session is None:
            raise NotFoundError("Session not found", code="session_not_found")
        rows = await self._messages.list_for_session(session_id, limit=limit)
        turns = _build_turns(rows)
        return AdminTimelineResponse(
            session_id=session.id,
            deerflow_thread_id=session.deerflow_thread_id,
            turns=turns,
            raw_message_count=len(rows),
        )

    async def get_checkpoint(self, session_id: str) -> AdminCheckpointResponse:
        session = await self._sessions.get_by_id(session_id)
        if session is None:
            raise NotFoundError("Session not found", code="session_not_found")

        skill = session.skill_hint or "resume-coach"
        client = _get_embedded_client(_client_config(), skill)
        data = client.get_thread(session.deerflow_thread_id)
        checkpoints = data.get("checkpoints") or []

        summaries: list[AdminCheckpointSummary] = []
        for cp in checkpoints:
            vals = cp.get("values") or {}
            msgs = vals.get("messages") or []
            summaries.append(
                AdminCheckpointSummary(
                    checkpoint_id=str(cp.get("checkpoint_id") or ""),
                    parent_checkpoint_id=cp.get("parent_checkpoint_id"),
                    ts=cp.get("ts"),
                    message_count=len(msgs),
                )
            )

        latest = checkpoints[-1] if checkpoints else {}
        vals = latest.get("values") or {}
        raw_messages = vals.get("messages") or []
        messages = [_serialize_lc_message(m, i) for i, m in enumerate(raw_messages)]

        return AdminCheckpointResponse(
            session_id=session.id,
            deerflow_thread_id=session.deerflow_thread_id,
            checkpoint_count=len(checkpoints),
            latest_checkpoint_id=str(latest.get("checkpoint_id") or "") or None,
            summaries=summaries,
            messages=messages,
            skill_context=vals.get("skill_context") or {},
            thread_data=vals.get("thread_data") or {},
        )
