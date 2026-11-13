"""新聊天栈的装配（A §5.1–5.2、O §8；chat-agent-next-plan.md §2）。只在组合根（入口进程）里调用。

组成：
- 存储：Postgres（兼容 MySQL）上的会话、消息、队列、确认、任务、提醒、记忆；Redis 做控制面。
- 大脑：DeerFlow 图 + Postgres checkpoint（对话线程 = 会话）；没有 checkpoint 时无状态。
- 每回合：上下文组装（角色、世界书、记忆）→ 大脑 → 回合层；收尾时补记中断回复、入队记忆写入。
- 历史操作：编辑、删除、重新生成同时改消息表与对话线程。
- 主动消息：提醒到点后由 worker 进程提交主动回合（同一套装配，见 worker_jobs.py）。

``build_platform`` 是同步的；连接池等需要事件循环的资源在 ``Platform.astart()`` 里打开，
由 FastAPI 的 lifespan 或 worker 的 main 调用。
"""

from __future__ import annotations

import logging
import os
import socket
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from companion.turn.redis_control import RedisTurnControl
from companion.memory.recallers import MemoryPortRecaller, TimelineRecaller
from companion.adapters.push.log import LogPush
from companion.roles.catalog_files import load_system_catalog
from companion.adapters.storage.images import normalize_image
from companion.adapters.store.sql.account import SqlAccountStore
from companion.avatar.sql import SqlAvatarReleaseStore
from companion.adapters.store.sql.jobs import SqlJobStore
from companion.persona.sql import SqlPersonaStore
from companion.adapters.store.sql.proactive_store import (
    SqlDelivery, SqlPreferencesStore, SqlSendLedger,
)
from companion.timeline.sql import SqlTimelineStore
from companion.memory.sql import SqlMemoryPort
from companion.adapters.store.sql.reminders import SqlReminderStore
from companion.adapters.store.sql.repositories import (
    SqlConfirmationStore,
    SqlMessageStore,
    SqlQueueStore,
    SqlRoleStore,
    SqlSessionStore,
    SqlToolCallStore,
    SqlUploadStore,
)
from companion.api.http.routers.chat import ChatApi
from companion.adapters.store.sql.compliance import SqlComplianceStore
from companion.app.account.purge import AccountPurgeService
from companion.app.compliance.service import ComplianceService
from companion.avatar.catalog import AvatarCatalog
from companion.chat.assembler import PromptAssembler, skill_ids_of
from companion.chat.context import ContextBuilder
from companion.chat.history import HistoryService
from companion.chat.lifecycle import DrainState
from companion.chat.resummarize import ResummarizeService
from companion.chat.turn_runner import TurnOutcome
from companion.memory.extraction import MemoryExtractor
from companion.memory.recorder import ExtractionRecorder
from companion.persona.updater import PERSONA_JOB, PersonaUpdater
from companion.timeline.recorder import TimelineRecorder
from companion.app.proactive.reminders import ReminderDispatcher, ReminderService, SessionGone
from companion.roles.resolver import RoleProfileResolver
from companion.roles.service import RoleService
from companion.app.tools.builtin import register_builtin_tools
from companion.app.tools.confirmation import ConfirmationService
from companion.app.tools.runtime import ToolRuntime
from companion.app.uploads.service import UploadService
from companion.bootstrap.chat_stack import build_chat_api
from companion.brain.llm_trace import LlmCallCollector
from companion.app.trace.writer import BackgroundWriter
from companion.config import Settings
from companion.paths import CHARACTERS_DIR, ROLES_CATALOG_DIR, SKILLS_PUBLIC_DIR
from companion.domain.prompt.templates import PROMPT_VERSION
from companion.history.summary import TIMELINE_RECORD_JOB
from companion.memory.pipeline import MemoryPipeline
from companion.domain.tools.registry import ToolRegistry
from companion.brain.port import TextDelta, TurnRequest
from memory_hub import AppConfig, MemoryHub
from memory_hub.hub import ScopedMemory

log = logging.getLogger("companion.platform")

