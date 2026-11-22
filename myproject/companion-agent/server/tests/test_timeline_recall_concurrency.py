"""TimelineRecaller 的两笔读取必须并发：异地库上串行必然超 0.8s 召回预算。

生产证据（2026-11-22 stage-2，voice=main f3d8ae7，**暖进程** pid 387795 130 回合）：
timeline 超时 80/127≈63%——与冷 import 无关（同进程 facts 已从全灭回到 19%）。
`_auto` 注释早就写明异地 PG 一次事务三往返 ~550ms；autocommit 后单查询一个往返，
而 `recall()` 把 upcoming 和 recent_past **串行** await：两次往返 + 连接池等待
 routinely >800ms（MemoryPipeline.DEFAULT_TIMEOUT_SEC）。串行是结构性的，
重启/预热都救不了——只并发化这两笔，不动 0.8s 预算（那是合理的首句延迟上限）。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from companion.agent.memory.hooks import RecallQuery
from companion.agent.memory.recallers import TimelineRecaller
from companion.service.timeline.models import EventKind, TimelineEvent


class _SlowTimeline:
    """每次读取都要 60ms 的时间线；记录是否出现两笔读同时在飞。"""

    READ_MS = 60

    def __init__(self) -> None:
        self.inflight = 0
        self.max_inflight = 0

    async def _read(self) -> list[TimelineEvent]:
        self.inflight += 1
        self.max_inflight = max(self.max_inflight, self.inflight)
        try:
            await asyncio.sleep(self.READ_MS / 1000)
        finally:
            self.inflight -= 1
        return []

    async def upcoming(self, **kw):  # noqa: ANN003, ANN001
        return await self._read()

    async def recent_past(self, **kw):  # noqa: ANN003, ANN001
        return await self._read()


async def test_upcoming_and_recent_past_run_concurrently() -> None:
    timeline = _SlowTimeline()
    recaller = TimelineRecaller(timeline)
    query = RecallQuery(user_id="7", scope="companion", text="", role_id="linche")

    t0 = asyncio.get_event_loop().time()
    result = await recaller.recall(query)
    elapsed = asyncio.get_event_loop().time() - t0

    assert result.error is None
    # 串行 = 2×60ms；并发 = ~60ms。阈值取 1.5×，两边都有余量。
    assert timeline.max_inflight == 2, "两笔读没有同时在飞（串行 await）"
    assert elapsed < _SlowTimeline.READ_MS * 1.5 / 1000, f"耗时 {elapsed * 1000:.0f}ms，仍接近串行"


async def test_concurrent_recall_still_filters_by_role() -> None:
    """并发化不许丢按角色隔离：两笔读都必须带同一个 role。"""
    seen: list[dict] = []

    class _RecordingTimeline:
        async def upcoming(self, **kw):  # noqa: ANN003, ANN001
            seen.append({"fn": "upcoming", **kw})
            return []

        async def recent_past(self, **kw):  # noqa: ANN003, ANN001
            seen.append({"fn": "recent_past", **kw})
            return []

    now = datetime.now(UTC)
    result = await TimelineRecaller(_RecordingTimeline(), clock=lambda: now).recall(
        RecallQuery(user_id="7", scope="companion", text="", role_id="linche"))
    assert result.error is None
    assert {s["fn"] for s in seen} == {"upcoming", "recent_past"}
    assert all(s["role_id"] == "linche" and s["owner_id"] == "7" for s in seen)
