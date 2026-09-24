"""Agent session orchestration."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from agentkit.adapters.deerflow.client import AgentRunMetadata
from agentkit.common.ids import new_id
from agentkit.web.auth import UserActor
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.adapters.deerflow_harness_client import _extract_text
from jobcome.adapters.deerflow_client import get_deerflow_client
from jobcome.agent.context_usage import build_context_usage_event
from jobcome.agent.message_content import flatten_message_for_text_agent
from jobcome.config import settings
from jobcome.exceptions import NotFoundError
from jobcome.models.agent import AgentSession
from jobcome.models.agent_message import AgentMessage
from jobcome.models.enums import AgentSessionKind, AgentSessionStatus
from jobcome.schemas.agent import (
    AgentAttachment,
    AgentConfirmRequest,
    AgentConfirmResponse,
    AgentMessageListResponse,
    AgentMessageRecord,
    AgentSessionCreateRequest,
    AgentSessionListItem,
    AgentSessionListResponse,
    AgentSessionResponse,
)
from jobcome.observability.events import log_product_event
from jobcome.services.profile_service import ProfileService
from jobcome.mcp.context import McpRunContext
from jobcome.mcp.handlers import profile_patch
from jobcome.stores.agent_message_store import AgentMessageStore
from jobcome.stores.agent_store import AgentStore

_PERSIST_EVENT_TYPES = frozenset(
    {
        "thinking",
        "tool_start",
        "tool",
        "tool_result",
        "plan_todos",
        "subagent_start",
        "subagent_done",
        "confirm",
        "usage",
        "error",
    }
)

_TOOL_ACTIVITY_EVENT_TYPES = frozenset(
    {
        "thinking",
        "tool_start",
        "tool",
        "tool_result",
        "plan_todos",
        "subagent_start",
        "subagent_done",
        "confirm",
    }
)

_ASSISTANT_FALLBACK = "处理完成。如需继续，请描述下一步需求。"


def _finalize_assistant_content(assistant_parts: list[str], had_tool_activity: bool) -> str | None:
    text = "".join(assistant_parts).strip()
    if text:
        return "".join(assistant_parts)
    if had_tool_activity:
        return _ASSISTANT_FALLBACK
    return None


def _format_user_message(content: str, attachments: list[AgentAttachment]) -> str:
    parts: list[str] = []
    if content.strip():
        parts.append(content.strip())
    for att in attachments:
        if att.kind == "image":
            parts.append(f"[Attached image: {att.label or att.name}]")
        elif att.kind == "audio":
            parts.append(f"[Attached voice: {att.label or att.name}]")
        elif att.text_preview:
            preview = att.text_preview[:4000]
            parts.append(f"[Attached file: {att.name}]\n{preview}")
        else:
            parts.append(f"[Attached file: {att.name}]")
    return "\n\n".join(parts) if parts else "(empty)"


class AgentService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._store = AgentStore(db)
        self._messages = AgentMessageStore(db)
        self._profiles = ProfileService(db)

    async def create_session(
        self,
        *,
        actor: UserActor,
        body: AgentSessionCreateRequest,
        trace_id: str,
    ) -> AgentSessionResponse:
        profile_id = body.profile_id
        if profile_id:
            await self._profiles.get(profile_id, actor=actor)

        extra: dict = {}
        if body.job_id:
            extra["job_id"] = body.job_id

        client = get_deerflow_client(db=self._db)
        metadata = AgentRunMetadata(
            trace_id=trace_id,
            user_id=actor.user_id,
            profile_id=profile_id,
            session_id=None,
            skill_hint=body.skill_hint,
            extra=extra,
        )
        thread_id = await client.start_session(metadata=metadata)

        session = AgentSession(
            id=new_id("agsn"),
            user_id=actor.user_id,
            profile_id=profile_id,
            job_id=body.job_id,
            kind=body.kind or AgentSessionKind.RESUME,
            status=AgentSessionStatus.ACTIVE,
            deerflow_thread_id=thread_id,
            skill_hint=body.skill_hint,
            trace_id=trace_id,
        )
        await self._store.create(session)
        # Load server-side timestamps before commit/response (avoids async lazy-load).
        await self._db.refresh(session)
        await self._db.commit()
        return self._to_response(session)

    async def get_session(self, session_id: str, *, actor: UserActor) -> AgentSessionResponse:
        session = await self._require_session(session_id, actor=actor)
        return self._to_response(session)

    async def list_sessions(
        self,
        *,
        actor: UserActor,
        profile_id: str | None = None,
        kind: str | None = None,
        limit: int = 20,
    ) -> AgentSessionListResponse:
        rows = await self._store.list_for_user(
            actor.user_id,
            profile_id=profile_id,
            kind=kind,
            limit=min(limit, 50),
        )
        return AgentSessionListResponse(
            sessions=[
                AgentSessionListItem(
                    id=s.id,
                    skill_hint=s.skill_hint,
                    kind=s.kind,
                    status=s.status,
                    profile_id=s.profile_id,
                    created_at=s.created_at,
                    updated_at=s.updated_at,
                )
                for s in rows
            ]
        )

    async def list_messages(
        self, session_id: str, *, actor: UserActor
    ) -> AgentMessageListResponse:
        await self._require_session(session_id, actor=actor)
        rows = await self._messages.list_for_session(session_id)
        return AgentMessageListResponse(
            session_id=session_id,
            messages=[self._to_message_record(row) for row in rows],
        )

    async def stream_message(
        self,
        session_id: str,
        *,
        actor: UserActor,
        content: str,
        attachments: list[AgentAttachment] | None = None,
        reply_locale: str = "zh-CN",
    ) -> AsyncIterator[dict]:
        session = await self._require_session(session_id, actor=actor)
        attachment_list = attachments or []
        user_text = _format_user_message(content, attachment_list)

        await self._messages.append(
            message_id=new_id("agm"),
            session_id=session.id,
            role="user",
            event_type="message",
            content=user_text,
            payload={"attachments": [a.model_dump() for a in attachment_list]}
            if attachment_list
            else None,
        )
        await self._db.commit()

        client = get_deerflow_client(db=self._db)
        metadata = AgentRunMetadata(
            trace_id=session.trace_id or "",
            user_id=actor.user_id,
            profile_id=session.profile_id,
            session_id=session.id,
            skill_hint=session.skill_hint,
            extra={
                **({"job_id": session.job_id} if session.job_id else {}),
                "reply_locale": reply_locale,
            },
        )

        agent_message = await flatten_message_for_text_agent(content, attachment_list)
        from jobcome.agent.reply_locale import reply_language_instruction
        from jobcome.agent.resume_task import build_profile_digest, wrap_resume_coach_message

        skill = session.skill_hint or "resume-coach"
        if skill == "resume-coach" and session.profile_id:
            digest = ""
            try:
                profile = await self._profiles.get(session.profile_id, actor=actor)
                digest = build_profile_digest(profile.payload)
            except Exception:  # noqa: BLE001
                digest = ""
            agent_message = wrap_resume_coach_message(
                agent_message,
                profile_id=session.profile_id,
                digest=digest,
            )
        agent_message = f"{reply_language_instruction(reply_locale)}\n\n{agent_message}"

        assistant_parts: list[str] = []
        had_tool_activity = False
        async for event in client.stream_message(
            session.deerflow_thread_id,
            agent_message,
            metadata=metadata,
            attachments=[a.model_dump() for a in attachment_list],
        ):
            yield event
            event_type = event.get("type")
            if event_type == "token":
                assistant_parts.append(_extract_text(event.get("content")))
            elif event_type in _TOOL_ACTIVITY_EVENT_TYPES:
                had_tool_activity = True
            if event_type in _PERSIST_EVENT_TYPES:
                await self._persist_stream_event(session.id, event)
                if event_type in {"tool_start", "confirm"}:
                    log_product_event(
                        f"agent_{event_type}",
                        trace_id=session.trace_id,
                        user_id=actor.user_id,
                        profile_id=session.profile_id,
                        session_id=session.id,
                        name=event.get("name"),
                        confirm_id=event.get("confirm_id"),
                    )
            if event_type == "usage":
                yield build_context_usage_event(
                    prompt_tokens=int(event.get("prompt_tokens") or 0),
                    completion_tokens=int(event.get("completion_tokens") or 0),
                    total_tokens=int(event.get("total_tokens") or 0),
                    limit_tokens=settings.resolved_context_token_limit,
                )

        final_content = _finalize_assistant_content(assistant_parts, had_tool_activity)
        if final_content:
            await self._messages.append(
                message_id=new_id("agm"),
                session_id=session.id,
                role="assistant",
                event_type="message",
                content=final_content,
            )
        await self._db.commit()

    async def cancel_run(self, session_id: str, *, actor: UserActor) -> dict[str, bool]:
        session = await self._require_session(session_id, actor=actor)
        from jobcome.adapters.deerflow_harness_client import request_session_cancel

        cancelled = request_session_cancel(session.id)
        return {"cancelled": cancelled}

    async def confirm_patch(
        self,
        session_id: str,
        *,
        actor: UserActor,
        body: AgentConfirmRequest,
    ) -> AgentConfirmResponse:
        session = await self._require_session(session_id, actor=actor)
        if not body.approved:
            await self._messages.append(
                message_id=new_id("agm"),
                session_id=session.id,
                role="user",
                event_type="confirm_rejected",
                content=None,
                payload={"confirm_id": body.confirm_id},
            )
            await self._db.commit()
            return AgentConfirmResponse(
                status="rejected",
                confirm_id=body.confirm_id,
                profile_id=session.profile_id,
            )

        ctx = McpRunContext(
            db=self._db,
            user_id=actor.user_id,
            profile_id=session.profile_id,
            session_id=session.id,
        )
        result = await profile_patch(
            ctx,
            {},
            apply=False,
            confirm_id=body.confirm_id,
        )
        await self._messages.append(
            message_id=new_id("agm"),
            session_id=session.id,
            role="assistant",
            event_type="confirm_applied",
            content=f"Profile updated to version {result.get('version')}",
            payload=result,
        )
        await self._db.commit()
        return AgentConfirmResponse(
            status="applied",
            confirm_id=body.confirm_id,
            profile_id=result.get("id") or session.profile_id,
            version=result.get("version"),
        )

    async def _require_session(self, session_id: str, *, actor: UserActor) -> AgentSession:
        session = await self._store.get_by_id(session_id)
        if session is None or session.user_id != actor.user_id:
            raise NotFoundError("Agent session not found")
        return session

    async def _persist_stream_event(self, session_id: str, event: dict[str, Any]) -> None:
        event_type = str(event.get("type") or "event")
        payload = {k: v for k, v in event.items() if k not in {"type", "content"}}
        content = event.get("content")
        if content is not None and not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        await self._messages.append(
            message_id=new_id("agm"),
            session_id=session_id,
            role="assistant",
            event_type=event_type,
            content=content if isinstance(content, str) else None,
            payload=payload or None,
        )

    @staticmethod
    def _to_message_record(row: AgentMessage) -> AgentMessageRecord:
        payload: dict[str, Any] | None = None
        if row.payload_json:
            payload = json.loads(row.payload_json)
        return AgentMessageRecord(
            id=row.id,
            session_id=row.session_id,
            role=row.role,
            event_type=row.event_type,
            content=row.content,
            payload=payload,
            created_at=row.created_at,
        )

    @staticmethod
    def _to_response(session: AgentSession) -> AgentSessionResponse:
        return AgentSessionResponse(
            id=session.id,
            deerflow_thread_id=session.deerflow_thread_id,
            skill_hint=session.skill_hint,
            kind=session.kind,
            status=session.status,
            profile_id=session.profile_id,
            created_at=session.created_at,
        )
