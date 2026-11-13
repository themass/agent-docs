"""记忆编排（chat-agent-memory-hooks.md §5）：扇出、超时隔离、合并、排序、预算裁剪、渲染。

规则对所有来源一致：
1. 所有 Recaller 并发执行，每个有独立超时；超时或失败只影响那一个来源；
2. 按 ``(source, ref)`` 去重；
3. 先按时间降序（缺失的排最后），再按来源内分数降序；**不跨来源比较分数**；
4. 按字符预算从前往后累加，超出即停；
5. 召回为空不是错误，提示词里对应段落直接省略。
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import datetime

#: 记忆写入的后台任务名。回合把写入排进队列，不等它完成。
MEMORY_RECORD_JOB = "memory.record"

from companion.memory.hooks import (
    RecallQuery,
    RecallResult,
    RecallStats,
    RecalledItem,
    Recaller,
    RecordOutcome,
    Recorder,
    TurnRecord,
)

DEFAULT_TIMEOUT_SEC = 0.8
SECTION_TITLES = (("fact", "关于用户"), ("event", "近期事件"))


async def _one(recaller: Recaller, query: RecallQuery, timeout: float) -> RecallResult:
    try:
        return await asyncio.wait_for(recaller.recall(query), timeout=timeout)
    except asyncio.TimeoutError:
        return RecallResult(source=recaller.name, error="timeout")
    except Exception as exc:  # noqa: BLE001 —— 来源失败不影响回合
        return RecallResult(source=recaller.name, error=type(exc).__name__)


def _sort_key(item: RecalledItem) -> tuple[int, float, float]:
    ts = item.occurred_at.timestamp() if isinstance(item.occurred_at, datetime) else float("-inf")
    return (0 if item.occurred_at else 1, -ts, -(item.score if item.score is not None else float("-inf")))


class MemoryPipeline:
    def __init__(self, *, recallers: Sequence[Recaller] = (), recorders: Sequence[Recorder] = (),
                 timeout_sec: float = DEFAULT_TIMEOUT_SEC) -> None:
        self._recallers = tuple(recallers)
        self._recorders = tuple(recorders)
        self._timeout = timeout_sec

    async def recall(self, query: RecallQuery) -> tuple[list[RecalledItem], RecallStats]:
        if not self._recallers:
            return [], RecallStats()
        results = await asyncio.gather(*(_one(r, query, self._timeout) for r in self._recallers))
        seen: set[tuple[str, str]] = set()
        merged: list[RecalledItem] = []
        for result in results:
            for item in result.items:
                key = (item.source, item.ref)
                if key not in seen:
                    seen.add(key)
                    merged.append(item)
        merged.sort(key=_sort_key)

        kept: list[RecalledItem] = []
        used = 0
        truncated = False
        for item in merged:
            if used + len(item.text) > query.budget_chars:
                truncated = True
                break
            kept.append(item)
            used += len(item.text)
        stats = RecallStats(
            per_source={r.source: {"items": len(r.items), "error": r.error} for r in results},
            truncated=truncated or any(r.truncated for r in results),
        )
        return kept, stats

    async def record(self, turn: TurnRecord) -> list[RecordOutcome]:
        outcomes: list[RecordOutcome] = []
        for recorder in self._recorders:
            try:
                outcomes.append(await recorder.record(turn))
            except Exception as exc:  # noqa: BLE001 —— 写入失败不影响已返回的回合
                outcomes.append(RecordOutcome(source=recorder.name, error=type(exc).__name__))
        return outcomes


def render_memory_block(items: Sequence[RecalledItem]) -> str:
    """按标签分段渲染。来源不关心段落结构；没有标签的条目归入第一段。"""
    if not items:
        return ""
    sections: list[str] = []
    used: set[int] = set()
    for tag, title in SECTION_TITLES:
        lines = []
        for index, item in enumerate(items):
            if index in used:
                continue
            if tag in item.tags or (tag == SECTION_TITLES[0][0] and not item.tags):
                lines.append(f"- {item.text}")
                used.add(index)
        if lines:
            sections.append(f"{title}：\n" + "\n".join(lines))
    rest = [f"- {item.text}" for index, item in enumerate(items) if index not in used]
    if rest:
        sections.append("其他：\n" + "\n".join(rest))
    return "\n\n".join(sections)
