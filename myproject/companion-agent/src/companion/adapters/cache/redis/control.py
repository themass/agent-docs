"""回合控制面（D §6.2）。所有跨进程的协调都经过这里。

键：
- sess:{sid}:turn   hash：turn_id、phase、restarts、steer_used
- sess:{sid}:lock   string：持有者 "{process}:{turn_id}"，SET NX PX，每 10 秒续租
- turn:{tid}:ctl    stream：merge / steer / cancel 控制消息（回合所在进程读取）
- turn:{tid}:text   string：已产出正文，APPEND
- sess:{sid}:events stream：对外事件（SSE 的数据源）

判定与投递在同一个 Lua 脚本里原子完成（D §6.2）：读 phase，决定处置，写控制流。
这样不会出现「判定时还是 pre_output，投递时已经开始吐字」的竞态。

注意：Lua 脚本内动态拼接键名（turn:{tid}:ctl）只在单节点 Redis 上安全；
多节点/集群部署前需要改为同一哈希槽（{sid} 标签）。这是已知约束，写进 T13。
"""

from __future__ import annotations

import json
from typing import Any

from companion.domain.turn.queue import Disposition, TurnPhase

LOCK_TTL_MS = 30_000
EVENTS_MAXLEN = 5_000

_SUBMIT_LUA = """
local turn, lock = KEYS[1], KEYS[2]
local mid, steerable, text = ARGV[1], ARGV[2], ARGV[5]
local steer_budget, max_restarts = tonumber(ARGV[3]), tonumber(ARGV[4])
if redis.call('EXISTS', lock) == 0 then
  return {'started', ''}
end
local phase = redis.call('HGET', turn, 'phase') or 'none'
local tid = redis.call('HGET', turn, 'turn_id') or ''
local restarts = tonumber(redis.call('HGET', turn, 'restarts') or '0')
local used = tonumber(redis.call('HGET', turn, 'steer_used') or '0')
local ctl = 'turn:' .. tid .. ':ctl'
if phase == 'pre_output' and restarts < max_restarts then
  redis.call('HINCRBY', turn, 'restarts', 1)
  redis.call('XADD', ctl, '*', 'kind', 'merge', 'message_id', mid, 'text', text)
  return {'merged', tid}
end
if phase == 'output' and steerable == '1' and used < steer_budget then
  redis.call('HINCRBY', turn, 'steer_used', 1)
  redis.call('XADD', ctl, '*', 'kind', 'steer', 'message_id', mid, 'text', text)
  return {'steered', tid}
end
return {'queued', tid}
"""

# 阶段只能前进：none -> pre_output -> output|tool；output -> tool。绝不回退（否则会允许已产出内容后的合并）。
_PHASE_LUA = """
local turn, new = KEYS[1], ARGV[1]
local rank = {none=0, pre_output=1, output=2, tool=3}
local cur = redis.call('HGET', turn, 'phase') or 'none'
if rank[new] > rank[cur] then
  redis.call('HSET', turn, 'phase', new)
  return 1
end
return 0
"""

_RELEASE_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""

