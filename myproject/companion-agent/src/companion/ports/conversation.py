"""大脑对话线程的状态（模型的工作上下文）。

分工（chat-agent-next-plan.md §2.2）：消息表管原始内容与界面；对话线程管模型看到的最近消息与摘要。
编辑、删除、重新生成必须两边一起改，这个端口是改线程的唯一入口。

消息 id 约定：用户消息 = ``lc_user_id(message_id)``；助手消息 = 回合里大脑报告的 id
（记在助手消息 ``meta["lc_ids"]``）；中断回复的补记 = ``lc_assistant_id(message_id)``。
所有写操作都必须在持有会话锁时调用。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


def lc_user_id(message_id: int) -> str:
    return f"m{message_id}"


def lc_assistant_id(message_id: int) -> str:
    return f"a{message_id}"


def message_id_of(lc_id: str) -> int | None:
    """``m123`` / ``a123`` → 123；大脑自己生成的 id 返回 None。"""
    if len(lc_id) > 1 and lc_id[0] in "ma" and lc_id[1:].isdigit():
        return int(lc_id[1:])
    return None


class ConversationStatePort(Protocol):
    async def present_ids(self, *, session_id: int) -> list[str]:
        """线程里现有的消息 id，按顺序。被摘要压缩掉的消息不在其中。"""
        ...

    async def remove(self, *, session_id: int, ids: Sequence[str]) -> int:
        """移除这些 id（不在线程里的忽略），返回实际移除的条数。"""
        ...

    async def replace_user_text(self, *, session_id: int, lc_id: str, text: str) -> bool:
        """替换一条用户消息的正文；不在线程里返回 False。"""
        ...

    async def append_assistant(self, *, session_id: int, lc_id: str, text: str) -> None:
        """补记一条助手消息（例如被中断的回复），让模型知道上一句说到了哪里。"""
        ...

    async def reset(self, *, session_id: int) -> int:
        """清空整个线程（含摘要），返回清掉的条数。用户「清空历史」时用：
        只清消息表不在这里清，模型下次回复还会引用被清掉的内容。"""
        ...

    async def summary(self, *, session_id: int) -> str: ...

    async def set_summary(self, *, session_id: int, text: str) -> None: ...
