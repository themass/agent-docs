from __future__ import annotations

import asyncio
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from companion.service.room.livekit_port import LiveKitToken, TokenIssuer


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
    # 新服务的会话 id（chat_session.id）。语音和文字共用同一段对话：agent 用它读写同一个线程与记忆。
    chat_session_id: int | None = None


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


PROVIDER_LIVEKIT = "livekit"
PROVIDER_VOLCENGINE = "volcengine"
SUPPORTED_PROVIDERS = (PROVIDER_LIVEKIT, PROVIDER_VOLCENGINE)


@dataclass(frozen=True, slots=True)
class SessionGrant:
    """一次会话创建的结果，即 /companion/sessions 的响应体。

    ``provider`` 是线路选择的唯一出口（协议 §2）：建会话时定，客户端只照着分发。
    ``provider_config`` 放 provider 特定参数；livekit 时为空 dict——livekit 的连接
    参数（livekit_url/token）沿用顶层字段，旧客户端因此完全无感。
    """

    session_id: str
    room_name: str
    token: str
    livekit_url: str
    expires_at: datetime
    identity: str
    provider: str = PROVIDER_LIVEKIT
    provider_config: dict[str, object] = field(default_factory=dict)

    def to_json(self) -> dict[str, object]:
        # 时间统一用 ISO-8601 UTC（带 Z），客户端不必猜时区。
        return {
            "session_id": self.session_id,
            "room_name": self.room_name,
            "token": self.token,
            "livekit_url": self.livekit_url,
            "expires_at": self.expires_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "identity": self.identity,
            # 新增字段：老客户端解析时直接忽略，不影响既有字段。
            "provider": self.provider,
            "provider_config": self.provider_config,
        }


RoomProvisioner = Callable[[str, dict[str, str]], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class SessionService:
    store: SessionStore
    minter: TokenIssuer
    livekit_url: str
    provision_room: RoomProvisioner | None = None
    provider: str = PROVIDER_LIVEKIT

    async def create(
        self, *, user_id: str, character_id: str, now: float | None = None,
        chat_session_id: int | None = None,
    ) -> SessionGrant:
        """``user_id`` 必须来自已验证的凭据，不能取自请求体。

        ``character_id`` 暂时只记录，不进入 token：角色决定主脑行为，与入场无关；
        等 agent 侧按会话查角色时再补进 room metadata。
        """
        if not user_id:
            raise SessionError("user_id 不能为空")
        if not character_id:
            raise SessionError("character_id 不能为空")
        provider = self._resolve_provider()
        # 线路凭据按 provider 校验：livekit 线路要 LIVEKIT_URL（火山线路的实现落地后换成它的校验）。
        if provider == PROVIDER_LIVEKIT and not self.livekit_url:
            raise SessionError("LIVEKIT_URL 未配置")

        issued_at = time.time() if now is None else now
        session_id = new_session_id()
        room = room_name_for(session_id)
        if self.provision_room is not None:
            # 先建房再发 token：房间 metadata 必须在 agent 入场前就位，否则它会拒绝入场。
            try:
                # chat_session_id 让 agent 知道这是同一段对话；没有时（旧客户端）退回旧行为。
                metadata: dict[str, object] = {"user_id": user_id, "character_id": character_id}
                if chat_session_id is not None:
                    metadata["chat_session_id"] = chat_session_id
                await self.provision_room(room, metadata)
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
                chat_session_id=chat_session_id,
            )
        )
        return SessionGrant(
            session_id=session_id,
            room_name=room,
            token=minted.token,
            livekit_url=self.livekit_url,
            expires_at=minted.expires_at,
            identity=minted.identity,
            provider=provider,
            # livekit 的连接参数就是顶层 livekit_url + token，所以 provider_config 为空；
            # 火山线路落地时在这里组装 app_id/room_id/token/turn_url（协议 §2 草案）。
            provider_config={},
        )

    def _resolve_provider(self) -> str:
        """线路选择在唯一一处：值来自配置，以后可换成按用户/地域/健康探测的策略函数。

        认不出来的配置值**报错不降级**：降级按 livekit 是客户端的事（那里旧实现可能
        就是唯一可用实现）；服务端这里没有任何实现能替火山兜底，静默换线等于配置错误
        被吞掉，必须让建会话显式失败。
        """
        provider = (self.provider or "").strip().lower() or PROVIDER_LIVEKIT
        if provider not in SUPPORTED_PROVIDERS:
            raise SessionError(f"不支持的语音线路：{provider}（可用：{', '.join(SUPPORTED_PROVIDERS)}）")
        if provider != PROVIDER_LIVEKIT:
            # 值合法但服务端实现尚未接入（P1）：此时下发 grant 会让客户端拿到
            # 它多半也解不开的凭据，不如在这里就失败。
            raise SessionError(f"语音线路 {provider} 的服务端实现尚未接入，请勿配置 companion_voice_provider={provider}")
        return provider
