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
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from companion import metrics
from companion.service.turn.redis_control import RedisTurnControl
from companion.agent.memory.recallers import MemoryPortRecaller, TimelineRecaller
from companion.service.proactive.push_log import LogPush
from companion.service.roles.catalog_files import load_system_catalog
from companion.service.uploads.images import normalize_image
from companion.service.account.sql import SqlAccountStore
from companion.service.avatar.sql import SqlAvatarReleaseStore
from companion.service.jobs.sql import SqlJobStore
from companion.service.persona.sql import SqlPersonaStore
from companion.service.relationship.model import delta_for
from companion.service.relationship.sql import SqlRelationshipStore
from companion.service.card.sql import SqlCardStore
from companion.service.card.store import CardService
from companion.service.roles.packs import (
    ChainedCharacterSource,
    DbCharacterSource,
    SqlCharacterPackStore,
)
from companion.service.roles.hers import SqlHerPackStore
from companion.service.proactive.store import (
    SqlDelivery, SqlPreferencesStore, SqlSendLedger,
)
from companion.service.timeline.sql import SqlTimelineStore
from companion.agent.memory.sql import SqlMemoryPort
from companion.service.proactive.reminders_sql import SqlReminderStore
from companion.db.sql import (
    SqlConfirmationStore,
    SqlMessageStore,
    SqlQueueStore,
    SqlRoleStore,
    SqlSessionStore,
    SqlToolCallStore,
    SqlUploadStore,
)
from companion.api.http.routers.chat import ChatApi
from companion.service.compliance.sql import SqlComplianceStore
from companion.service.account.purge import AccountPurgeService
from companion.service.compliance.service import ComplianceService
from companion.service.avatar.catalog import AvatarCatalog
from companion.service.chat.assembler import PromptAssembler, skill_ids_of
from companion.service.chat.context import ContextBuilder
from companion.service.chat.history import HistoryService
from companion.service.chat.lifecycle import DrainState
from companion.service.chat.resummarize import ResummarizeService
from companion.service.chat.turn_runner import TurnOutcome
from companion.agent.memory.extraction import MemoryExtractor
from companion.agent.memory.recorder import ExtractionRecorder
from companion.service.persona.updater import PERSONA_JOB, PersonaUpdater
from companion.service.profile_doc.sql import SqlProfileDocStore
from companion.service.profile_doc.updater import ProfileDocUpdater
from companion.service.timeline.recorder import TimelineRecorder
from companion.service.proactive.reminders import ReminderDispatcher, ReminderService, SessionGone
from companion.service.roles.resolver import RoleProfileResolver
from companion.service.roles.service import RoleService
from companion.service.tools_impl.builtin import register_builtin_tools
from companion.agent.tools.confirmation import ConfirmationService
from companion.agent.tools.runtime import ToolRuntime
from companion.service.uploads.service import UploadService
from companion.bootstrap.chat_stack import build_chat_api
from companion.agent.brain.llm_trace import LlmCallCollector
from companion.service.trace.writer import BackgroundWriter
from companion.config import Settings
from companion.paths import CHARACTERS_DIR, ROLES_CATALOG_DIR, SKILLS_PUBLIC_DIR
from companion.agent.prompt.templates import PROMPT_VERSION
from companion.service.history.summary import TIMELINE_RECORD_JOB
from companion.agent.memory.pipeline import MEMORY_RECORD_JOB, MemoryPipeline
from companion.agent.tools.registry import ToolRegistry
from companion.agent.brain.port import TextDelta, TurnRequest
from memory_hub import AppConfig, MemoryHub
from memory_hub.hub import ScopedMemory

log = logging.getLogger("companion.platform")

BUILTIN_PERSONA_IDS = frozenset({"linche", "sudai"})


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def log_turn_llm_calls(calls: list[Any], *, channel: str) -> None:
    """语音 worker 没有 /metrics，模型段只能落进行内日志（F16 RCA 的 ② 段）。

    字段全部来自 LlmCallCollector 已有的记录，不新造采集。文字通道的同一组数字
    由 api 进程的 /metrics 提供（observe_llm_call 在采集器里就写掉），这里只补语音。
    """
    if channel != "voice":
        return
    for call in calls:
        log.info(
            "voice llm seq=%d model=%s ttft_ms=%s total_ms=%s reasoning_chars=%d error=%s",
            call.seq, call.model or "-",
            call.first_token_ms if call.first_token_ms is not None else "-",
            call.total_ms if call.total_ms is not None else "-",
            len(call.reasoning_text or ""), call.error_code or "-",
        )


