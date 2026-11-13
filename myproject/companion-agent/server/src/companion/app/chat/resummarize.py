"""重建会话摘要（后台任务 ``session.resummarize``）。

触发：用户删除或编辑了线程里已经找不到的消息（已被摘要压缩），见 app/chat/history.py。
做法：线程里现存最早的消息之前、消息表里未删除的内容 → 重新生成摘要 → 写回线程的 ``summary_text``。
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable

from companion.domain.history.summary import TranscriptLine, render_transcript, summary_prompt
from companion.ports.conversation import ConversationStatePort, message_id_of
from companion.ports.store import MessageStore
from companion.ports.turn_control import TurnControlPort

log = logging.getLogger("companion.summary")

LLMCall = Callable[[str], Awaitable[str]]
PAGE = 200


class SessionBusy(RuntimeError):
    """会话正在进行回合：任务稍后重试。"""


class ResummarizeService:
    def __init__(self, *, messages: MessageStore, conversation: ConversationStatePort,
                 control: TurnControlPort, llm: LLMCall) -> None:
        self._messages = messages
        self._conversation = conversation
        self._control = control
        self._llm = llm

    async def run(self, *, owner_id: int, session_id: int) -> str:
        owner = f"summary:{uuid.uuid4().hex}"
        if not await self._control.acquire_lock(session_id=session_id, owner=owner):
            raise SessionBusy(session_id)
        try:
            present = await self._conversation.present_ids(session_id=session_id)
            present_mids = [m for m in (message_id_of(i) for i in present) if m is not None]
            boundary = min(present_mids) if present_mids else None

            lines: list[TranscriptLine] = []
            after = 0
            done = False
            while not done:
                page = await self._messages.list_after(owner_id=owner_id, session_id=session_id,
                                                       after_id=after, limit=PAGE)
                for m in page:
                    if boundary is not None and m.id >= boundary:
                        done = True   # 从这里开始的消息仍在线程里，不属于摘要范围
                        break
                    if m.role in ("user", "assistant") and m.content.strip():
                        lines.append(TranscriptLine(role=m.role, text=m.content))
                if len(page) < PAGE:
                    done = True
                elif page:
                    after = page[-1].id

            if not lines:
                await self._conversation.set_summary(session_id=session_id, text="")
                return ""
            text = (await self._llm(summary_prompt(render_transcript(lines)))).strip()
            await self._conversation.set_summary(session_id=session_id, text=text)
            log.info("summary rebuilt", extra={"session_id": session_id, "lines": len(lines), "chars": len(text)})
            return text
        finally:
            await self._control.release_lock(session_id=session_id, owner=owner)
