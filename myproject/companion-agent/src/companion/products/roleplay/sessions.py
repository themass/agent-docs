from __future__ import annotations

import asyncio
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from companion.ports.livekit import LiveKitToken, TokenIssuer


ROOM_PREFIX = "companion-"


def room_name_for(session_id: str) -> str:
    """房间名与会话一对一：同一用户连开两次不会撞进同一房间。"""
    return f"{ROOM_PREFIX}{session_id}"


def new_session_id() -> str:
    return secrets.token_urlsafe(16)


class SessionError(Exception):
    """会话无法创建。"""


@dataclass(frozen=True, slots=True)
class SessionRecord:
    session_id: str
    user_id: str
    character_id: str
    room_name: str
    identity: str
    created_at: datetime
    expires_at: datetime


class SessionStore(Protocol):
    """会话持久化。

    现在只有内存实现；换成 Redis 时只改注入的实例，调用方不动。
    """

    async def save(self, record: SessionRecord) -> None: ...

    async def get(self, session_id: str) -> SessionRecord | None: ...

    async def list_for_user(self, user_id: str) -> list[SessionRecord]: ...

    async def aclose(self) -> None: ...


@dataclass
class InMemorySessionStore:
    """dict + 单把锁。

    进程内有效，重启即丢；单实例开发够用，多副本部署必须换共享存储。
    """

    _items: dict[str, SessionRecord] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def save(self, record: SessionRecord) -> None:
        async with self._lock:
            self._items[record.session_id] = record

    async def get(self, session_id: str) -> SessionRecord | None:
        async with self._lock:
            return self._items.get(session_id)

    async def list_for_user(self, user_id: str) -> list[SessionRecord]:
        async with self._lock:
            return [r for r in self._items.values() if r.user_id == user_id]

    async def aclose(self) -> None:
        return None


@dataclass(frozen=True, slots=True)
class SessionGrant:
    """一次会话创建的结果，即 /companion/sessions 的响应体。"""

    session_id: str
    room_name: str
    token: str
    livekit_url: str
    expires_at: datetime
    identity: str

    def to_json(self) -> dict[str, str]:
        # 时间统一用 ISO-8601 UTC（带 Z），客户端不必猜时区。
        return {
            "session_id": self.session_id,
            "room_name": self.room_name,
            "token": self.token,
            "livekit_url": self.livekit_url,
            "expires_at": self.expires_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "identity": self.identity,
        }


RoomProvisioner = Callable[[str, dict[str, str]], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class SessionService:
    store: SessionStore
    minter: TokenIssuer
    livekit_url: str
    provision_room: RoomProvisioner | None = None

    async def create(
        self, *, user_id: str, character_id: str, now: float | None = None
    ) -> SessionGrant:
        """``user_id`` 必须来自已验证的凭据，不能取自请求体。

        ``character_id`` 暂时只记录，不进入 token：角色决定主脑行为，与入场无关；
        等 agent 侧按会话查角色时再补进 room metadata。
        """
        if not user_id:
            raise SessionError("user_id 不能为空")
        if not character_id:
            raise SessionError("character_id 不能为空")
        if not self.livekit_url:
            raise SessionError("LIVEKIT_URL 未配置")

        issued_at = time.time() if now is None else now
        session_id = new_session_id()
        room = room_name_for(session_id)
        if self.provision_room is not None:
            # 先建房再发 token：房间 metadata 必须在 agent 入场前就位，否则它会拒绝入场。
            try:
                await self.provision_room(
                    room, {"user_id": user_id, "character_id": character_id}
                )
            except Exception as exc:  # noqa: BLE001 — 任何建房失败都是会话失败
                raise SessionError(f"无法创建房间：{exc}") from exc
        minted: LiveKitToken = self.minter.user_token(user_id, room, now=issued_at)

        await self.store.save(
            SessionRecord(
                session_id=session_id,
                user_id=user_id,
                character_id=character_id,
                room_name=room,
                identity=minted.identity,
                created_at=datetime.fromtimestamp(issued_at, UTC),
                expires_at=minted.expires_at,
            )
        )
        return SessionGrant(
            session_id=session_id,
            room_name=room,
            token=minted.token,
            livekit_url=self.livekit_url,
            expires_at=minted.expires_at,
            identity=minted.identity,
        )
