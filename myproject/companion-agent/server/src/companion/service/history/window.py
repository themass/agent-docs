"""历史窗口：按回合分组，不截半个回合（P §6.6，评审 m16）。

一个回合 = 它覆盖的全部用户消息（合并或排空时可能有多条）+ 它的助手回复。
工具调用的中间过程不进历史（P §6.6）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HistoryMessage:
    role: str          # "user" | "assistant"
    content: str
    turn_id: str | None


def select_window(messages: list[HistoryMessage], *, max_messages: int = 30, max_chars: int = 12000) -> list[HistoryMessage]:
    """从最新往前取，整回合取舍。返回按时间正序的结果。"""
    groups: list[list[HistoryMessage]] = []
    for msg in messages:
        if groups and msg.turn_id is not None and groups[-1][-1].turn_id == msg.turn_id:
            groups[-1].append(msg)
        else:
            groups.append([msg])

    chosen: list[list[HistoryMessage]] = []
    count = 0
    chars = 0
    for group in reversed(groups):
        size = sum(len(m.content) for m in group)
        if count + len(group) > max_messages or chars + size > max_chars:
            break
        chosen.append(group)
        count += len(group)
        chars += size
    out: list[HistoryMessage] = []
    for group in reversed(chosen):
        out.extend(group)
    return out
