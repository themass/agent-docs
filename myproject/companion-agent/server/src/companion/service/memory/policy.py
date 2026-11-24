"""窄记忆的确定性策略层（P6）。纯函数，无 I/O——存储复用 agent/memory（ca_memory_item）。

三件事都能被用户一句话讲明白，这是刻意约束（设计参照 AIRI 记忆 ADR，按确定性起步）：

- ``select_index``：往提示词里挑哪几条。kind 有优先级（PREFERENCE > EVENT > FACT），
  组内新在前；条目数与字符数双预算，装不下的跳过而不是截断。
- ``dedupe_same_content``：同一句话（去空白后相同）只留最新一条。
- ``plan_forgetting``：超过容量时忘最旧的；未超保护期的 PREFERENCE 排到最后被忘。

``build_context`` 是给 prompt 组装的注入接口：卡在前、记忆在后，返回 list[str]。
接线在主线（挂点见 service/chat/context.py 与 agent/prompt/roleplay.py，笔记里有写明）。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta

from companion.agent.memory.port import MemoryItem, MemoryKind
from companion.service.card.model import render_card_lines

# 选取与淘汰用的 kind 优先级：数字小者优先进入紧凑索引、最后被忘。
_KIND_PRIORITY: dict[MemoryKind, int] = {
    MemoryKind.PREFERENCE: 0,
    MemoryKind.EVENT: 1,
    MemoryKind.FACT: 2,
}

DEFAULT_MAX_ENTRIES = 12
DEFAULT_MAX_CHARS = 1200
DEFAULT_PROTECT_DAYS = 30


def _newest_first(items: Iterable[MemoryItem]) -> list[MemoryItem]:
    return sorted(items, key=lambda i: (i.created_at, i.id), reverse=True)


def select_index(items: Sequence[MemoryItem], *, max_entries: int = DEFAULT_MAX_ENTRIES,
                 max_chars: int = DEFAULT_MAX_CHARS) -> list[MemoryItem]:
    """挑进紧凑索引的条目：kind 优先级 → 组内新在前；双预算内装谁。

    返回按展示顺序（新在前）排好的列表；超预算的条目**跳过**（截断一条事实会歪曲它）。
    """
    ranked = sorted(items, key=lambda i: (_KIND_PRIORITY.get(i.kind, 9), -i.created_at.timestamp(), i.id))
    chosen: list[MemoryItem] = []
    used = 0
    for item in ranked:
        if len(chosen) >= max_entries:
            break
        if used + len(item.content) > max_chars:
            continue
        chosen.append(item)
        used += len(item.content)
    return chosen


def dedupe_same_content(items: Sequence[MemoryItem]) -> list[MemoryItem]:
    """去空白后内容相同的条目只保留最新的一条（其余等价，旧的没有信息量）。"""
    best: dict[str, MemoryItem] = {}
    for item in items:
        key = item.content.strip()
        current = best.get(key)
        if current is None or (item.created_at, item.id) > (current.created_at, current.id):
            best[key] = item
    return _newest_first(best.values())


def plan_forgetting(items: Sequence[MemoryItem], *, max_entries: int,
                    now: datetime | None = None,
                    protect_days: int = DEFAULT_PROTECT_DAYS) -> list[MemoryItem]:
    """超出容量时要忘掉（delete_one 级别）的条目。

    规则：最旧者优先忘；PREFERENCE 在保护期（默认 30 天）内不主动忘——用户说的偏好
    被悄悄删掉是最伤体验的失效。全部都在保护期内且仍超容量时，按最旧继续收敛（容量是硬约束）。
    """
    if len(items) <= max_entries:
        return []
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=protect_days)

    def rank(item: MemoryItem) -> tuple[int, float]:
        # 第一维：受保护的 PREFERENCE 排后（更不易被忘）；第二维：越旧越先被忘。
        protected = item.kind is MemoryKind.PREFERENCE and item.created_at >= cutoff
        return (1 if protected else 0, item.created_at.timestamp())

    order = sorted(items, key=rank)
    return order[: len(items) - max_entries]


def build_context(*, card_fields: dict, memory_items: Sequence[MemoryItem],
                  max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    """注入接口：角色卡（active version 合并后）+ 紧凑记忆索引 → 提示词条目行。

    顺序固定：卡在前（身份/边界是「她是谁」），记忆在后（「她知道你什么」）。
    预算先给卡，剩余给记忆——卡被记忆挤掉是不可接受的失效，反之只是少记一件事。
    返回可直接拼进 system prompt 的 list[str]（与 render_card_lines 同形状）。
    """
    lines = list(render_card_lines(card_fields))
    used = sum(len(line) + 1 for line in lines)
    room = max(max_chars - used, 0)
    for item in select_index(memory_items, max_chars=room):
        line = f"- {item.content.strip()}"
        if used + len(line) + 1 > max_chars:
            break
        lines.append(line)
        used += len(line) + 1
    return lines
