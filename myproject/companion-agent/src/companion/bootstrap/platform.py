"""新聊天栈的装配（A §5.1–5.2、O §8）：真实存储、控制面、工具、确认、上传与角色。

与 ``container.create_container`` 并列：旧容器仍服务旧的 /companion 路由，这里组装的是
``/api/agent/v1`` 的全套接口。只在组合根（入口进程）里调用。

已知的临时实现（见 T13 报告）：记忆与时间线目前是进程内实现（重启即丢）；
回合里的工具调用还没有接入大脑的图（工具只注册、确认与执行链路可用）。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from companion.adapters.roles.catalog_files import load_system_catalog
from companion.adapters.storage.images import normalize_image
from companion.adapters.storage.tos import TosObjectStore
from companion.api.http.routers.chat import ChatApi
from companion.adapters.cache.redis.control import RedisTurnControl
from companion.adapters.store.mysql.repositories import (
    MysqlConfirmationStore,
    MysqlMessageStore,
    MysqlQueueStore,
    MysqlRoleStore,
    MysqlSessionStore,
    MysqlToolCallStore,
    MysqlUploadStore,
)
from companion.adapters.timeline.memory import InMemoryTimeline
from companion.adapters.store.mysql.memory import MysqlMemoryPort
from companion.app.chat.lifecycle import DrainState
from companion.app.roles.service import RoleService
from companion.app.tools.builtin import register_builtin_tools
from companion.app.tools.confirmation import ConfirmationService
from companion.app.tools.runtime import ToolRuntime
from companion.app.uploads.service import UploadService
from companion.bootstrap.chat_stack import build_chat_api
from companion.config import PROJECT_ROOT, Settings
from companion.domain.tools.registry import ToolRegistry
from companion.domain.roles.catalog import USER_ROLE_PREFIX
from companion.ports.brain import TextDelta, TurnRequest
from memory_hub import AppConfig, MemoryHub
from memory_hub.hub import ScopedMemory

BUILTIN_PERSONA_IDS = frozenset({"linche", "sudai"})


@dataclass
class Platform:
    chat: ChatApi
    roles: RoleService
    uploads: UploadService
    confirmations: ConfirmationService
    memory: ScopedMemory
    timeline: Any
    drain: DrainState
    engine: Any
    redis: Any

    async def aclose(self) -> None:
        await self.redis.aclose()
        await self.engine.dispose()


def build_platform(settings: Settings, *, brain: Any, prompts: Any, memory_port: Any = None) -> Platform:
    """组装。缺少 MySQL 或 Redis 配置时直接失败（fail-closed），不退回内存实现。"""
    if not settings.companion_mysql_url or not settings.companion_redis_url:
        raise RuntimeError("COMPANION_MYSQL_URL and COMPANION_REDIS_URL are required for the chat platform")

    from redis import asyncio as redis_async
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(settings.companion_mysql_url, pool_pre_ping=True)
    redis = redis_async.from_url(settings.companion_redis_url, decode_responses=False)

    sessions = MysqlSessionStore(engine)
    messages = MysqlMessageStore(engine)
    queue = MysqlQueueStore(engine)
    roles_store = MysqlRoleStore(engine)
    confirmations_store = MysqlConfirmationStore(engine)
    tool_calls = MysqlToolCallStore(engine)
    uploads_store = MysqlUploadStore(engine)
    control = RedisTurnControl(redis)

    catalog = load_system_catalog(PROJECT_ROOT / "roles" / "catalog", reserved_ids=BUILTIN_PERSONA_IDS)
    roles = RoleService(catalog, roles_store)

    timeline = InMemoryTimeline()
    # 记忆：默认持久化到 MySQL（ca_memory_item）。传入的 memory_port 仅用于测试替换。
    backend = memory_port if memory_port is not None else MysqlMemoryPort(engine)
    hub = MemoryHub.from_config(
        [AppConfig("companion", "ca_memory_companion", "COMPANION_QDRANT_TOKEN")],
        lambda cfg: backend,
    )
    memory = hub.for_app("companion")

    registry = ToolRegistry()
    register_builtin_tools(registry, memory=memory, timeline=timeline)
    runtime = ToolRuntime(registry=registry, confirmations=confirmations_store, audit=tool_calls)
    confirmations = ConfirmationService(store=confirmations_store, messages=messages, runtime=runtime)

    async def system_prompt_for(role_id: str, owner_id: int) -> str:
        if role_id.startswith(USER_ROLE_PREFIX):
            record = await roles_store.get_owned(owner_id=owner_id, public_id=role_id)
            return record.prompt if record else ""
        system = catalog.get(role_id)
        if system is not None:
            return system.prompt
        return prompts.build(role_id)

    async def produce(request: TurnRequest, inbox: Any) -> AsyncIterator[Any]:
        owner_id = int(request.user_id)
        system_prompt = await system_prompt_for(request.character_id, owner_id)
        turn = await brain.start_turn(TurnRequest(
            user_id=request.user_id, character_id=request.character_id,
            message=request.message, system_prompt=system_prompt))
        async for chunk in turn.tokens:
            yield TextDelta(chunk)

    drain = DrainState()
    api, _close = build_chat_api(
        sessions=sessions, messages=messages, queue=queue, control=control,
        produce=produce, drain=drain, process_name=None,
    )
    uploads = UploadService(
        objects=TosObjectStore(endpoint=settings.tos_endpoint, bucket=settings.tos_bucket,
                               access_key=settings.tos_access_key, secret_key=settings.tos_secret_key,
                               region=settings.tos_region),
        records=uploads_store, normalize=normalize_image, key_prefix=settings.tos_key_prefix)

    return Platform(chat=api, roles=roles, uploads=uploads, confirmations=confirmations,
                    memory=memory, timeline=timeline, drain=drain, engine=engine, redis=redis)
