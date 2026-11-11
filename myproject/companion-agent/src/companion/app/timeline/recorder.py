"""回合后的事件抽取：把「用户说了下周三面试」写进时间线（chat-agent-timeline-design.md §5）。

和记忆写入同一个位置、同一种方式：回合结束后入队后台任务（按 turn_id 幂等），不在回合里等它。
写入按 ``dedupe_key`` 合并，所以工具已经记过的那件事不会重复。

两个刻意的边界（与记忆抽取相同）：
- 只从用户的话里抽；角色的回复只作上下文。
- 失败只记日志，不影响已经完成的回合。
"""

from __future__ import annotations

import logging
from typing import Any

from companion.domain.timeline.extraction import extract_events
from companion.domain.timeline.models import EventOrigin, TimelineEvent

log = logging.getLogger("companion.timeline")

# 低于这个置信度的事件只存着（对话里可以自然提起），不参与将来的主动提醒。
MIN_CONFIDENCE = 0.5


class TimelineRecorder:
    def __init__(self, store: Any, llm: Any, *, min_confidence: float = MIN_CONFIDENCE) -> None:
        self._store = store
        self._llm = llm
        self._min_confidence = min_confidence

    async def record_turn(self, *, owner_id: int, role_id: str, session_id: int | None, user_message_id: int,
                          user_text: str, assistant_text: str = "") -> list[TimelineEvent]:
        if not user_text.strip():
            return []
        conversation = f"用户：{user_text.strip()}\n角色：{assistant_text.strip()[:400]}"
        try:
            events = await extract_events(conversation=conversation, user_id=str(owner_id),
                                          character_id=role_id, message_id=str(user_message_id),
                                          llm=self._llm)
        except Exception:  # noqa: BLE001 —— 少记一条事件不该让任务失败重试
            log.warning("event extraction failed", extra={"owner_id": owner_id, "message_id": user_message_id})
            return []
        saved: list[TimelineEvent] = []
        for event in events:
            if event.confidence < self._min_confidence:
                continue
            event.origin = EventOrigin.EXTRACTED
            event.session_id = session_id
            saved.append(await self._store.upsert(event))
        return saved