def voice_llm_start_logger(*, channel: str):
    """模型**开流那一刻**的日志口（F16 ② 段的另一半），非语音通道返回 None。

    ``voice llm`` 那行在回合收尾才落，时间戳是流末；被打断的回合里 ``on_llm_end``
    还会晚触发，拿它减 total_ms 反推开流时刻整体错位。这一行由 LlmCallCollector 在
    ``on_chat_model_start`` 当场调用，和 context 完成、tts start 同一条时钟轴，
    ② 段就能切成 A（recall→开流）/ B（ttft）/ C（开流→首片段）三段分别读。
    """
    if channel != "voice":
        return None

    def on_start(*, seq: int, model: str) -> None:
        log.info("voice llm start seq=%d model=%s", seq, model or "-")

    return on_start


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
    profile_doc_updater: Any = None
    profile_doc: Any = None
    relationship: Any = None
    compliance: ComplianceService | None = None
    account: AccountPurgeService | None = None
    avatars: AvatarCatalog | None = None
    admin_token: str = ""
    sessions: Any = None
    brain: Any = None
    qa: Any = None
    # 孤儿回合清扫（重启打断的回合重新驱动）。见 service/chat/recovery.py。
    turn_recovery: Any = None
    objects: Any = None
    # P6 角色卡（可版本化身份/边界）与窄记忆索引读接口共享它
    cards: Any = None
    # 角色读取链（库优先、文件兜底）：目录、语音入口与解析共用一条链，
    # 「页面上的角色」与「说话的角色」不会各自读一份。见 service/roles/packs.py。
    characters: Any = None
    # her 包注册表（呈现实体，persona/her 分层第一刀）：ca_her_pack + ca_character_her。
    # 没有文件兜底——呈现实体从第一刀起就以库为事实源（播种 tools/seed_her_packs.py）。
    hers: Any = None
    # 二次元头像生成（Android 契约）：uploads 可用时才有——生成图的存储复用 uploads。
    avatar_gen: Any = None
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
    from companion.agent.brain.deerflow import DeerFlowBrain, build_summarization, build_turn_graph
    from companion.agent.brain.tools import to_langchain_tools
    from companion.agent.llm.router import LLMRouter
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
    from companion.service.roles.files import CharacterSource
    from companion.agent.skills.library import SkillLibrary

    return PromptAssembler(characters=CharacterSource(CHARACTERS_DIR),
                           skills=SkillLibrary(SKILLS_PUBLIC_DIR))


