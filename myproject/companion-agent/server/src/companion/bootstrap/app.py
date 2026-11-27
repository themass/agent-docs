"""FastAPI 应用装配。

fastapi 只在本模块顶层导入——服务端依赖它，测试环境不装它。
需要在不装 fastapi 的环境里用会话逻辑，请直接 import
``companion.server.sessions``（那是纯逻辑，无 fastapi 依赖）。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI

from companion.config import settings
from companion.paths import CHARACTERS_DIR
from companion.service.roles.files import CharacterSource
from companion.api.http.routers import characters as characters_router
from companion.api.http.routers import hers as hers_router
from companion.api.http.routers import control as control_router
from companion.api.http.routers import inbox as inbox_router
from companion.api.http.routers.characters import CharacterCatalog
from companion.api.http.deps import AllowAllVerifier, CredentialVerifier, build_current_user
from companion.service.room.sessions import SessionService, SessionStore
from companion.api.livekit.sessions_router import build_router
from companion.service.room.livekit_tokens import TokenMinter
from companion.service.chat.lifecycle import DrainState
from companion.api.http.routers.roles import build_router as build_roles_router
from companion.api.http.routers.uploads import build_router as build_uploads_router
from companion.api.http.routers.actions import build_router as build_actions_router
from companion.api.http.routers.account import build_router as build_account_router
from companion.api.http.routers.avatars import build_router as build_avatars_router
from companion.api.http.routers.avatar_gen import build_router as build_avatar_gen_router
from companion.api.http.routers.compliance import build_router as build_compliance_router
from companion.api.http.routers.memory_v1 import build_router as build_memory_v1_router
from companion.api.http.routers import memory_index as memory_index_router
from companion.api.http.routers.cards import build_router as build_cards_router
from companion.api.http.routers.reminders import build_router as build_reminders_router
from companion.api.http.routers.chat import build_health_router
from companion.bootstrap.platform import Platform
from companion.bootstrap.models import photosolve_service
from companion.service.photosolve import PhotoSolveService
from companion.api.http.routers.photosolve import build_router as build_photosolve_router
from companion.service.roles.service import RoleService
from companion.api.http.routers.chat import ChatApi, build_router as build_chat_router

logger = logging.getLogger(__name__)

__all__ = ["create_app", "AppState", "INITIATIVE_INTERVAL_SECONDS"]

# 主动性扫描周期。事件提醒有几分钟的提前量，60 秒足够不漏，也不会高频打扰存储。
INITIATIVE_INTERVAL_SECONDS = 60.0   # 后台任务进程（worker_jobs）用


def _room_provisioner_from_settings():
    """有 LiveKit 密钥才真正建房；没有则返回 None，会话层保持原样（离线/测试）。"""
    if not (settings.livekit_api_key and settings.livekit_api_secret and settings.livekit_url):
        return None
    from companion.service.room.livekit_rooms import livekit_room_provisioner

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
    preferences: Any = None
    drain: Any = None
    background: Any = None


def _default_room_store(settings: Any) -> Any:
    """配了 Redis 就用 Redis 版；没配（本地开发/测试）用内存版。"""
    url = getattr(settings, "companion_redis_url", "") or ""
    if url:
        try:
            from companion.bootstrap.redis_client import redis_client_from_url
            from companion.service.room.redis_store import RedisSessionStore

            return RedisSessionStore(redis_client_from_url(url, decode_responses=True))
        except Exception:  # noqa: BLE001 —— Redis 不可用时不能让整个服务起不来
            pass
    from companion.service.room.sessions import InMemorySessionStore

    return InMemorySessionStore()


def _default_script_lease(settings: Any) -> Any:
    """剧本房 lease：有 Redis 走 Redis（多副本共享）；dev 无 Redis 才退回内存。

    非 dev：Redis URL 缺失或初始化失败一律 fail-closed——内存版无跨副本、
    且历史上曾静默 immortal，生产不能悄悄降级。
    """
    from companion.bootstrap.checks import StartupRefused
    from companion.devtools.script_room.lease import InMemoryScriptRoomLease, RedisScriptRoomLease

    env = (getattr(settings, "companion_env", "") or "dev").strip().lower()
    url = getattr(settings, "companion_redis_url", "") or ""
    if url:
        try:
            from companion.bootstrap.redis_client import redis_client_from_url

            return RedisScriptRoomLease(redis_client_from_url(url, decode_responses=True))
        except Exception as exc:  # noqa: BLE001
            if env != "dev":
                raise StartupRefused(
                    f"剧本房 Redis lease 初始化失败（env={env}）：{type(exc).__name__}: {exc}"
                ) from exc
    elif env != "dev":
        raise StartupRefused(
            f"COMPANION_ENV={env} 需要 companion_redis_url 以启用剧本房 Redis lease；"
            f"禁止静默降级到进程内 immortal lease"
        )
    return InMemoryScriptRoomLease()

def create_app(
    *,
    verifier: CredentialVerifier | None = None,
    store: SessionStore | None = None,
    minter: TokenMinter | None = None,
    livekit_url: str | None = None,
    chat: ChatApi | None = None,
    roles: RoleService | None = None,
    platform: Platform | None = None,
    photosolve: PhotoSolveService | None = None,
) -> FastAPI:
    """装配应用。参数都可注入，方便测试替换实现。

    默认 verifier 是 ``AllowAllVerifier``——**仅开发可用**，生产必须传入
    真正验签的实现（见 ``deps.CredentialVerifier``）。

    主动开口的扫描不在这里跑：API 可能有多个进程，每个都扫一遍会重复发；
    它由后台任务进程（``worker_jobs``）单独运行。
    """
    from companion.bootstrap.checks import assert_startup_safe

    # 身份验证：生产只能用 Redis 登录态；dev 才允许 allow_all（D §4、A §5.5）
    assert_startup_safe(env=settings.companion_env, auth_verifier=settings.companion_auth_verifier)
    if verifier is None and settings.companion_auth_verifier == "redis_token":
        from companion.bootstrap.redis_client import redis_client_from_url
        from companion.service.auth.redis_token import RedisTokenVerifier

        verifier = RedisTokenVerifier(redis_client_from_url(settings.auth_redis_url, decode_responses=True))

    # 房间会话：有 Redis 就存 Redis（多副本可见、重启不丢），否则退回进程内。
    resolved_store = store or _default_room_store(settings)
    script_lease = _default_script_lease(settings)
    service = SessionService(
        store=resolved_store,
        minter=minter or TokenMinter.from_settings(settings),
        livekit_url=settings.livekit_url if livekit_url is None else livekit_url,
        provision_room=_room_provisioner_from_settings(),
        provider=settings.companion_rtc_provider,
        script_lease=script_lease,
    )

    if platform is not None:
        # 生产必须是真实大脑：假大脑会静默返回占位回复（A §5.5）
        assert_startup_safe(env=settings.companion_env, auth_verifier=settings.companion_auth_verifier,
                            brain_name=type(platform.brain).__name__ if platform.brain is not None else None)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        background = None
        if platform is not None:
            await platform.astart()   # checkpoint 连接池必须在服务的事件循环里打开
            if settings.companion_jobs_in_api:
                # 后台循环跟 API 一起跑：少一个必须记得部署的进程。多副本时只在一个副本上开。
                from companion.service.jobs.background import BackgroundJobs

                background = BackgroundJobs(platform)
                await background.start()
                app.state.companion.background = background
        try:
            yield
        finally:
            if background is not None:
                await background.stop()     # 先停循环，否则它会在连接关掉之后继续用
            await app.state.companion.store.aclose()
            if platform is not None:
                await platform.aclose()

    app = FastAPI(title="companion-agent", version="0.1.0", lifespan=lifespan)
    app.state.companion = AppState(
        drain=DrainState(),
        service=service,
        store=resolved_store,
        verifier=verifier or AllowAllVerifier(),
        preferences=platform.preferences if platform is not None else None,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        # 不做依赖检查：进程活着就算健康，下游状态由各自的探针负责。
        return {"status": "ok"}

    current_user = build_current_user(app.state.companion.verifier)
    app.include_router(build_photosolve_router(
        photosolve if photosolve is not None else photosolve_service(settings), current_user))
    app.include_router(build_router(service, current_user,
                                    chat_sessions=platform.sessions if platform is not None else None,
                                    # 与 /v1/sessions 同一个角色校验判据（build_platform 挂在 chat 上）：
                                    # 语音建会话会自动创建聊天会话，未知角色同样要先拒。
                                    role_check=platform.chat.role_check if platform is not None else None,
                                    lease=script_lease))

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
            app.include_router(build_uploads_router(platform.uploads, current_user, direct=platform.chat.direct))
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
        if platform.avatar_gen is not None:
            # 「我」的二次元头像生成（Android AvatarGenRemote 的对端）。与上面的
            # avatars（角色形象包目录）是两个特性，各自一个 router。
            app.include_router(build_avatar_gen_router(platform.avatar_gen, current_user))
        app.include_router(build_memory_v1_router(memory=platform.memory, timeline=platform.timeline,
                                                  current_user=current_user, persona=platform.persona,
                                                  profile_doc=platform.profile_doc))
        # P6：角色卡接口与紧凑记忆索引（只读预览）。索引必须排在 memory_v1 之后：
        # 两者共用 /v1/memory 前缀，v1 没有 /index 路由，顺序只影响可读性。
        app.include_router(build_cards_router(platform.cards, current_user))
        app.include_router(memory_index_router.build_router(
            memory=platform.memory, cards=platform.cards, current_user=current_user))
        app.include_router(build_health_router(platform.drain))

    # 角色卡目录（陪伴角色的展示信息）。有平台时用它的读取链（库里的系统包优先、文件兜底）——
    # 目录与角色解析读同一份封装；没有平台时退回文件，这时确实不依赖数据库。
    catalog = CharacterCatalog(
        getattr(platform, "characters", None) or CharacterSource(CHARACTERS_DIR))
    app.include_router(characters_router.build_router(catalog, current_user))

    # her 包目录（persona/her 分层第一刀）：只有平台（数据库）才挂——呈现实体没有
    # 文件兜底，没库时根本没有注册表可查（与 control/inbox 同一取舍）。
    if platform is not None and getattr(platform, "hers", None) is not None:
        app.include_router(hers_router.build_router(
            hers_router.HerCatalog(platform.hers), current_user))

    if platform is not None:
        # 偏好与收件箱读写 Postgres；没有平台时这两组接口不存在，而不是退回进程内存：
        # 内存版重启就丢，用户关掉的主动消息会重新打开。
        app.include_router(control_router.build_router(
            preferences=control_router.PreferencesApi(store=platform.preferences), current_user=current_user))
        app.include_router(inbox_router.build_router(
            inbox=inbox_router.InboxApi(delivery=platform.delivery), current_user=current_user))

    return app
