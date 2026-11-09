from __future__ import annotations

import asyncio
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from companion.ports.livekit import LiveKitToken, TokenIssuer


def build_router(service: SessionService, current_user):
    """挂到 app 上。fastapi/pydantic 在这里才导入。"""
    from typing import Annotated

    from fastapi import APIRouter, Depends, HTTPException
    from pydantic import BaseModel, Field

    from companion.ports.livekit import MissingCredentials

    class CreateSessionBody(BaseModel):
        """请求体。

        只收 ``character_id``；**user_id 不在这里**——真实部署从 auth 中间件
        解析出的身份里取，收请求体就等于让人自己报身份。
        """

        character_id: str = Field(min_length=1)

    class SessionResponse(BaseModel):
        session_id: str
        room_name: str
        token: str
        livekit_url: str
        expires_at: str
        identity: str

    router = APIRouter(prefix="/companion", tags=["companion"])

    @router.post("/sessions", response_model=SessionResponse)
    async def create_session(
        body: CreateSessionBody,
        user_id: Annotated[str, Depends(current_user)],
    ) -> SessionResponse:
        try:
            grant = await service.create(
                user_id=user_id, character_id=body.character_id
            )
        except MissingCredentials as exc:
            # 服务端配置问题，不是调用方的错。
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except SessionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return SessionResponse(**grant.to_json())

    return router