def build_platform(settings: Settings, *, brain: Any = None, prompts: Any = None, memory_port: Any = None,
                   llm: Any = None, push: Any = None, catalog: Any = None, profile: str = "api",
                   checkpoint_bundle: tuple[Any, Any] | None = None) -> Platform:
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

    from companion.service.trace.qa import SqlQaStore

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

    if catalog is None:
        catalog = load_system_catalog(ROLES_CATALOG_DIR, reserved_ids=BUILTIN_PERSONA_IDS)
    roles = RoleService(catalog, roles_store)

    timeline = SqlTimelineStore(engine)
    backend = memory_port if memory_port is not None else SqlMemoryPort(engine)
    hub = MemoryHub.from_config([AppConfig("companion")], lambda cfg: backend)
    memory = hub.for_app("companion")

    reminders = ReminderService(store=reminder_store, sessions=sessions)
    registry = ToolRegistry()
    register_builtin_tools(registry, memory=memory, timeline=timeline, reminders=reminders,
                           amap_key=settings.amap_key)
    runtime = ToolRuntime(registry=registry, confirmations=confirmations_store, audit=tool_calls)
    confirmations = ConfirmationService(store=confirmations_store, messages=messages, runtime=runtime)

    pool = checkpointer = graph = None
    if brain is None:
        if settings.checkpoint_url:
            if checkpoint_bundle is not None:
                pool, checkpointer = checkpoint_bundle
            else:
                pool, checkpointer = _checkpointer(settings.checkpoint_url, pool_profile)
        brain, graph, built_llm = _build_brain(settings, registry=registry, runtime=runtime,
                                               checkpointer=checkpointer)
        llm = llm or built_llm

    conversation = None
    if graph is not None and checkpointer is not None:
        from companion.agent.brain.conversation_state import DeerFlowConversationState

        conversation = DeerFlowConversationState(graph)

    recorders = [ExtractionRecorder(MemoryExtractor(memory, llm))] if llm is not None else []
    pipeline = MemoryPipeline(recallers=[MemoryPortRecaller(memory), TimelineRecaller(timeline)],
                              recorders=recorders)
    # P6 角色卡：CardService 包住 SQL store；API 与解析链的覆盖层都只经它。
    # （建在 resolver 之前：用户的微调要在角色解析里盖在系统包上。）
    cards = CardService(SqlCardStore(engine))
    # 角色封装在库里：解析与目录都走链（ca_character_pack 优先，prompts 里的文件源兜底，
    # 见 service/roles/packs.py）。没播种过的部署读文件，播种之后以库为准——
    # 「改了没生效」不再取决于哪台机器的磁盘。
    file_characters = getattr(prompts, "characters", None)
    characters = ChainedCharacterSource(
        tuple(s for s in (DbCharacterSource(SqlCharacterPackStore(engine)), file_characters) if s is not None))
    # her 包注册表：与角色链同步建立（同一 engine），路由在 app 装配时挂。
    hers = SqlHerPackStore(engine)
    # prompts：PromptAssembler（角色卡来源 + skill 目录），陪伴角色卡与它声明的 skill 都从这里来。
    # card_overlays=cards：用户的角色卡微调（ca_role_card）盖在系统包之上，只覆盖人格字段，
    # 最后应用——系统封装与用户微调互不顶掉。
    resolver = RoleProfileResolver(catalog=catalog, user_roles=roles_store,
                                   characters=characters,
                                   skills=getattr(prompts, "skills", None), skill_ids_of=skill_ids_of,
                                   card_overlays=cards)
    compliance = ComplianceService(store=SqlComplianceStore(engine))
    persona = SqlPersonaStore(engine)
    persona_updater = PersonaUpdater(store=persona, memory=memory, messages=messages, llm=llm) if llm is not None else None
    # 用户档案（形态 A）：与画像条目并行的长篇 Markdown，同一套「攒批 + 后台维护」节奏
    profile_doc = SqlProfileDocStore(engine)
    profile_doc_updater = (ProfileDocUpdater(store=profile_doc, memory=memory, messages=messages, llm=llm)
                           if llm is not None else None)
    relationship = SqlRelationshipStore(engine)
    context = ContextBuilder(roles=resolver, messages=messages, sessions=sessions, memory=pipeline, persona=persona,
                             relationship=relationship, profile_doc=profile_doc)
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
        # 语音回合的模型段先落日志再返回：语音 worker（8082）没有 /metrics，
        # 没有这一行，RCA 里「context 完成→流末」只能靠时间差猜（见 log_turn_llm_calls）。
        log_turn_llm_calls(calls, channel=str(request.metadata.get("channel") or "text"))
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
        # 输出层要知道这句话从哪来：语音要口语短句且带 cue JSON，文字不要 Markdown 之外的东西。
        # 渠道由回合层写在 metadata 里（见 TurnRunner._attempt）。
        channel = str(request.metadata.get("channel") or "text")
        prepare_started = time.monotonic()
        plan = await context.build(owner_id=owner_id, session_id=request.session_id or 0,
                                   role_id=request.character_id, current_texts=texts, channel=channel)
        # 用户的等待里有一部分是我们自己造提示词（召回、世界书、角色卡），和模型无关。
        # 单独量出来，别都算到"模型慢"头上。
        metrics.observe_phase(phase="prepare", duration_sec=time.monotonic() - prepare_started)
        # ⓪ 段探针：语音 worker（8082）没有 /metrics，Prometheus 这一份在语音侧看不见，
        # 没有这行「提交完成→造提示词完成」就只能靠别的行的时间差推。
        if channel == "voice":
            log.info("voice prepare ms=%d", int((time.monotonic() - prepare_started) * 1000))
        request.prompt = plan
        request.system_prompt = plan.system
        if hasattr(brain, "run"):
            # 采集器一直挂着，不再跟 QA 开关走：它同时承担写指标（延迟、用量）的职责，
            # 追踪落不落库才看开关（见 record_trace 与 metrics 模块文档）。
            # 语音通道额外挂开流日志口：② 段要在开流那一刻记墙钟，见 voice_llm_start_logger。
            collector = LlmCallCollector(on_start=voice_llm_start_logger(channel=channel))
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
        # 有「已说话前缀」时只补记她真正说出口的部分（契约 v2 §2.2）：全部已生成文本
        # 里有一半以上可能根本没出声，喂给模型就是让它以为自己说完了那半句。
        # 没有前缀（文字端回合、缺 played_ms）时退回全量，与改动前一致。
        if outcome.interrupted and outcome.assistant_message_id and not outcome.lock_lost:
            noted = outcome.spoken_prefix or outcome.assistant_text
            if noted.strip():
                await history.note_interrupted(session_id=outcome.session_id,
                                               assistant_message_id=outcome.assistant_message_id,
                                               text=noted)
        # 记忆写入放到后台任务：回合不等它。
        if recorders and not outcome.failed and outcome.user_text.strip():
            await jobs.enqueue(kind=MEMORY_RECORD_JOB, payload={
                "owner_id": outcome.owner_id, "session_id": outcome.session_id, "role_id": outcome.character_id,
                "turn_id": outcome.turn_id, "user_text": outcome.user_text,
                "assistant_text": outcome.assistant_text}, run_after=_utcnow(),
                dedupe_key=f"{MEMORY_RECORD_JOB}:{outcome.turn_id}")
        # 关系：纯算术（无模型），每个成功回合直接落一次；失败与中断的回合不算真实互动。
        if not outcome.failed and outcome.user_text.strip():
            await relationship.bump(owner_id=outcome.owner_id, role_id=outcome.character_id,
                                    delta=delta_for(outcome.user_text), at=_utcnow())
        # 画像：累计用户发言字数，够一批才入队（对话路径只记数，不抽取、不等模型）。
        if persona_updater is not None and not outcome.failed and outcome.user_text.strip() and outcome.user_message_ids:
            await persona_updater.note_turn(
                owner_id=outcome.owner_id, role_id=outcome.character_id, last_message_id=max(outcome.user_message_ids),
                user_text=outcome.user_text, jobs=jobs, session_id=outcome.session_id)
        # 用户档案：同一套攒批节奏，但批次更大（整篇重写比逐条更贵）
        if profile_doc_updater is not None and not outcome.failed and outcome.user_text.strip() and outcome.user_message_ids:
            await profile_doc_updater.note_turn(
                owner_id=outcome.owner_id, role_id=outcome.character_id, last_message_id=max(outcome.user_message_ids),
                user_text=outcome.user_text, jobs=jobs, session_id=outcome.session_id)
        # 事件的来源是这一回合的第一条用户消息（重新生成、合并时也指向它）。
        if timeline_recorder is not None and not outcome.failed and outcome.user_message_ids:
            await jobs.enqueue(kind=TIMELINE_RECORD_JOB, payload={
                "owner_id": outcome.owner_id, "session_id": outcome.session_id, "role_id": outcome.character_id,
                "user_message_id": outcome.user_message_ids[0], "turn_id": outcome.turn_id,
                "user_text": outcome.user_text, "assistant_text": outcome.assistant_text},
                run_after=_utcnow(), dedupe_key=f"{TIMELINE_RECORD_JOB}:{outcome.user_message_ids[0]}")

    # 对象存储要在 build_chat_api 之前建好：回合需要按 upload_id 读原图喂给模型。
    # 放在后面会 UnboundLocalError（uploads 此时还没绑值），而且那是个只在启动时才暴露的错误。
    uploads = objects = None
    if settings.tos_endpoint:
        from companion.service.uploads.tos import TosObjectStore
        from companion.bootstrap.checks import assert_storage_reachable

        objects = TosObjectStore(endpoint=settings.tos_endpoint, bucket=settings.tos_bucket,
                                 access_key=settings.tos_access_key, secret_key=settings.tos_secret_key,
                                 region=settings.tos_region)
        # 凭据配错时当场自检，不要等到第一次上传才 500（见 assert_storage_reachable）。
        #
        # 但**不因此拒绝启动**：对象存储只影响「发图片」这一条能力，聊天本身不依赖它。
        # 让一个可选子系统的凭据问题把整个进程挡住，等于用一次配置失误换一次全站停机
        # （2026-11-17 就这么发生过一次）。所以这里降级：记一条 CRITICAL、关掉上传与形象接口，
        # 服务照常起来；凭据修好之后重启即恢复。
        try:
            assert_storage_reachable(objects, bucket=settings.tos_bucket)
        except Exception as exc:  # noqa: BLE001 —— 任何原因的自检失败都只降级，不中止启动
            log.critical("对象存储自检失败，图片上传与形象接口本次不启用；修好 TOS_* 后重启即恢复",
                         extra={"bucket": settings.tos_bucket, "error": str(exc)[:300]})
            objects = None
        if objects is not None:
            uploads = UploadService(objects=objects, records=uploads_store, normalize=normalize_image,
                                    key_prefix=settings.tos_key_prefix)

    drain = DrainState()
    api, _close = build_chat_api(
        sessions=sessions, messages=messages, queue=queue, control=control,
        produce=produce, drain=drain, process_name=None, after_turn=after_turn, fence_sessions=True,
        uploads=uploads,
    )
    api.history = history
    # 建会话时校验角色存在性：与回合里同一判据（同一个 resolver），不会出现
    # 「建会话放行、发消息必挂」的错位（线上 __default__ 占位符事故的根治）。
    api.role_check = resolver.exists

    # 孤儿回合清扫：重启打断一个刚起步的回合后，那条消息原本永远没有回复
    # （2026-11-28 线上 session 39）。判活看 Redis 锁，不靠猜时间。见 service/chat/recovery.py。
    from companion.service.chat.recovery import SqlTurnRecoveryStore, TurnRecovery

    turn_recovery = TurnRecovery(store=SqlTurnRecoveryStore(engine), control=control,
                                 submit=api.submit, sessions=sessions, queue=queue)

    # 直传（ADR-011 同款）：sign 签发 presigned PUT、发送时绑定校验。挂在不被 dataclass
    # 约束的 ChatApi 实例上，随 uploads 一起降级——对象存储自检失败时直传同样不可用。
    if objects is not None:
        from companion.service.uploads.direct import DirectUploadService

        api.direct = DirectUploadService(objects=objects, records=uploads_store,
                                         key_prefix=settings.tos_key_prefix)

    # 连续使用提醒：用户发消息就算活跃；一段内到 2 小时，在这条回合的 SSE 里带一条提醒给客户端。
    # 计时失败只记日志（ComplianceService 内部已兜住），不会让回合失败。
    upstream_submit = api.submit

    class _ActivityAwareSubmit:
        async def submit(self, **kw):
            # ⓪ 段探针：把「上游提交」与「活跃记账」分开量。note_activity 是在语音路径上
            # 同步等的库往返，没有这一行就只能看见总耗时、分不清哪一段。
            upstream_started = time.monotonic()
            result = await upstream_submit.submit(**kw)
            upstream_ms = int((time.monotonic() - upstream_started) * 1000)
            if getattr(result, "status", "") == "accepted":
                activity_started = time.monotonic()
                try:
                    reminder = await compliance.note_activity(owner_id=int(kw["owner_id"]))
                except Exception:  # noqa: BLE001
                    log.warning("usage reminder failed", extra={"owner_id": kw.get("owner_id")})
                    reminder = None
                activity_ms = int((time.monotonic() - activity_started) * 1000)
                if reminder:
                    await control.publish(session_id=int(kw["session_id"]), event="usage.reminder",
                                          data={"text": reminder, "turn_id": result.turn_id or ""})
                log.info("voice submit chain upstream_ms=%d activity_ms=%d", upstream_ms, activity_ms)
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

    # 形象发布需要对象存储（形象包是 zip）；没配 TOS 就不挂这组接口。
    avatars = (AvatarCatalog(store=SqlAvatarReleaseStore(engine), objects=objects,
                             key_prefix=settings.tos_key_prefix) if objects is not None else None)

    # 二次元头像（Android 契约 2026-11-24-anime-avatar-mvp.md）：同样吃对象存储——
    # 源图与生成图都走既有 uploads 管线，uploads 降级时这组接口一起关。
    # provider 在这里选：fake 默认可用；配了没有实现的取值当场拒绝启动（fail-closed）。
    avatar_gen = None
    if uploads is not None:
        from datetime import timedelta

        from companion.service.avatar_gen.providers import real_provider
        from companion.service.avatar_gen.service import AvatarGenService
        from companion.service.avatar_gen.sql import SqlAvatarGenAttemptStore, SqlUserAvatarStore

        avatar_gen = AvatarGenService(
            uploads=uploads, attempts=SqlAvatarGenAttemptStore(engine), avatars=SqlUserAvatarStore(engine),
            provider=real_provider(settings), daily_quota=settings.companion_avatar_gen_daily_quota,
            source_ttl=timedelta(hours=settings.companion_avatar_source_ttl_hours))

    dispatcher = ReminderDispatcher(store=reminder_store, submit=submit_proactive,
                                    owner=f"{socket.gethostname()}:{os.getpid()}", push=push or LogPush())

    threads = None
    if checkpointer is not None:
        from companion.agent.brain.conversation_state import CheckpointThreadEraser

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
                    persona=persona, profile_doc_updater=profile_doc_updater, profile_doc=profile_doc,
                    relationship=relationship, compliance=compliance, account=account, avatars=avatars,
                    avatar_gen=avatar_gen,
                    cards=cards,
                    characters=characters,
                    hers=hers,
                    admin_token=settings.companion_admin_token, sessions=sessions, brain=brain, qa=qa, objects=objects,
                    turn_recovery=turn_recovery,
                    qa_retention_days=settings.companion_qa_retention_days, trace_writer=trace_writer, qa_enabled=qa_enabled,
                    tos_key_prefix=settings.tos_key_prefix, _pool=pool, _checkpointer=checkpointer)