_RENEW_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('PEXPIRE', KEYS[1], ARGV[2])
end
return 0
"""


def turn_key(sid: int) -> str:
    return f"sess:{sid}:turn"


def lock_key(sid: int) -> str:
    return f"sess:{sid}:lock"


def ctl_key(tid: str) -> str:
    return f"turn:{tid}:ctl"


def text_key(tid: str) -> str:
    return f"turn:{tid}:text"


def events_key(sid: int) -> str:
    return f"sess:{sid}:events"


class RedisTurnControl:
    def __init__(self, redis: Any) -> None:
        self._r = redis
        self._submit = redis.register_script(_SUBMIT_LUA)
        self._phase = redis.register_script(_PHASE_LUA)
        self._release = redis.register_script(_RELEASE_LUA)
        self._renew = redis.register_script(_RENEW_LUA)

    # ---- 判定（submit 用）----

    async def decide(self, *, session_id: int, message_id: str, text: str, steerable: bool,
                     steer_budget: int, max_restarts: int) -> tuple[Disposition, str]:
        status, tid = await self._submit(
            keys=[turn_key(session_id), lock_key(session_id)],
            args=[message_id, "1" if steerable else "0", steer_budget, max_restarts, text],
        )
        status = status.decode() if isinstance(status, bytes) else status
        tid = tid.decode() if isinstance(tid, bytes) else tid
        return Disposition(status), tid

    # ---- 锁（每 10 秒续租，D §6.2）----

    async def acquire_lock(self, *, session_id: int, owner: str) -> bool:
        return bool(await self._r.set(lock_key(session_id), owner, nx=True, px=LOCK_TTL_MS))

    async def renew_lock(self, *, session_id: int, owner: str) -> bool:
        return bool(await self._renew(keys=[lock_key(session_id)], args=[owner, LOCK_TTL_MS]))

    async def release_lock(self, *, session_id: int, owner: str) -> None:
        await self._release(keys=[lock_key(session_id)], args=[owner])

    # ---- 回合状态 ----

    async def init_turn(self, *, session_id: int, turn_id: str, message_ids: list[int] | None = None) -> None:
        await self._r.hset(turn_key(session_id), mapping={
            "turn_id": turn_id, "phase": TurnPhase.PRE_OUTPUT.value,
            "restarts": 0, "steer_used": 0,
            "message_ids": ",".join(str(i) for i in (message_ids or [])),
        })

    async def advance_phase(self, *, session_id: int, phase: TurnPhase) -> bool:
        return bool(await self._phase(keys=[turn_key(session_id)], args=[phase.value]))

    async def clear_turn(self, *, session_id: int) -> None:
        await self._r.delete(turn_key(session_id))

    # ---- 控制流（回合所在进程读取）----

    async def read_ctl(self, *, turn_id: str, last_id: str, block_ms: int = 1000) -> list[tuple[str, dict[str, str]]]:
        res = await self._r.xread({ctl_key(turn_id): last_id}, count=50, block=block_ms)
        out: list[tuple[str, dict[str, str]]] = []
        for _stream, entries in res or []:
            for entry_id, fields in entries:
                out.append((_s(entry_id), {_s(k): _s(v) for k, v in fields.items()}))
        return out

    async def send_cancel(self, *, turn_id: str) -> None:
        await self._r.xadd(ctl_key(turn_id), {"kind": "cancel"}, maxlen=100, approximate=True)

    # ---- 正文缓冲（首连快照与崩溃回收用）----

    async def append_text(self, *, turn_id: str, delta: str) -> None:
        await self._r.append(text_key(turn_id), delta)
        await self._r.expire(text_key(turn_id), 3600)

    async def read_text(self, *, turn_id: str) -> str:
        raw = await self._r.get(text_key(turn_id))
        return _s(raw) if raw else ""

    # ---- 对外事件流（SSE 数据源）----

    async def publish(self, *, session_id: int, event: str, data: dict[str, Any]) -> str:
        entry_id = await self._r.xadd(
            events_key(session_id),
            {"event": event, "data": json.dumps(data, ensure_ascii=False)},
            maxlen=EVENTS_MAXLEN, approximate=True,
        )
        await self._r.expire(events_key(session_id), 30 * 60)
        return _s(entry_id)

    async def read_events_after(self, *, session_id: int, after_id: str, count: int = 100) -> list[tuple[str, str, dict]]:
        start = "-" if after_id in ("0", "0-0") else f"({after_id}"
        res = await self._r.xrange(events_key(session_id), min=start, count=count)
        return _parse_events(res)

    async def wait_events(self, *, session_id: int, after_id: str, block_ms: int) -> list[tuple[str, str, dict]]:
        res = await self._r.xread({events_key(session_id): after_id}, count=100, block=block_ms)
        out: list[tuple[str, str, dict]] = []
        for _stream, entries in res or []:
            out.extend(_parse_events(entries))
        return out

    async def active_turn(self, *, session_id: int) -> dict[str, str] | None:
        if not await self._r.exists(lock_key(session_id)):
            return None
        raw = await self._r.hgetall(turn_key(session_id))
        parsed = {_s(k): _s(v) for k, v in raw.items()} if raw else {}
        return parsed if parsed.get("turn_id") else None

    async def tail_event_id(self, *, session_id: int) -> str:
        res = await self._r.xrevrange(events_key(session_id), count=1)
        return _s(res[0][0]) if res else "0-0"

    async def oldest_event_id(self, *, session_id: int) -> str:
        res = await self._r.xrange(events_key(session_id), count=1)
        return _s(res[0][0]) if res else "0-0"


def _parse_events(entries: list) -> list[tuple[str, str, dict]]:
    out = []
    for entry_id, fields in entries:
        f = {_s(k): _s(v) for k, v in fields.items()}
        out.append((_s(entry_id), f["event"], json.loads(f["data"])))
    return out


def _s(v: Any) -> str:
    return v.decode() if isinstance(v, bytes) else str(v)
