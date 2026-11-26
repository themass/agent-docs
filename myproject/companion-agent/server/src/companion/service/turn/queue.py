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


# 默认裁决策略（chat 发送模型，2026-11-26）：回复已开始输出后到达的新消息不再默认插话
# （steered），排队（queued）——当前回复完整跑完，回合收尾后排空成新回合。
# pre_output 的合并不变（「还在想就合并回答」是用户要的行为）。
# STEERED 的枚举、ctl 投递与注入路径全部保留：它是显式能力，接线时（per-skill 或请求级
# 开关）把这个标识翻成 True 即可恢复默认插话。redis_control._SUBMIT_LUA 把同一个值作为
# ARGV 读入，两份实现不会漂移。
DEFAULT_STEER_ENABLED = False


def decide(*, lock_held: bool, phase: TurnPhase, restarts: int, max_restarts: int,
           steerable: bool, steer_used: int, steer_budget: int) -> Disposition:
    if not lock_held:
        return Disposition.STARTED
    if phase is TurnPhase.PRE_OUTPUT and restarts < max_restarts:
        return Disposition.MERGED
    if (phase is TurnPhase.OUTPUT and DEFAULT_STEER_ENABLED and steerable
            and steer_used < steer_budget):
        return Disposition.STEERED
    return Disposition.QUEUED


DRAIN_BATCH_SIZE = 10
DRAIN_MAX_ATTEMPTS = 3
