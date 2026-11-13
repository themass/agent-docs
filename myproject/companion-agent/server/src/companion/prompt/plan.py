"""一次回合的提示词计划（纯数据 + 纯函数）。

上下文分工（chat-agent-next-plan.md §2.2）：
- 对话历史由大脑的 checkpoint 提供，这里不拼历史；
- 这里只产出「这一轮要加在历史外面的东西」：系统提示词，以及按深度插进历史的注入
  （角色备注、世界书 @深度 条目、作者注、历史后指令）。注入只进本次请求，不写回 checkpoint。

深度的含义与 SillyTavern 一致：0 = 最后一条消息之后；N = 倒数第 N 条消息之前。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

from companion.lorebook.model import ROLES, DepthInjection

T = TypeVar("T")


@dataclass(frozen=True)
class PromptPlan:
    system: str
    injections: tuple[DepthInjection, ...] = ()
    version: str = ""
    lore_uids: tuple[str, ...] = ()      # 本轮激活的世界书条目（排查用，不含正文）
    dropped: tuple[str, ...] = ()        # 因预算放不下而丢掉的可选块
    skills: tuple[str, ...] = ()         # 本轮提示词里用到的 skill（含常驻），质检用


def splice_injections(messages: Sequence[T], injections: Sequence[DepthInjection],
                      make: Callable[[str, str], T]) -> list[T]:
    """把注入插进消息列表，返回新列表（不改原列表）。

    同一深度：按 order 从高到低分组；每组内按 system → user → assistant 各合并成一条。
    深度超过消息数时插在最前面。
    """
    if not injections:
        return list(messages)
    by_depth: dict[int, list[DepthInjection]] = {}
    for inj in injections:
        if inj.text.strip():
            by_depth.setdefault(inj.depth, []).append(inj)

    out = list(messages)
    n = len(out)
    # 从后往前插，前面的下标不受影响。
    for depth in sorted(by_depth, key=lambda d: n - min(d, n), reverse=True):
        index = n - min(depth, n)
        block: list[T] = []
        orders = sorted({i.order for i in by_depth[depth]}, reverse=True)
        for order in orders:
            group = [i for i in by_depth[depth] if i.order == order]
            for role in ROLES:
                texts = [i.text.strip() for i in group if i.role == role]
                if texts:
                    block.append(make(role, "\n\n".join(texts)))
        out[index:index] = block
    return out
