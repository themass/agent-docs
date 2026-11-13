"""队列排空（D §6.4、§6.5）。

一批最多 DRAIN_BATCH_SIZE 条，合并成一个回合启动，并把这些消息挂到新回合上。
排空失败回到 queued；drain_attempts 在 queued→draining 时已计数，达到上限后置 failed，
等用户手动重试（POST /sessions/{id}/queue/retry）。
"""

from __future__ import annotations

from dataclasses import dataclass

from companion.agent.util.ids import new_ulid
from companion.service.chat.submit import SubmitService
from companion.service.turn.queue import DRAIN_BATCH_SIZE, DRAIN_MAX_ATTEMPTS
from companion.db.port import QueueItem, QueueStore


@dataclass(frozen=True)
class DrainOutcome:
    started: bool
    count: int


class DrainService:
    def __init__(self, *, queue: QueueStore, submit: SubmitService) -> None:
        self._queue = queue
        self._submit = submit

    async def drain(self, *, owner_id: int, session_id: int, character_id: str) -> DrainOutcome:
        queued = await self._queue.list_queued(owner_id=owner_id, session_id=session_id)
        batch: list[QueueItem] = []
        for item in queued[:DRAIN_BATCH_SIZE]:
            if await self._queue.transition(item_id=item.id, from_status="queued", to_status="draining"):
                batch.append(item)
        if not batch:
            return DrainOutcome(False, 0)

        text = "\n\n".join(item.text for item in batch)
        message_ids = [item.message_id for item in batch]
        try:
            turn_id = await self._submit.rerun(owner_id=owner_id, session_id=session_id,
                                               character_id=character_id, text=text, message_ids=message_ids)
        except Exception:
            await self._fail(batch)
            raise
        if turn_id is None:  # 会话正忙：原样放回，等下一次排空
            await self._release(batch)
            return DrainOutcome(False, 0)
        for item in batch:
            await self._queue.transition(item_id=item.id, from_status="draining",
                                         to_status="drained", turn_id=turn_id)
        return DrainOutcome(True, len(batch))

    async def _release(self, batch: list[QueueItem]) -> None:
        for item in batch:
            await self._queue.transition(item_id=item.id, from_status="draining", to_status="queued")

    async def _fail(self, batch: list[QueueItem]) -> None:
        for item in batch:
            # 认领时 drain_attempts 已经 +1（见 SqlQueueStore.transition），这里直接用它判断上限。
            exhausted = item.drain_attempts + 1 >= DRAIN_MAX_ATTEMPTS  # 认领前读到的值，+1 即本次计数
            await self._queue.transition(item_id=item.id, from_status="draining",
                                         to_status="failed" if exhausted else "queued")
