"""世界书扫描：选出本轮激活的条目。

第一版算法（无递归）：
1. 候选 = 启用的条目中，常驻的，或主关键词任一命中、且次关键词满足逻辑的；
2. 按顺序号从高到低占用预算（顺序号越大越重要）；放不下的记为丢弃；
3. 输出按顺序号从低到高（顺序号大的离对话更近）。

扫描文本由调用方给出：最近几条消息，最新在前。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from companion.lorebook.model import LoreEntry, Lorebook
from companion.lorebook.text import matches, normalize


@dataclass(frozen=True)
class Activation:
    entries: tuple[LoreEntry, ...]     # 已按输出顺序排列
    dropped: tuple[str, ...]           # 因预算丢弃的 uid


def _secondary_ok(entry: LoreEntry, text: str) -> bool:
    if not entry.secondary_keys:
        return True
    hits = [matches(k, text, case_sensitive=entry.case_sensitive, whole_word=entry.whole_word)
            for k in entry.secondary_keys]
    if entry.logic == "and_any":
        return any(hits)
    if entry.logic == "and_all":
        return all(hits)
    if entry.logic == "not_any":
        return not any(hits)
    return not all(hits)  # not_all


def _scan_text(recent_texts: Sequence[str], depth: int, case_sensitive: bool) -> str:
    return normalize("\n".join(recent_texts[:max(1, depth)]), case_sensitive=case_sensitive)


def activate(book: Lorebook | None, recent_texts: Sequence[str], *, budget_chars: int) -> Activation:
    if book is None or not book.entries:
        return Activation((), ())
    budget = min(budget_chars, book.budget_chars) if book.budget_chars else budget_chars

    texts: dict[tuple[int, bool], str] = {}
    candidates: list[LoreEntry] = []
    for entry in book.entries:
        if not entry.enabled:
            continue
        if entry.constant:
            candidates.append(entry)
            continue
        if not entry.keys:
            continue
        key = (entry.scan_depth or book.scan_depth, entry.case_sensitive)
        if key not in texts:
            texts[key] = _scan_text(recent_texts, key[0], entry.case_sensitive)
        text = texts[key]
        primary = any(matches(k, text, case_sensitive=entry.case_sensitive, whole_word=entry.whole_word)
                      for k in entry.keys)
        if primary and _secondary_ok(entry, text):
            candidates.append(entry)

    chosen: list[LoreEntry] = []
    dropped: list[str] = []
    used = 0
    for entry in sorted(candidates, key=lambda e: e.order, reverse=True):
        size = len(entry.content)
        if used + size > budget:
            dropped.append(entry.uid)
            continue
        used += size
        chosen.append(entry)
    chosen.sort(key=lambda e: e.order)
    return Activation(tuple(chosen), tuple(dropped))
