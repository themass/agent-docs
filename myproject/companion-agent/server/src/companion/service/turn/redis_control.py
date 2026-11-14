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
from collections.abc import Sequence
from typing import Any

from companion.service.turn.queue import Disposition, TurnPhase

# 共用的 Redis：所有键带 ca: 前缀，与 job-come 的 jc:… 区分（不清库、不占用别的 db）。
KEY_PREFIX = "ca:"
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
local ctl = 'ca:turn:' .. tid .. ':ctl'
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
    return f"{KEY_PREFIX}sess:{sid}:turn"


def lock_key(sid: int) -> str:
    return f"{KEY_PREFIX}sess:{sid}:lock"


def fence_key(sid: int) -> str:
    return f"{KEY_PREFIX}sess:{sid}:fence"


def ctl_key(tid: str) -> str:
    return f"{KEY_PREFIX}turn:{tid}:ctl"


def text_key(tid: str) -> str:
    return f"{KEY_PREFIX}turn:{tid}:text"


def events_key(sid: int) -> str:
    return f"{KEY_PREFIX}sess:{sid}:events"


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

    async def next_fence(self, *, session_id: int) -> int:
        """单调递增的围栏号。拿到锁之后取一次，随回合传递；写回复时按它做条件写。"""
        return int(await self._r.incr(fence_key(session_id)))

    # ---- 回合状态 ----

    async def init_turn(self, *, session_id: int, turn_id: str, message_ids: list[int] | None = None) -> None:
        await self._r.hset(turn_key(session_id), mapping={
            "turn_id": turn_id, "phase": TurnPhase.PRE_OUTPUT.value,
            "restarts": 0, "steer_used": 0,
            "message_ids": ",".join(str(i) for i in (message_ids or [])),
        })

    async def advance_phase(self, *, session_id: int, phase: TurnPhase) -> bool:
        return bool(await self._phase(keys=[turn_key(session_id)], args=[phase.value]))

    async def set_phase(self, *, session_id: int, phase: TurnPhase) -> None:
        """只允许回合进程自己撤销（首 token 前的合并被发现后，阶段要退回 pre_output）。"""
        await self._r.hset(turn_key(session_id), "phase", phase.value)

    async def clear_turn(self, *, session_id: int) -> None:
        await self._r.delete(turn_key(session_id))

    async def finish_turn(self, *, session_id: int, owner: str, turn_id: str, event: str,
                          data: dict[str, Any]) -> None:
        """回合收尾：发布最后一个事件、删回合状态、释放锁，**一次往返**。

        这三件事原本是三次串行 Redis 往返（各 180 ms 量级）。顺序是硬约束：
        1. 事件要先发出去——客户端靠它知道回合结束；
        2. 回合状态必须在放锁之前删——否则锁一放开，下一个回合就可能已经写好了
           turn hash，而那之后才执行的 DEL 会把新回合的状态删掉；
        3. 最后才释放锁。
        pipeline 按注册顺序执行，三条命令之间没有其它连接能插进来，所以顺序不变；
        而释放锁的判定仍在 Lua 里做（只删属于自己的那把），不会误删别人的锁。
        """
        pipe = self._r.pipeline(transaction=False)
        pipe.xadd(events_key(session_id),
                  {"event": event, "data": json.dumps(data, ensure_ascii=False)},
                  maxlen=EVENTS_MAXLEN, approximate=True)
        pipe.expire(events_key(session_id), 30 * 60)
        pipe.delete(turn_key(session_id))
        self._release(client=pipe, keys=[lock_key(session_id)], args=[owner])
        await pipe.execute()

    # ---- 控制流（回合所在进程读取）----

    async def read_ctl(self, *, turn_id: str, last_id: str, block_ms: int = 1000) -> list[tuple[str, dict[str, str]]]:
        res = await self._r.xread({ctl_key(turn_id): last_id}, count=50, block=block_ms)
        out: list[tuple[str, dict[str, str]]] = []
        for _stream, entries in res or []:
            for entry_id, fields in entries:
                out.append((_s(entry_id), {_s(k): _s(v) for k, v in fields.items()}))
        return out

    async def read_ctl_after(self, *, turn_id: str, last_id: str) -> list[tuple[str, dict[str, str]]]:
        """非阻塞读取 last_id 之后的控制消息（首 token 前的同步检查用）。"""
        start = "-" if last_id in ("0", "0-0") else f"({last_id}"
        res = await self._r.xrange(ctl_key(turn_id), min=start, count=100)
        return [(_s(entry_id), {_s(k): _s(v) for k, v in fields.items()}) for entry_id, fields in res]

    async def send_cancel(self, *, turn_id: str) -> None:
        await self._r.xadd(ctl_key(turn_id), {"kind": "cancel"}, maxlen=100, approximate=True)

    # ---- 正文缓冲（首连快照与崩溃回收用）----

    async def append_text(self, *, turn_id: str, delta: str) -> None:
        # pipeline 而不是两条独立命令：托管 Redis 的单命令往返实测 193 ms
        # （应用机与库不在同一机房），两条串行就是 386 ms，而每一次 flush 都要走这里。
        # APPEND + EXPIRE 合并成一次往返，语义完全一样。
        pipe = self._r.pipeline(transaction=False)
        pipe.append(text_key(turn_id), delta)
        pipe.expire(text_key(turn_id), 3600)
        await pipe.execute()

    async def read_text(self, *, turn_id: str) -> str:
        raw = await self._r.get(text_key(turn_id))
        return _s(raw) if raw else ""

    # ---- 对外事件流（SSE 数据源）----

    async def publish(self, *, session_id: int, event: str, data: dict[str, Any]) -> str:
        # XADD + EXPIRE 合并为一次往返（理由同 append_text）。
        pipe = self._r.pipeline(transaction=False)
        pipe.xadd(events_key(session_id),
                  {"event": event, "data": json.dumps(data, ensure_ascii=False)},
                  maxlen=EVENTS_MAXLEN, approximate=True)
        pipe.expire(events_key(session_id), 30 * 60)
        entry_id, _ = await pipe.execute()
        return _s(entry_id)

    async def publish_many(self, *, session_id: int, events: Sequence[tuple[str, dict[str, Any]]]) -> list[str]:
        """一次往返发多条事件。

        每条仍是**独立的 stream entry、各自递增的 id**——不能折成一条：客户端的去重用
        ``<=`` 丢弃（`AgentChatState.kt` 的 ``isDuplicate``），合并成一条之后第二条会被
        永久吞掉，断线续传也找不回来（续传从 ``Last-Event-ID`` 严格之后开始）。

        pipeline 里按顺序 XADD，所以顺序与逐条调用等价；只把往返次数从 N 降到 1。
        """
        if not events:
            return []
        pipe = self._r.pipeline(transaction=False)
        for event, data in events:
            pipe.xadd(events_key(session_id),
                      {"event": event, "data": json.dumps(data, ensure_ascii=False)},
                      maxlen=EVENTS_MAXLEN, approximate=True)
        pipe.expire(events_key(session_id), 30 * 60)
        results = await pipe.execute()
        # 最后一条结果是 expire() 的，前面都是各 XADD 的 id。
        return [_s(entry_id) for entry_id in results[:-1]]

    async def publish_and_append(self, *, session_id: int, turn_id: str, event: str,
                                 data: dict[str, Any], delta: str) -> str:
        """``message.delta`` 的专用路径：正文追加与事件发布合并成**一次**往返。

        流式输出时每帧都要做这两件事。以前是 4 条串行命令（APPEND、EXPIRE、XADD、EXPIRE），
        在这台托管 Redis 上实测一次 flush 1385 ms；合并后 168 ms。
        一回合 27 帧的话，差别是 37 秒和 4.5 秒——用户等的是前者。
        """
        pipe = self._r.pipeline(transaction=False)
        pipe.append(text_key(turn_id), delta)
        pipe.expire(text_key(turn_id), 3600)
        pipe.xadd(events_key(session_id),
                  {"event": event, "data": json.dumps(data, ensure_ascii=False)},
                  maxlen=EVENTS_MAXLEN, approximate=True)
        pipe.expire(events_key(session_id), 30 * 60)
        _, _, entry_id, _ = await pipe.execute()
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

    async def purge_session(self, *, session_id: int) -> None:
        """注销用：取消进行中的回合，删掉会话的锁、回合状态、围栏与事件流。

        锁被删后，进行中的回合下一次续租失败就会停止；它的回复写入也会因为会话围栏已推进而被拒。
        """
        raw = await self._r.hgetall(turn_key(session_id))
        tid = _s(raw.get(b"turn_id") or raw.get("turn_id") or "") if raw else ""
        if tid:
            await self.send_cancel(turn_id=tid)
        keys = [turn_key(session_id), lock_key(session_id), fence_key(session_id), events_key(session_id)]
        if tid:
            keys += [ctl_key(tid), text_key(tid)]
        await self._r.delete(*keys)

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
