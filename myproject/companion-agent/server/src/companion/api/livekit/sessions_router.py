
import asyncio
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from companion.room.resolve import ChatSessionError, resolve_chat_session
from companion.room.livekit_port import LiveKitToken, TokenIssuer
from companion.room.sessions import SessionError, SessionService


def build_router(service: SessionService, current_user, chat_sessions=None):
    """挂到 app 上。fastapi/pydantic 在这里才导入。

    ``chat_sessions``：聊天会话存储。给了就把房间绑到用户与角色唯一的那段历史（语音与文字共用）；
    没给（没有聊天平台的离线装配）则只透传请求里的会话号。
    """
    from typing import Annotated

    from fastapi import APIRouter, Depends, HTTPException
    from pydantic import BaseModel, Field

    from companion.room.livekit_port import MissingCredentials

    class CreateSessionBody(BaseModel):
        """请求体。

        只收 ``character_id``；**user_id 不在这里**——真实部署从 auth 中间件
        解析出的身份里取，收请求体就等于让人自己报身份。
        """

        character_id: str = Field(min_length=1)
        # 要接着聊的聊天会话。不给就用该用户与该角色最近的会话（没有则新建），
        # 所以语音与文字永远是同一段历史。给了必须属于当前用户且角色一致。
        chat_session_id: int | None = Field(default=None, ge=1)

    class SessionResponse(BaseModel):
        session_id: str
        room_name: str
        token: str
        livekit_url: str
        expires_at: str
        identity: str
        chat_session_id: int | None = None

    router = APIRouter(prefix="/v1/voice", tags=["companion"])

    @router.post("/sessions", response_model=SessionResponse)
    async def create_session(
        body: CreateSessionBody,
        user_id: Annotated[str, Depends(current_user)],
    ) -> SessionResponse:
        chat_session_id = body.chat_session_id
        if chat_sessions is not None:
            try:
                chat_session_id = await resolve_chat_session(
                    chat_sessions, user_id=user_id, character_id=body.character_id,
                    chat_session_id=body.chat_session_id)
            except ChatSessionError as exc:
                raise HTTPException(status_code=404, detail={"code": "not_found"}) from exc
        try:
            grant = await service.create(
                user_id=user_id, character_id=body.character_id, chat_session_id=chat_session_id
            )
        except MissingCredentials as exc:
            # 服务端配置问题，不是调用方的错。
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except SessionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return SessionResponse(**grant.to_json(), chat_session_id=chat_session_id)

    return router
