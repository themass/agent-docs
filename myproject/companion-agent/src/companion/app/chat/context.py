"""每回合的上下文组装（chat-agent-next-plan.md 阶段 3）。

只组装「历史之外」的东西：系统提示词与按深度注入。对话历史由大脑的 checkpoint 提供。

输入来源：
- 角色：RoleProfileResolver（三种来源统一成 RoleProfile）；
- 世界书扫描文本：消息表里最近几条（原始内容，含本轮输入）；
- 记忆：MemoryPipeline 召回（失败或超时不影响回合，只是这一轮没有记忆段）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from companion.app.roles.resolver import RoleProfileResolver
from companion.domain.memory.hooks import RecallQuery
from companion.domain.memory.pipeline import MemoryPipeline, render_memory_block
from companion.domain.persona.model import render_profile
from companion.domain.prompt.plan import PromptPlan
from companion.domain.prompt.roleplay import PromptBudget, build_prompt_plan
from companion.ports.store import MessageStore, SessionStore

log = logging.getLogger("companion.context")

SCAN_MESSAGES = 6


@dataclass(frozen=True)
class ContextSettings:
    scope: str = "companion"
    memory_limit: int = 5
    budget: PromptBudget = PromptBudget()
    user_name: str = "用户"


class ContextBuilder:
    def __init__(self, *, roles: RoleProfileResolver, messages: MessageStore, sessions: SessionStore,
                 memory: MemoryPipeline | None = None, settings: ContextSettings = ContextSettings(),
                 persona: object | None = None) -> None:
        self._persona = persona   # PersonaStore：对话路径只读，写入全在后台任务里
        self._roles = roles
        self._messages = messages
        self._sessions = sessions
        self._memory = memory
        self._settings = settings

    async def build(self, *, owner_id: int, session_id: int, role_id: str, current_texts: tuple[str, ...],
                    channel: str = "text") -> PromptPlan:
        session = await self._sessions.get(owner_id=owner_id, session_id=session_id)
        locale = session.locale if session is not None else "zh-CN"
        profile = await self._roles.resolve(role_id=role_id, owner_id=owner_id, locale=locale)

        recent = await self._messages.list_before(owner_id=owner_id, session_id=session_id, before_id=None,
                                                  limit=SCAN_MESSAGES)
        # 最新在前；本轮输入已经落库，所以通常已在 recent 里，去重后放在最前。
        texts: list[str] = [t for t in reversed(current_texts) if t]
        texts += [m.content for m in recent if m.content and m.content not in texts]

        memory_block = ""
        if self._memory is not None and current_texts:
            items, stats = await self._memory.recall(RecallQuery(
                user_id=str(owner_id), scope=self._settings.scope, text="\n".join(current_texts),
                limit=self._settings.memory_limit, budget_chars=self._settings.budget.memory_chars,
                role_id=role_id))
            memory_block = render_memory_block(items)
            log.info("recall", extra={"session_id": session_id, "items": len(items),
                                      "sources": stats.per_source, "truncated": stats.truncated})

        persona_block = ""
        if self._persona is not None:
            try:
                entries = await self._persona.list_entries(owner_id=owner_id, role_id=role_id)
                persona_block = render_profile(entries, budget_chars=self._settings.budget.persona_chars)
            except Exception:  # noqa: BLE001 —— 画像读不到只是这一轮少一段，不能让回合失败
                log.warning("persona read failed", extra={"session_id": session_id})

        plan = build_prompt_plan(profile, user_name=self._settings.user_name, locale=locale, channel=channel,
                                 recent_texts=tuple(texts), memory_block=memory_block,
                                 persona_block=persona_block, budget=self._settings.budget)
        if plan.dropped:
            log.info("prompt budget dropped", extra={"session_id": session_id, "dropped": plan.dropped})
        return plan
