"""回合后的记忆写入：把现有的提取器接成 ``Recorder``（chat-agent-memory-hooks.md §4.2）。

只从用户的话里提取；助手回复仅用于消歧（提取器的提示词已这样约束）。
"""

from __future__ import annotations

from companion.app.memory.extraction import MemoryExtractor
from companion.domain.memory.hooks import RecordOutcome, TurnRecord
from companion.domain.memory.subject import role_subject


class ExtractionRecorder:
    def __init__(self, extractor: MemoryExtractor, *, name: str = "facts", per_role: bool = True) -> None:
        self._extractor = extractor
        self.name = name
        self._per_role = per_role

    async def record(self, turn: TurnRecord) -> RecordOutcome:
        if not turn.user_text.strip():
            return RecordOutcome(source=self.name, skipped=1)
        items = await self._extractor.extract(
            user_id=role_subject(turn.user_id, turn.role_id) if self._per_role else turn.user_id,
            character_id=turn.role_id or "",
            message_id=turn.turn_id,
            user_message=turn.user_text,
            assistant_reply=turn.assistant_text,
        )
        return RecordOutcome(source=self.name, written=len(items))