BUILTIN_PERSONA_IDS = frozenset({"linche", "sudai"})
MEMORY_RECORD_JOB = "memory.record"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class Platform:
    chat: ChatApi
    roles: RoleService
    uploads: UploadService | None
    confirmations: ConfirmationService
    memory: ScopedMemory
    timeline: Any
    drain: DrainState
    engine: Any
    redis: Any
    reminders: ReminderService | None = None
    history: HistoryService | None = None
    dispatcher: ReminderDispatcher | None = None
    resummarize: ResummarizeService | None = None
    pipeline: MemoryPipeline | None = None
    jobs: SqlJobStore | None = None
    timeline_recorder: TimelineRecorder | None = None
    persona_updater: PersonaUpdater | None = None
    persona: Any = None
    compliance: ComplianceService | None = None
    account: AccountPurgeService | None = None
    avatars: AvatarCatalog | None = None
    admin_token: str = ""
    sessions: Any = None
    brain: Any = None
    qa: Any = None
    objects: Any = None
    qa_retention_days: int = 90
    tos_key_prefix: str = ""
    trace_writer: Any = None
    qa_enabled: bool = True
    # 主动消息的三块持久化（原来是进程内，重启即丢）
    preferences: Any = None
    delivery: Any = None
    ledger: Any = None
    _pool: Any = None
    _checkpointer: Any = None
    _started: bool = field(default=False, repr=False)

    async def astart(self) -> None:
        """打开需要事件循环的资源：checkpoint 连接池，并建表（幂等）。"""
        if self._started:
            return
        if self._pool is not None:
            await self._pool.open()
            await self._checkpointer.setup()
        self._started = True

    async def aclose(self) -> None:
        # 旁路写入器要先排空：它的 worker 用的就是下面要关掉的数据库连接
        if self.trace_writer is not None:
            await self.trace_writer.close()
        if self._pool is not None:
            await self._pool.close()
        await self.redis.aclose()
        await self.engine.dispose()


def _checkpointer(url: str, profile: Any, tag: str = "") -> tuple[Any, Any]:
    """LangGraph 的 Postgres checkpoint。连接池先不打开（open=False），在 astart 里打开。"""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    from companion.bootstrap.database import make_checkpoint_pool

    pool = make_checkpoint_pool(url, profile, process_tag=tag)
    return pool, AsyncPostgresSaver(pool)


def _build_brain(settings: Settings, *, registry: ToolRegistry, runtime: ToolRuntime, checkpointer: Any,
                 product: str = "chat") -> tuple[Any, Any, Any]:
    """真实大脑：路由表里的 companion_chat 模型 + DeerFlow 图。返回 (brain, graph, llm_call)。"""
    from companion.brain.deerflow import DeerFlowBrain, build_summarization, build_turn_graph
    from companion.brain.tools import to_langchain_tools
    from companion.adapters.llm.router import LLMRouter
    from companion.bootstrap.models import brain_models, chat_model, scenario_call

    router = LLMRouter(settings.companion_llm_routing_path)
    model, fallbacks = brain_models(router, "companion_chat")
    summarization = None
    if checkpointer is not None and "session_summarize" in router.scenarios:
        summarization = build_summarization(
            chat_model(router.chain("session_summarize")[0], streaming=False),
            trigger_tokens=settings.companion_summary_trigger_tokens,
            keep_messages=settings.companion_summary_keep_messages)
    specs = registry.for_product(product)
    graph = build_turn_graph(model, tools=to_langchain_tools(specs), checkpointer=checkpointer,
                             summarization=summarization, fallback_models=fallbacks)
    brain = DeerFlowBrain(graph, tool_runtime=runtime, tool_allowed=frozenset(s.name for s in specs),
                          tool_product=product, stateful=checkpointer is not None)
    llm = scenario_call(router, "memory_extract") if "memory_extract" in router.scenarios else None
    return brain, graph, llm


def default_prompts() -> PromptAssembler:
    """入口进程用的角色卡与 skill 来源（仓库里的 characters/ 与 skills/public/）。"""
    from companion.roles.files import CharacterSource
    from companion.adapters.skills.library import SkillLibrary

    return PromptAssembler(characters=CharacterSource(CHARACTERS_DIR),
                           skills=SkillLibrary(SKILLS_PUBLIC_DIR))


