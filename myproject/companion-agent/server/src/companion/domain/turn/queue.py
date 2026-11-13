"""回合状态机与处置规则（D §6、§3.3）。纯逻辑，无 I/O。

同一套规则在 Redis Lua 脚本里原子执行（adapters/cache/redis/control.py）；
这里是可读的参考实现，两者必须保持一致（T13 的契约测试对比它们）。
"""

from __future__ import annotations

from enum import Enum


class Disposition(str, Enum):
    STARTED = "started"
    MERGED = "merged"
    STEERED = "steered"
    QUEUED = "queued"


class TurnPhase(str, Enum):
    NONE = "none"
    PRE_OUTPUT = "pre_output"   # 还没有可见 token，也没有执行过工具
    OUTPUT = "output"           # 已产出可见正文
    TOOL = "tool"               # 执行过工具：有副作用，之后禁止合并（D §6.3）


def decide(*, lock_held: bool, phase: TurnPhase, restarts: int, max_restarts: int,
           steerable: bool, steer_used: int, steer_budget: int) -> Disposition:
    if not lock_held:
        return Disposition.STARTED
    if phase is TurnPhase.PRE_OUTPUT and restarts < max_restarts:
        return Disposition.MERGED
    if phase is TurnPhase.OUTPUT and steerable and steer_used < steer_budget:
        return Disposition.STEERED
    return Disposition.QUEUED


# 队列状态转移（D §3.3）。其余一律非法。
QUEUE_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    ("queued", "draining"), ("draining", "drained"),
    ("queued", "merged"), ("queued", "steered"), ("queued", "withdrawn"), ("queued", "dropped"),
    ("steered", "queued"),
    ("draining", "queued"), ("draining", "failed"), ("failed", "queued"),
})

DRAIN_BATCH_SIZE = 10
DRAIN_MAX_ATTEMPTS = 3
