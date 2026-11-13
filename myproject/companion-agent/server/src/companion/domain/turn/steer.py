"""steer 收件箱：回合所在进程内的待注入消息（D §6.4）。

跨进程的消息由控制协程（T5）写进这里；SteerMiddleware 在每次模型调用前取走。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SteerInbox:
    budget: int = 3                       # 一个回合最多注入几次（D §6.4）
    injected: int = 0
    _items: list[tuple[str, str]] = field(default_factory=list)   # (message_id, text)

    def push(self, message_id: str, text: str) -> None:
        self._items.append((message_id, text))

    def take_all(self) -> list[tuple[str, str]]:
        """取走所有待注入项。超过预算时不再注入，留给回合结束时转回队列。"""
        if not self._items or self.injected >= self.budget:
            return []
        items, self._items = self._items, []
        self.injected += 1
        return items

    def remaining(self) -> list[tuple[str, str]]:
        """回合结束时仍未注入的项：调用方负责把它们转回队列（D §6.4）。"""
        items, self._items = self._items, []
        return items


def render_steer_block(items: list[tuple[str, str]]) -> str:
    """把注入的消息渲染成定界块。内容按数据处理，不是指令（与排队块一致）。"""
    lines = [
        "<followups-while-busy>",
        "The following messages arrived while you were still answering. Take them into account in your next reply:",
    ]
    for idx, (_mid, text) in enumerate(items, start=1):
        lines.append(f"{idx}. {text}")
    lines.append("</followups-while-busy>")
    return "\n".join(lines)
