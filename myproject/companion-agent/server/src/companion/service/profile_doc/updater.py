"""用户档案维护（后台任务 ``profile_doc.update``）。

**对话路径对档案只读，只有这个后台任务写**：回合里不维护、不等模型。
触发方式和画像一样：回合收尾累计新的用户发言字数，超过阈值才入队一次维护
（默认 1200 字——档案比画像条目更贵：要读整篇旧档案重写，攒更大的批更划算）。

与画像更新的两个不同：
- **管理员优先**：落库是乐观并发。维护期间管理员改过档案（version 变了），这一批放弃，
  只推水位；下一批以管理员的版本为底稿重写。
- **整体重写而非逐条合并**：模型产出整篇新档案（或「无变化」），没有条目级合并规则。

失败只记日志：档案少维护一次不影响对话，下一批会补上。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from companion.agent.memory.subject import role_subject
from companion.service.profile_doc.extraction import MAX_FACTS, MAX_UTTERANCES, parse_doc, render_prompt

log = logging.getLogger("companion.profile_doc")

PROFILE_DOC_JOB = "profile_doc.update"
TRIGGER_CHARS = 1200
PAGE = 100

LLMCall = Callable[[str], Awaitable[str]]


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


class ProfileDocUpdater:
    def __init__(self, *, store: Any, memory: Any, messages: Any, llm: LLMCall,
                 trigger_chars: int = TRIGGER_CHARS) -> None:
        self._store = store          # ProfileDocStore
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
        pending = await self._store.advance(owner_id=owner_id, role_id=role_id,
                                            last_message_id=last_message_id, add_chars=added)
        if pending < self._trigger:
            return False
        # dedupe_key 带上批次水位：同一批重复调用只入队一次
        return await jobs.enqueue(kind=PROFILE_DOC_JOB, payload={
            "owner_id": owner_id, "role_id": role_id, "session_id": session_id,
            "up_to_message_id": last_message_id}, run_after=_now(),
            dedupe_key=f"{PROFILE_DOC_JOB}:{owner_id}:{role_id}:{last_message_id}")

    async def run(self, *, owner_id: int, role_id: str, session_id: int, up_to_message_id: int,
                  role_name: str = "") -> int:
        """维护一次档案。返回 1（写了新档案）或 0（无变化 / 放弃）；模型失败则抛出交任务重试。"""
        current = await self._store.get(owner_id=owner_id, role_id=role_id)
        if current is None:
            return 0
        since = current.last_message_id
        utterances = await self._recent_user_text(owner_id, session_id, after=since, up_to=up_to_message_id)
        facts = await self._memory.list_for_user(role_subject(owner_id, role_id), limit=MAX_FACTS)
        if not utterances and not facts:
            await self._store.mark_processed(owner_id=owner_id, role_id=role_id,
                                             last_message_id=up_to_message_id)
            return 0
        # 短编号只对本次有效：模型在提示词里看到编号，解析端不再用它们（正文出现编号即不合格）
        fact_lines = [(f"F{i + 1}", f.content) for i, f in enumerate(facts)]
        prompt = render_prompt(role_name=role_name or role_id, doc=current.markdown,
                               fact_lines=fact_lines, utterances=utterances)
        try:
            raw = await self._llm(prompt)
        except Exception:  # noqa: BLE001 —— 模型失败交给任务重试，不推水位
            log.warning("profile doc maintain call failed", extra={"owner_id": owner_id, "role_id": role_id})
            raise
        markdown = parse_doc(raw)
        if markdown is None:
            # 「无变化」或输出不合格：推水位（这批已经看过），不动正文
            await self._store.mark_processed(owner_id=owner_id, role_id=role_id,
                                             last_message_id=up_to_message_id)
            log.info("profile doc unchanged", extra={"owner_id": owner_id, "role_id": role_id})
            return 0
        if not await self._store.commit_llm(owner_id=owner_id, role_id=role_id, markdown=markdown,
                                            up_to_message_id=up_to_message_id,
                                            expected_version=current.version):
            # 管理员在这期间改过档案：放弃这一版，以管理员的为底稿，下一批再来
            await self._store.mark_processed(owner_id=owner_id, role_id=role_id,
                                             last_message_id=up_to_message_id)
            log.info("profile doc skipped (admin edited meanwhile)",
                     extra={"owner_id": owner_id, "role_id": role_id})
            return 0
        log.info("profile doc updated", extra={"owner_id": owner_id, "role_id": role_id,
                                               "chars": len(markdown)})
        return 1

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
