"""画像更新（后台任务 ``persona.update``，chat-agent 调研建议 1）。

**对话路径对画像只读，只有这个后台任务写**：回合里不抽取、不等模型，画像只在批量触发时更新。
触发：回合收尾时累计新的用户发言字数，超过阈值才入队一次抽取（默认 600 字；
Memobase 默认 1 小时或 1024 token，这里按字数更直观）。同一用户同一角色同一批只入队一次。

失败只记日志：画像少更新一次不影响对话，下一批会补上。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from companion.service.persona.extraction import MAX_FACTS, MAX_UTTERANCES, parse_drafts, render_prompt
from companion.service.persona.model import ABORT, plan_merge
from companion.agent.memory.subject import role_subject

log = logging.getLogger("companion.persona")

PERSONA_JOB = "persona.update"
TRIGGER_CHARS = 600
PAGE = 100

LLMCall = Callable[[str], Awaitable[str]]


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


class PersonaUpdater:
    def __init__(self, *, store: Any, memory: Any, messages: Any, llm: LLMCall,
                 trigger_chars: int = TRIGGER_CHARS) -> None:
        self._store = store          # PersonaStore
        self._memory = memory        # ScopedMemory：按角色空间读事实
        self._messages = messages    # MessageStore：读该会话的用户发言
        self._llm = llm
        self._trigger = trigger_chars

    async def note_turn(self, *, owner_id: int, role_id: str, last_message_id: int, user_text: str,
                        jobs: Any, session_id: int) -> bool:
        """回合收尾调用：累计字数，够了才入队。返回是否入队了任务。"""
        added = len(user_text.strip())
        if added == 0:
            return False
        pending = await self._store.advance(owner_id=owner_id, role_id=role_id, last_message_id=last_message_id,
                                            add_chars=added)
        if pending < self._trigger:
            return False
        # dedupe_key 带上批次水位：同一批重复调用只入队一次
        return await jobs.enqueue(kind=PERSONA_JOB, payload={
            "owner_id": owner_id, "role_id": role_id, "session_id": session_id,
            "up_to_message_id": last_message_id}, run_after=_now(),
            dedupe_key=f"{PERSONA_JOB}:{owner_id}:{role_id}:{last_message_id}")

    async def run(self, *, owner_id: int, role_id: str, session_id: int, up_to_message_id: int) -> int:
        """抽取并合并。返回写入的条数；模型输出不可用时返回 0。"""
        cursor, _ = await self._store.cursor(owner_id=owner_id, role_id=role_id)
        utterances = await self._recent_user_text(owner_id, session_id, after=cursor, up_to=up_to_message_id)
        facts = await self._memory.list_for_user(role_subject(owner_id, role_id), limit=MAX_FACTS)
        if not utterances and not facts:
            await self._store.reset_pending(owner_id=owner_id, role_id=role_id, last_message_id=up_to_message_id)
            return 0
        # 短编号只对本次有效：模型引用来源只能写这些，解析时再校验
        fact_ids = {f"F{i + 1}": f.id for i, f in enumerate(facts)}
        fact_lines = [(f"F{i + 1}", f.content) for i, f in enumerate(facts)]
        existing = await self._store.list_entries(owner_id=owner_id, role_id=role_id, include_history=True)
        prompt = render_prompt(existing=existing, fact_lines=fact_lines, utterances=utterances)
        try:
            raw = await self._llm(prompt)
        except Exception:  # noqa: BLE001 —— 模型失败交给任务重试，不推进游标
            log.warning("persona extraction call failed", extra={"owner_id": owner_id, "role_id": role_id})
            raise
        drafts = parse_drafts(raw, fact_ids=fact_ids, now=_now())
        # 逐条按「当前」画像决定怎么并。模型有时在同一批里对同一话题写两条：只留置信度更高的那条，
        # 不然两条都会通过合并判断、都落库。
        best: dict[str, Any] = {}
        for draft in drafts:
            if draft.topic not in best or draft.confidence > best[draft.topic].confidence:
                best[draft.topic] = draft
        actions = []
        for draft in best.values():
            action = plan_merge(existing, draft)
            if action.kind == ABORT:
                continue
            actions.append(action)
        written = await self._store.apply(owner_id=owner_id, role_id=role_id, actions=actions) if actions else 0
        await self._store.reset_pending(owner_id=owner_id, role_id=role_id, last_message_id=up_to_message_id)
        log.info("persona updated", extra={"owner_id": owner_id, "role_id": role_id, "drafts": len(drafts),
                                           "written": written})
        return written

    async def _recent_user_text(self, owner_id: int, session_id: int, *, after: int, up_to: int) -> list[str]:
        out: list[str] = []
        cursor = after
        while True:
            page = await self._messages.list_after(owner_id=owner_id, session_id=session_id,
                                                   after_id=cursor, limit=PAGE)
            for m in page:
                if m.id > up_to:
                    return out[-MAX_UTTERANCES:]
                if m.role == "user" and m.kind != "proactive" and m.content.strip():
                    out.append(m.content)
            if len(page) < PAGE:
                return out[-MAX_UTTERANCES:]
            cursor = page[-1].id