def build_platform(settings: Settings, *, brain: Any = None, prompts: Any = None, memory_port: Any = None,
                   llm: Any = None, push: Any = None, profile: str = "api") -> Platform:
    """组装。缺少数据库或 Redis 配置时直接失败（fail-closed），不退回内存实现。

    ``brain`` 为空时按配置构造 DeerFlow 大脑（需要网关配置）；测试可以传入假大脑。
    ``prompts`` 是 PromptAssembler（陪伴角色卡与 skill），为空时只支持目录角色与用户自建角色；
    入口进程用 ``default_prompts()``。
    ``profile``：进程角色（api / jobs / voice），决定数据库连接池大小，见 ``bootstrap/database.py``。
    """
    if not settings.database_url or not settings.companion_redis_url:
        raise RuntimeError("COMPANION_DATABASE_URL (or COMPANION_MYSQL_URL) and COMPANION_REDIS_URL are required")

    from redis import asyncio as redis_async
    from companion.bootstrap.database import make_engine, profile_for

    pool_profile = profile_for(profile)
    engine = make_engine(settings.database_url, pool_profile)
    redis = redis_async.from_url(settings.companion_redis_url, decode_responses=False)

    from companion.adapters.store.sql.qa import SqlQaStore

    qa = SqlQaStore(engine)
    sessions = SqlSessionStore(engine)
    messages = SqlMessageStore(engine)
    queue = SqlQueueStore(engine)
    roles_store = SqlRoleStore(engine)
    confirmations_store = SqlConfirmationStore(engine)
    tool_calls = SqlToolCallStore(engine)
    uploads_store = SqlUploadStore(engine)
    jobs = SqlJobStore(engine)
    reminder_store = SqlReminderStore(engine)
    control = RedisTurnControl(redis)

    catalog = load_system_catalog(ROLES_CATALOG_DIR, reserved_ids=BUILTIN_PERSONA_IDS)
    roles = RoleService(catalog, roles_store)

    timeline = SqlTimelineStore(engine)
    backend = memory_port if memory_port is not None else SqlMemoryPort(engine)
    hub = MemoryHub.from_config([AppConfig("companion")], lambda cfg: backend)
    memory = hub.for_app("companion")

    reminders = ReminderService(store=reminder_store, sessions=sessions)
    registry = ToolRegistry()
    register_builtin_tools(registry, memory=memory, timeline=timeline, reminders=reminders)
    runtime = ToolRuntime(registry=registry, confirmations=confirmations_store, audit=tool_calls)
    confirmations = ConfirmationService(store=confirmations_store, messages=messages, runtime=runtime)

    pool = checkpointer = graph = None
    if brain is None:
        if settings.checkpoint_url:
            pool, checkpointer = _checkpointer(settings.checkpoint_url, pool_profile)
        brain, graph, built_llm = _build_brain(settings, registry=registry, runtime=runtime,
                                               checkpointer=checkpointer)
        llm = llm or built_llm

    conversation = None
    if graph is not None and checkpointer is not None:
        from companion.brain.conversation_state import DeerFlowConversationState

        conversation = DeerFlowConversationState(graph)

    recorders = [ExtractionRecorder(MemoryExtractor(memory, llm))] if llm is not None else []
    pipeline = MemoryPipeline(recallers=[MemoryPortRecaller(memory), TimelineRecaller(timeline)],
                              recorders=recorders)
    # prompts：PromptAssembler（角色卡来源 + skill 目录），陪伴角色卡与它声明的 skill 都从这里来。
    resolver = RoleProfileResolver(catalog=catalog, user_roles=roles_store,
                                   characters=getattr(prompts, "characters", None),
                                   skills=getattr(prompts, "skills", None), skill_ids_of=skill_ids_of)
    compliance = ComplianceService(store=SqlComplianceStore(engine))
    persona = SqlPersonaStore(engine)
    persona_updater = PersonaUpdater(store=persona, memory=memory, messages=messages, llm=llm) if llm is not None else None
    context = ContextBuilder(roles=resolver, messages=messages, sessions=sessions, memory=pipeline, persona=persona)
    history = HistoryService(messages=messages, control=control, conversation=conversation, jobs=jobs,
                             timeline=timeline)
    resummarize = (ResummarizeService(messages=messages, conversation=conversation, control=control, llm=llm)
                   if conversation is not None and llm is not None else None)

    trace_writer = BackgroundWriter()
    qa_enabled = settings.companion_qa_enabled

    def record_trace(collector: LlmCallCollector, request: TurnRequest, *, owner_id: int, role_id: str,
                     started_at: datetime) -> None:
        """回合收尾时登记这一回合的追踪。**这里只把任务放进队列**，同意判断和写库都在后台：
        记录是旁路，不能让回复多等一次数据库往返，也不能让会话锁多占。"""
        calls = collector.drain()
        if not calls:
            return
        turn_id = str(request.metadata.get("turn_id") or "")
        session_id = request.session_id or 0
        plan = request.prompt
        prompt_version = getattr(plan, "version", "") or PROMPT_VERSION
        skills = tuple(getattr(plan, "skills", ()) or ())

        async def job() -> None:
            # 同意在写入时读：比回合稍晚几秒，用户在这几秒内改了设置按最新的算（撤回同意立即生效）
            keep = await compliance.qa_content_allowed(owner_id=owner_id)
            steps = await qa.record_trace(turn_id=turn_id, session_id=session_id, owner_id=owner_id,
                                          role_id=role_id, calls=calls, keep_content=keep)
            await qa.note_turn_models(turn_id=turn_id, session_id=session_id, owner_id=owner_id, role_id=role_id,
                                      prompt_version=prompt_version, skills=skills, steps=steps, started_at=started_at)

        trace_writer.submit(job)

    async def produce(request: TurnRequest, inbox: Any) -> AsyncIterator[Any]:
        owner_id = int(request.user_id)
        texts = tuple(i.text for i in request.inputs) or (request.message,)
        plan = await context.build(owner_id=owner_id, session_id=request.session_id or 0,
                                   role_id=request.character_id, current_texts=texts)
        request.prompt = plan
        request.system_prompt = plan.system
        if hasattr(brain, "run"):
            collector = LlmCallCollector() if qa_enabled else None
            if collector is not None:
                request.metadata["llm_collector"] = collector
            started_at = datetime.now(UTC)
            try:
                async for event in brain.run(request, inbox):
                    yield event
            finally:
                if collector is not None:
                    record_trace(collector, request, owner_id=owner_id, role_id=request.character_id,
                                 started_at=started_at)
            return
        turn = await brain.start_turn(request)   # 测试用的假大脑只实现了 start_turn
        async for chunk in turn.tokens:
            yield TextDelta(chunk)

    timeline_recorder = TimelineRecorder(timeline, llm) if llm is not None else None

    async def after_turn(outcome: TurnOutcome) -> None:
        # 回合最终状态写进 ca_chat_turn：同样只入队，不占会话锁。总开关关了就不写。
        if qa_enabled:
            state = "lost" if outcome.lock_lost else "failed" if outcome.failed else \
                "cancelled" if outcome.cancelled else "done"
            trace_writer.submit(lambda: qa.finish_turn(
                turn_id=outcome.turn_id, session_id=outcome.session_id, owner_id=outcome.owner_id,
                role_id=outcome.character_id, state=state, error_code="turn_failed" if outcome.failed else ""))
        # 拿着会话锁：补记中断的回复，让模型知道上一句说到哪里。
        if outcome.interrupted and outcome.assistant_message_id and outcome.assistant_text and not outcome.lock_lost:
            await history.note_interrupted(session_id=outcome.session_id,
                                           assistant_message_id=outcome.assistant_message_id,
                                           text=outcome.assistant_text)
        # 记忆写入放到后台任务：回合不等它。
        if recorders and not outcome.failed and outcome.user_text.strip():
            await jobs.enqueue(kind=MEMORY_RECORD_JOB, payload={
                "owner_id": outcome.owner_id, "session_id": outcome.session_id, "role_id": outcome.character_id,
                "turn_id": outcome.turn_id, "user_text": outcome.user_text,
                "assistant_text": outcome.assistant_text}, run_after=_utcnow(),
                dedupe_key=f"{MEMORY_RECORD_JOB}:{outcome.turn_id}")
        # 画像：累计用户发言字数，够一批才入队（对话路径只记数，不抽取、不等模型）。
        if persona_updater is not None and not outcome.failed and outcome.user_text.strip() and outcome.user_message_ids:
            await persona_updater.note_turn(
                owner_id=outcome.owner_id, role_id=outcome.character_id, last_message_id=max(outcome.user_message_ids),
                user_text=outcome.user_text, jobs=jobs, session_id=outcome.session_id)
        # 事件的来源是这一回合的第一条用户消息（重新生成、合并时也指向它）。
        if timeline_recorder is not None and not outcome.failed and outcome.user_message_ids:
            await jobs.enqueue(kind=TIMELINE_RECORD_JOB, payload={
                "owner_id": outcome.owner_id, "session_id": outcome.session_id, "role_id": outcome.character_id,
                "user_message_id": outcome.user_message_ids[0], "turn_id": outcome.turn_id,
                "user_text": outcome.user_text, "assistant_text": outcome.assistant_text},
                run_after=_utcnow(), dedupe_key=f"{TIMELINE_RECORD_JOB}:{outcome.user_message_ids[0]}")

    drain = DrainState()
    api, _close = build_chat_api(
        sessions=sessions, messages=messages, queue=queue, control=control,
        produce=produce, drain=drain, process_name=None, after_turn=after_turn, fence_sessions=True,
    )
    api.history = history

    # 连续使用提醒：用户发消息就算活跃；一段内到 2 小时，在这条回合的 SSE 里带一条提醒给客户端。
    # 计时失败只记日志（ComplianceService 内部已兜住），不会让回合失败。
    upstream_submit = api.submit

    class _ActivityAwareSubmit:
        async def submit(self, **kw):
            result = await upstream_submit.submit(**kw)
            if getattr(result, "status", "") == "accepted":
                try:
                    reminder = await compliance.note_activity(owner_id=int(kw["owner_id"]))
                except Exception:  # noqa: BLE001
                    log.warning("usage reminder failed", extra={"owner_id": kw.get("owner_id")})
                    reminder = None
                if reminder:
                    await control.publish(session_id=int(kw["session_id"]), event="usage.reminder",
                                          data={"text": reminder, "turn_id": result.turn_id or ""})
            return result

        def __getattr__(self, name):
            return getattr(upstream_submit, name)

    api.submit = _ActivityAwareSubmit()


    async def submit_proactive(owner_id: int, session_id: int, role_id: str, text: str) -> str | None:
        if await sessions.get(owner_id=owner_id, session_id=session_id) is None:
            raise SessionGone(session_id)
        # 主动联系总开关：关掉后调度器不再发起。用户明确要求的提醒是另一条路径（到点兑现），不受这个开关影响。
        if not await compliance.proactive_allowed(owner_id=owner_id):
            log.info("proactive skipped by consent", extra={"owner_id": owner_id, "session_id": session_id})
            return None
        result = await api.submit.submit(owner_id=owner_id, session_id=session_id, character_id=role_id,
                                         text=text, client_message_id=None, steerable=False,
                                         role="system", kind="proactive")
        if result.status != "accepted":
            raise RuntimeError(f"proactive submit {result.status}: {result.reason}")
        return result.turn_id

    dispatcher = ReminderDispatcher(store=reminder_store, submit=submit_proactive,
                                    owner=f"{socket.gethostname()}:{os.getpid()}", push=push or LogPush())

    uploads = objects = None
    if settings.tos_endpoint:
        from companion.adapters.storage.tos import TosObjectStore

        objects = TosObjectStore(endpoint=settings.tos_endpoint, bucket=settings.tos_bucket,
                                 access_key=settings.tos_access_key, secret_key=settings.tos_secret_key,
                                 region=settings.tos_region)
        uploads = UploadService(objects=objects, records=uploads_store, normalize=normalize_image,
                                key_prefix=settings.tos_key_prefix)

    # 形象发布需要对象存储（形象包是 zip）；没配 TOS 就不挂这组接口。
    avatars = (AvatarCatalog(store=SqlAvatarReleaseStore(engine), objects=objects,
                             key_prefix=settings.tos_key_prefix) if objects is not None else None)

    threads = None
    if checkpointer is not None:
        from companion.brain.conversation_state import CheckpointThreadEraser

        threads = CheckpointThreadEraser(checkpointer)
    system_role_ids = tuple(r.id for r in catalog.roles) + tuple(sorted(BUILTIN_PERSONA_IDS))
    account = AccountPurgeService(store=SqlAccountStore(engine), jobs=jobs, control=control, threads=threads,
                                  memory=memory, timeline=timeline, objects=objects,
                                  system_roles=lambda: system_role_ids)

    preferences = SqlPreferencesStore(engine)
    delivery = SqlDelivery(engine)
    ledger = SqlSendLedger(engine)

    return Platform(chat=api, roles=roles, uploads=uploads, confirmations=confirmations,
                    preferences=preferences, delivery=delivery, ledger=ledger,
                    memory=memory, timeline=timeline, drain=drain, engine=engine, redis=redis,
                    reminders=reminders, history=history, dispatcher=dispatcher, resummarize=resummarize,
                    pipeline=pipeline, jobs=jobs, timeline_recorder=timeline_recorder, persona_updater=persona_updater,
                    persona=persona, compliance=compliance, account=account, avatars=avatars,
                    admin_token=settings.companion_admin_token, sessions=sessions, brain=brain, qa=qa, objects=objects,
                    qa_retention_days=settings.companion_qa_retention_days, trace_writer=trace_writer, qa_enabled=qa_enabled,
                    tos_key_prefix=settings.tos_key_prefix, _pool=pool, _checkpointer=checkpointer)
