"""Agent SSE routes."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from agentkit.common.trace import get_trace_id
from agentkit.web.auth import UserActor
from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response, StreamingResponse

from jc.api.deps import get_agent_service, require_user
from jc.api.sse import with_heartbeat
from jc.schemas.agent import (
    AgentConfirmRequest,
    AgentConfirmResponse,
    AgentMessageListResponse,
    AgentMessageRequest,
    AgentSessionCreateRequest,
    AgentSessionListResponse,
    AgentSessionResponse,
)
from jc.services.agent_service import AgentService

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post(
    "/sessions",
    response_model=AgentSessionResponse,
    summary="创建 Agent 会话",
)
async def create_agent_session(
    body: AgentSessionCreateRequest,
    actor: UserActor = Depends(require_user),
    agents: AgentService = Depends(get_agent_service),
) -> AgentSessionResponse:
    return await agents.create_session(
        actor=actor,
        body=body,
        trace_id=get_trace_id() or "trace_local",
    )


@router.get(
    "/sessions",
    response_model=AgentSessionListResponse,
    summary="列出 Agent 会话",
)
async def list_agent_sessions(
    profile_id: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    actor: UserActor = Depends(require_user),
    agents: AgentService = Depends(get_agent_service),
) -> AgentSessionListResponse:
    return await agents.list_sessions(
        actor=actor,
        profile_id=profile_id,
        kind=kind,
        limit=limit,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=AgentSessionResponse,
    summary="获取 Agent 会话",
)
async def get_agent_session(
    session_id: str = Path(description="Agent session id"),
    actor: UserActor = Depends(require_user),
    agents: AgentService = Depends(get_agent_service),
) -> AgentSessionResponse:
    return await agents.get_session(session_id, actor=actor)


@router.get(
    "/sessions/{session_id}/messages",
    response_model=AgentMessageListResponse,
    summary="列出会话消息与事件",
)
async def list_agent_messages(
    session_id: str = Path(description="Agent session id"),
    actor: UserActor = Depends(require_user),
    agents: AgentService = Depends(get_agent_service),
) -> AgentMessageListResponse:
    return await agents.list_messages(session_id, actor=actor)


@router.post(
    "/sessions/{session_id}/confirm",
    response_model=AgentConfirmResponse,
    summary="确认或拒绝档案补丁",
)
async def confirm_agent_patch(
    session_id: str = Path(description="Agent session id"),
    body: AgentConfirmRequest = ...,
    actor: UserActor = Depends(require_user),
    agents: AgentService = Depends(get_agent_service),
) -> AgentConfirmResponse:
    return await agents.confirm_patch(session_id, actor=actor, body=body)


@router.post(
    "/sessions/{session_id}/cancel",
    summary="取消当前 Agent 运行（Steer / 停止）",
)
async def cancel_agent_run(
    session_id: str = Path(description="Agent session id"),
    actor: UserActor = Depends(require_user),
    agents: AgentService = Depends(get_agent_service),
) -> dict[str, bool]:
    return await agents.cancel_run(session_id, actor=actor)


@router.post(
    "/sessions/{session_id}/messages",
    summary="发送消息（SSE 流）",
)
async def agent_message_stream(
    session_id: str = Path(description="Agent session id"),
    body: AgentMessageRequest = ...,
    actor: UserActor = Depends(require_user),
    agents: AgentService = Depends(get_agent_service),
) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[bytes]:
        upstream = agents.stream_message(
            session_id,
            actor=actor,
            content=body.content,
            attachments=body.attachments,
            reply_locale=body.reply_locale,
            ui_context=body.ui_context,
        )
        async for event in with_heartbeat(upstream):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/sessions/{session_id}/messages/{message_id}/images/{attachment_index}",
    summary="读取当前用户会话图片用于前端头像裁剪",
)
async def read_agent_image(
    session_id: str,
    message_id: str,
    attachment_index: int = Path(ge=0),
    actor: UserActor = Depends(require_user),
    agents: AgentService = Depends(get_agent_service),
) -> Response:
    return await agents.read_photo_source(
        session_id, message_id=message_id, attachment_index=attachment_index, actor=actor,
    )
