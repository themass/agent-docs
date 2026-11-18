
import asyncio
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from companion.service.room.resolve import ChatSessionError, resolve_chat_session
from companion.service.room.livekit_port import LiveKitToken, TokenIssuer
from companion.service.room.sessions import SessionError, SessionService


def build_router(service: SessionService, current_user, chat_sessions=None, role_check=None):
    """挂到 app 上。fastapi/pydantic 在这里才导入。

    ``chat_sessions``：聊天会话存储。给了就把房间绑到用户与角色唯一的那段历史（语音与文字共用）；
    没给（没有聊天平台的离线装配）则只透传请求里的会话号。

    ``role_check``：角色存在性校验（异步，role_id/owner_id，返回 bool）。语音建会话会
    **自动创建**聊天会话（resolve_chat_session），未知角色不挡就会建出一段每回合必挂的
    历史——与 /v1/sessions 用同一个判据、同一种拒绝。
    """
    from typing import Annotated

    from fastapi import APIRouter, Depends, HTTPException
    from pydantic import BaseModel, Field

    from companion.service.room.livekit_port import MissingCredentials

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
        # 线路选择随 grant 下发（协议 §2）；provider_config 是 provider 特定参数，livekit 时为空对象。
        provider: str = "livekit"
        provider_config: dict = Field(default_factory=dict)

    router = APIRouter(prefix="/v1/voice", tags=["companion"])

    @router.post("/sessions", response_model=SessionResponse)
    async def create_session(
        body: CreateSessionBody,
        user_id: Annotated[str, Depends(current_user)],
    ) -> SessionResponse:
        # 未知角色先拒（同 /v1/sessions：400 unknown_role）。放在 resolve 之前：
        # 否则自动建会话那一步会先把坏历史落库。user_id 必须数字（owner_id 是 BIGINT），
        # 非数字的用户 id 留给 resolve 按既有语义拒绝。
        if role_check is not None and user_id.isdigit() and not await role_check(
            role_id=body.character_id, owner_id=int(user_id)
        ):
            raise HTTPException(status_code=400, detail={"code": "unknown_role", "role_id": body.character_id})
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
