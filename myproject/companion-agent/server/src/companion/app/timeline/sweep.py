"""每日整理时间线：把已经过去很久、没人处理的一次性事件标为「错过」。

为什么要有：事件没人手动标完成时，状态会一直是 scheduled。召回只取「将来」和「刚过去 2 天」，
所以不会被提起，但记忆页的列表、统计和后面的主动关心都需要一个干净的状态。
纯规则，不调模型；分批执行，直到没有可处理的为止。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

log = logging.getLogger("companion.timeline")

TIMELINE_SWEEP_JOB = "timeline.sweep"
GRACE = timedelta(days=2)    # 与召回的「刚过去」窗口一致：窗口之外才整理
BATCH = 500
MAX_BATCHES = 40             # 一次任务最多处理 2 万条；剩下的下一次接着做


async def sweep_overdue(store: Any, *, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    total = 0
    for _ in range(MAX_BATCHES):
        done = await store.close_overdue(now=now, grace=GRACE, limit=BATCH)
        total += done
        if done < BATCH:
            break
    if total:
        log.info("timeline sweep", extra={"missed": total})
    return total
