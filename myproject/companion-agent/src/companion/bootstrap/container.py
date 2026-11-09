"""装配：把各接口的实现接到一起，给 worker 与 HTTP 层一个入口。

所有依赖都可注入。默认值是一条**离线也能完整跑通**的链路：FakeBrain + 内存记忆
+ 内存时间线 + 默认策略。真实部署只需要在入口处替换 brain、memory、timeline
三个实现，其余装配逻辑不变。

中间件顺序在这里定，不在调用处定：装配层是唯一能看到全部组件的地方，把顺序
放在这里，就不可能某条入口偷偷漏掉一环。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from companion.app.tools.core import register_core_actions
from companion.domain.tools.executor import ActionExecutor, ActionRegistry
from companion.adapters.brain.fake import FakeBrain
from companion.ports.brain import BrainPort
from companion.app.chat.conversation import ConversationService
from companion.adapters.memory.fake import InMemoryMemoryPort
from companion.ports.memory import MemoryPort
from companion.domain.middleware.chain import MiddlewareChain
from companion.domain.middleware.cost import CostMiddleware
from companion.domain.middleware.extraction import EventExtractionMiddleware
from companion.domain.middleware.memory_recall import MemoryRecallMiddleware
from companion.domain.middleware.observability import ObservabilityMiddleware
from companion.domain.middleware.persona_guard import PersonaGuardMiddleware
from companion.domain.middleware.safety import SafetyMiddleware
from companion.domain.middleware.tool_auth import ToolAuthorizationMiddleware
from companion.domain.proactive.policy import InitiativePolicy
from companion.app.proactive.scheduler import InitiativeScheduler
from companion.adapters.roles.files import CharacterSource
from companion.app.chat.assembler import PromptAssembler
from companion.adapters.skills.library import SkillLibrary
from companion.domain.timeline.extraction import extract_events
from companion.adapters.timeline.memory import InMemoryTimeline

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Container:
    """一次进程内需要的全部实现。"""

    brain: BrainPort
    memory: MemoryPort
    timeline: Any
    conversation: ConversationService
    prompts: PromptAssembler
    actions: ActionRegistry
    executor: ActionExecutor
    scheduler: InitiativeScheduler
    chain: MiddlewareChain


def build_middleware_chain(
    *,
    memory: Any,
    timeline: Any,
    executor: ActionExecutor,
    extractor: Any | None = None,
    budget_tokens: int = 32_000,
) -> MiddlewareChain:
    """固定顺序：安全 → 记忆召回 → 事件抽取 → 人设 → 授权 → 成本 → 观测。

    顺序是设计的一部分（设计文档第 8 节）：安全最先，成本最后（它要看到前面
    所有环节的用量）。
    """
    middlewares = [
        SafetyMiddleware(),
        MemoryRecallMiddleware(memory=memory, timeline=timeline),
    ]
    if extractor is not None:
        middlewares.append(EventExtractionMiddleware(extractor=extractor, timeline=timeline))
    middlewares.extend(
        [
            PersonaGuardMiddleware(),
            ToolAuthorizationMiddleware(executor=executor),
            CostMiddleware(budget_tokens=budget_tokens),
            ObservabilityMiddleware(),
        ]
    )
    return MiddlewareChain(middlewares)


def create_container(
    *,
    brain: BrainPort | None = None,
    memory: MemoryPort | None = None,
    timeline: Any | None = None,
    characters_root: Path | None = None,
    skills_root: Path | None = None,
    extractor: Any | None = None,
    budget_tokens: int = 32_000,
) -> Container:
    """装配。不传参就是离线链路，测试与本地预览用这个。"""
    characters = CharacterSource(characters_root or PROJECT_ROOT / "characters")
    skills = SkillLibrary(skills_root or PROJECT_ROOT / "skills" / "public")
    prompts = PromptAssembler(characters=characters, skills=skills)

    resolved_brain = brain or FakeBrain()
    resolved_memory: MemoryPort = memory or InMemoryMemoryPort()
    resolved_timeline = timeline or InMemoryTimeline()

    registry = ActionRegistry()
    register_core_actions(
        registry=registry, memory=resolved_memory, timeline=resolved_timeline
    )
    executor = ActionExecutor(registry=registry)

    chain = build_middleware_chain(
        memory=resolved_memory,
        timeline=resolved_timeline,
        executor=executor,
        extractor=extractor,
        budget_tokens=budget_tokens,
    )

    conversation = ConversationService(
        brain=resolved_brain,
        prompt_builder=prompts,
        chain=chain,
    )

    scheduler = InitiativeScheduler(
        timeline=resolved_timeline,
        policy=InitiativePolicy(),
    )

    return Container(
        brain=resolved_brain,
        memory=resolved_memory,
        timeline=resolved_timeline,
        conversation=conversation,
        prompts=prompts,
        actions=registry,
        executor=executor,
        scheduler=scheduler,
        chain=chain,
    )


def default_extractor() -> Any:
    """真实部署用的抽取器。

    这里返回的是函数而不是实例：它需要模型调用，而模型在进程启动后才装配。
    """
    return extract_events
