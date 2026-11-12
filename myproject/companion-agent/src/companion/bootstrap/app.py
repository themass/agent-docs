"""FastAPI 应用装配。

fastapi 只在本模块顶层导入——服务端依赖它，测试环境不装它。
需要在不装 fastapi 的环境里用会话逻辑，请直接 import
``companion.server.sessions``（那是纯逻辑，无 fastapi 依赖）。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI

from companion.config import settings
from companion.bootstrap.container import PROJECT_ROOT, create_container
from companion.adapters.roles.files import CharacterSource
from companion.domain.proactive.models import Channel, InitiativePreferences
from companion.app.proactive.router import ChannelRouter
from companion.adapters.delivery.memory import InAppDelivery, InMemorySendLedger
from companion.app.proactive.loop import InitiativeLoop
from companion.app.proactive.scheduler import InitiativeScheduler
from companion.api.http.routers import characters as characters_router
from companion.api.http.routers import control as control_router
from companion.api.http.routers import inbox as inbox_router
from companion.api.http.routers import memory as memory_router
from companion.api.http.routers.characters import CharacterCatalog
from companion.api.http.deps import AllowAllVerifier, CredentialVerifier, build_current_user
from companion.products.roleplay.sessions import InMemorySessionStore, SessionService, SessionStore
from companion.api.livekit.sessions_router import build_router
from companion.adapters.livekit.tokens import TokenMinter
from companion.api.http.routers.turns import TurnService, build_router as build_turn_router
from companion.app.chat.lifecycle import DrainState
from companion.api.http.routers.roles import build_router as build_roles_router
from companion.api.http.routers.uploads import build_router as build_uploads_router
from companion.api.http.routers.actions import build_router as build_actions_router
from companion.api.http.routers.account import build_router as build_account_router
from companion.api.http.routers.avatars import build_router as build_avatars_router
from companion.api.http.routers.compliance import build_router as build_compliance_router
from companion.api.http.routers.memory_v1 import build_router as build_memory_v1_router
from companion.api.http.routers.reminders import build_router as build_reminders_router
from companion.api.http.routers.chat import build_health_router
from companion.adapters.timeline.legacy_adapter import LegacyTimelineAdapter
from companion.app.tools.legacy_actions import LegacyActionsAdapter
from companion.bootstrap.platform import Platform
from companion.app.roles.service import RoleService
from companion.api.http.routers.chat import ChatApi, build_router as build_chat_router
from companion.domain.turn.pipeline import TurnPipeline

logger = logging.getLogger(__name__)

__all__ = ["create_app", "AppState", "INITIATIVE_INTERVAL_SECONDS"]

# 主动性扫描周期。事件提醒有几分钟的提前量，60 秒足够不漏，也不会高频打扰存储。
INITIATIVE_INTERVAL_SECONDS = 60.0


def _room_provisioner_from_settings():
    """有 LiveKit 密钥才真正建房；没有则返回 None，会话层保持原样（离线/测试）。"""
    if not (settings.livekit_api_key and settings.livekit_api_secret and settings.livekit_url):
        return None
    from companion.adapters.livekit.rooms import livekit_room_provisioner

    return livekit_room_provisioner(
        url=settings.livekit_url,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
    )


@dataclass
class AppState:
    """挂在 ``app.state.companion``，供路由与测试取用。"""

    service: SessionService
    store: SessionStore
    verifier: CredentialVerifier
    container: Any = None
    preferences: Any = None
    delivery: Any = None
    loop: Any = None
    drain: Any = None


async def _initiative_worker(loop: InitiativeLoop, interval: float) -> None:
    """定时跑一轮主动性扫描。单轮出错只记日志，不让整个循环停掉。"""
    while True:
        try:
            await loop.run_once()
        except Exception:  # noqa: BLE001 — 后台任务不能因一轮失败而死
            logger.exception("initiative round failed")
        await asyncio.sleep(interval)


def _default_room_store(settings: Any) -> Any:
    """配了 Redis 就用 Redis 版；没配（本地开发/测试）用内存版。"""
    url = getattr(settings, "companion_redis_url", "") or ""
    if url:
        try:
            from redis import asyncio as redis_async

            from companion.adapters.store.redis.sessions import RedisSessionStore

            return RedisSessionStore(redis_async.from_url(url, decode_responses=True))
        except Exception:  # noqa: BLE001 —— Redis 不可用时不能让整个服务起不来
            pass
    from companion.products.roleplay.sessions import InMemorySessionStore

    return InMemorySessionStore()

def create_app(
    *,
    verifier: CredentialVerifier | None = None,
    store: SessionStore | None = None,
    minter: TokenMinter | None = None,
    livekit_url: str | None = None,
    container: Any = None,
    run_initiative: bool = True,
    initiative_interval: float = INITIATIVE_INTERVAL_SECONDS,
    chat: ChatApi | None = None,
    roles: RoleService | None = None,
    platform: Platform | None = None,
) -> FastAPI:
    """装配应用。参数都可注入，方便测试替换实现。

    默认 verifier 是 ``AllowAllVerifier``——**仅开发可用**，生产必须传入
    真正验签的实现（见 ``deps.CredentialVerifier``）。

    ``run_initiative=False`` 时不启动后台扫描：测试里用显式的 ``loop.run_once(now)``
    驱动，避免定时器带来的不确定性。
    """
    from companion.bootstrap.checks import assert_startup_safe

    # 身份验证：生产只能用 Redis 登录态；dev 才允许 allow_all（D §4、A §5.5）
    assert_startup_safe(env=settings.companion_env, auth_verifier=settings.companion_auth_verifier)
    if verifier is None and settings.companion_auth_verifier == "redis_token":
        import redis.asyncio as redis_async

        from companion.adapters.auth.redis_token import RedisTokenVerifier

        verifier = RedisTokenVerifier(redis_async.from_url(settings.auth_redis_url, decode_responses=True))

    # 房间会话：有 Redis 就存 Redis（多副本可见、重启不丢），否则退回进程内。
    resolved_store = store or _default_room_store(settings)
    service = SessionService(
        store=resolved_store,
        minter=minter or TokenMinter.from_settings(settings),
        livekit_url=settings.livekit_url if livekit_url is None else livekit_url,
        provision_room=_room_provisioner_from_settings(),
    )

    # 偏好是用户维度的：路由写、主动性循环读，必须是同一个存储。
    # 有平台（配了 Postgres）就用 SQL：内存版重启后会把用户关掉的主动消息重新打开。
    preferences_store = (
        platform.preferences if platform is not None and platform.preferences is not None
        else control_router.InMemoryPreferencesStore(InitiativePreferences())
    )

    async def preferences_loader(user_id: str) -> InitiativePreferences:
        return await preferences_store.load(user_id)

    resolved = container or create_container()
    # 大脑检查放在容器建好之后：默认容器用的是 FakeBrain，生产必须显式配置真实大脑（A §5.5）
    assert_startup_safe(env=settings.companion_env, auth_verifier=settings.companion_auth_verifier,
                        brain_name=type(resolved.brain).__name__)
    # 同理：内存版重启就丢消息，且多 worker 各自计数会让频控翻倍。
    delivery = platform.delivery if platform is not None and platform.delivery is not None else InAppDelivery()
    ledger = platform.ledger if platform is not None and platform.ledger is not None else InMemorySendLedger()
    initiative_loop = InitiativeLoop(
        scheduler=InitiativeScheduler(
            timeline=resolved.timeline,
            preferences_loader=preferences_loader,
            state_loader=ledger.state_for,
        ),
        conversation=resolved.conversation,
        router=ChannelRouter({Channel.IN_APP: delivery}, recorder=ledger),
        preferences_loader=preferences_loader,
        state_loader=ledger.state_for,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if platform is not None:
            await platform.astart()   # checkpoint 连接池必须在服务的事件循环里打开
        worker: asyncio.Task | None = None
        if run_initiative:
            worker = asyncio.create_task(
                _initiative_worker(initiative_loop, initiative_interval)
            )
        try:
            yield
        finally:
            if worker is not None:
                worker.cancel()
                with suppress(asyncio.CancelledError):
                    await worker
            await app.state.companion.store.aclose()
            if platform is not None:
                await platform.aclose()

    app = FastAPI(title="companion-agent", version="0.1.0", lifespan=lifespan)
    app.state.companion = AppState(
        drain=DrainState(),
        service=service,
        store=resolved_store,
        verifier=verifier or AllowAllVerifier(),
        container=resolved,
        preferences=preferences_store,
        delivery=delivery,
        loop=initiative_loop,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        # 不做依赖检查：进程活着就算健康，下游状态由各自的探针负责。
        return {"status": "ok"}

    current_user = build_current_user(app.state.companion.verifier)
    app.include_router(build_router(service, current_user,
                                    chat_sessions=platform.sessions if platform is not None else None))

    # 回合接口需要主脑与管线；没注入 container 时用离线链路，
    # 这样健康检查与会话接口之外的部分不会因为缺依赖而起不来。
    app.include_router(
        build_turn_router(
            TurnService(
                conversation=resolved.conversation,
                pipeline=TurnPipeline(resolved.brain),
            ),
            current_user,
        )
    )

    if chat is not None:
        app.include_router(build_chat_router(chat, current_user))
    if roles is not None:
        app.include_router(build_roles_router(roles, current_user))
    if platform is not None:
        # 新聊天栈：排空/停机状态与平台共享，探针随之生效（P §3.5）。
        app.state.companion.drain = platform.drain
        app.include_router(build_chat_router(platform.chat, current_user))
        app.include_router(build_roles_router(platform.roles, current_user))
        if platform.uploads is not None:
            app.include_router(build_uploads_router(platform.uploads, current_user))
        if platform.reminders is not None:
            app.include_router(build_reminders_router(platform.reminders, current_user))
        app.include_router(build_actions_router(platform.confirmations, current_user))
        if platform.account is not None:
            app.include_router(build_account_router(platform.account, current_user))
        if platform.compliance is not None:
            app.include_router(build_compliance_router(
                platform.compliance, current_user, sessions=platform.sessions, messages=platform.chat.messages,
                persona=platform.persona, timeline=platform.timeline, reminders=platform.reminders))
        if platform.avatars is not None:
            app.include_router(build_avatars_router(platform.avatars, current_user,
                                                    admin_token=platform.admin_token))
        app.include_router(build_memory_v1_router(memory=platform.memory, timeline=platform.timeline,
                                                  current_user=current_user, persona=platform.persona))
        app.include_router(build_health_router(platform.drain))

    # 客户端依赖的接口：角色目录、记忆与事件、动作确认与偏好、主动消息收件箱。
    catalog = CharacterCatalog(CharacterSource(PROJECT_ROOT / "characters"))
    app.include_router(characters_router.build_router(catalog, current_user))
    app.include_router(
        control_router.build_router(
            actions=control_router.ActionsApi(executor=resolved.executor),
            preferences=control_router.PreferencesApi(store=preferences_store),
            current_user=current_user,
        )
    )
    app.include_router(
        inbox_router.build_router(
            inbox=inbox_router.InboxApi(delivery=delivery),
            current_user=current_user,
        )
    )

    return app
