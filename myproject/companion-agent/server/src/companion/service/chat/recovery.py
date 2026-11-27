"""孤儿回合的清扫与重新驱动。

**为什么需要**（2026-11-28 线上，session 39）：进程重启打断一个刚起步的回合后，用户那条
消息永远停在「已提交、没有回复」的状态，端上就是「发了没反应」：

- 回合任务的 Redis 锁 30 秒自己过期（`redis_control.LOCK_TTL_MS`），没人重放、没人重驱动；
- 回合状态哈希 `ca:sess:{sid}:turn` **没有 TTL**，只有 `finish_turn` 会删它 —— 崩溃后它永久残留；
- 全仓没有任何一处读 `ca_chat_turn.state`，索引 `ca_ix_turn_state_started` 建好了却没用过。

**判活看 Redis，不看时间**：回合进程每 10 秒续租锁，丢租就停止产出（`turn_runner._renew`），
所以「锁不在」就是「那个回合已经死了」的确证。

**为什么不能从 `ca_chat_turn` 找候选**：那张表由 `note_turn_models` 在**第一次 LLM 调用之后**
才建行。session 39 的回合是 16:47:45 起步、16:47:51 被打断——一次 LLM 都没跑完，库里**根本没有行**。
按库扫恰好会漏掉真实发生的那一类。所以候选来自 Redis 的回合状态哈希。

判据是确定性的，不靠超时猜测：
- 回合哈希存在 **且** 锁不存在 ⇒ 崩溃/重启留下的孤儿。
- 正常收尾时 `finish_turn` 在一个 pipeline 里先 DEL 哈希、后释放锁，所以「哈希在、锁没了」
  不可能是一次正常收尾的中间态；新回合接手则会先拿锁，锁就在。

**重驱动的边界**：只在「这条回合从没产出过用户可见的助手回复」时重跑——回答过的绝不重复回答。
并发安全靠 `_start` 的 `SET NX`：撞上别的回合就返回 None，本轮跳过。

`message_ids` 取自回合哈希（`init_turn` 在起任务之前就写进去），因此连「挂接输入之前
就被打断」的回合也能救回来——这是从库里按 turn_id 找做不到的。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, select, update

from companion.db.schema import chat_message, chat_turn
from companion.db.sql import _now
from companion.db.port import QueueStore
from companion.service.chat.submit import SubmitService
from companion.service.turn.control import TurnControlPort

log = logging.getLogger("companion.recovery")

# 清扫写进 error_code 的值。不复用 'turn_failed'——那是模型/工具失败，
# 混在一起就分不清「代码出错」和「进程被打断」。
ERROR_CODE = "interrupted"


@dataclass(frozen=True)
class SweepOutcome:
    """一轮清扫的结果。``redriven`` 才是用户真正被救回来的数量。"""

    scanned: int
    closed: int
    redriven: int
    busy: int


class SqlTurnRecoveryStore:
    """恢复用的读/写：按 turn_id 收尾记账，按 message_id 取回输入。

    ``ca_chat_turn`` 的写入方是 ``service/trace/qa.py``（回合汇总）。这里只把它改成终态，
    不承担 QA 语义——两个关注点不同，所以各自持有自己的查询。
    """

    def __init__(self, engine: Any) -> None:
        self._engine = engine

    async def load_inputs(self, *, message_ids: list[int]) -> list[dict[str, Any]]:
        """按 id 取消息行。归属（owner_id）以行上的值为准——不猜。"""
        if not message_ids:
            return []
        async with self._engine.connect() as conn:
            rows = (await conn.execute(
                select(chat_message.c.id, chat_message.c.owner_id, chat_message.c.session_id,
                       chat_message.c.role, chat_message.c.content)
                .where(and_(chat_message.c.id.in_(message_ids),
                            chat_message.c.deleted == False))  # noqa: E712
                .order_by(chat_message.c.id)
            )).mappings().all()
        return [dict(r) for r in rows]

    async def has_assistant_reply(self, *, owner_id: int, session_id: int, turn_id: str) -> bool:
        """这条回合是否已经产出过用户能看到的助手消息。**有就绝不重驱动。**

        ``alt_selected`` 不参与判断：候选回复同样是给用户看过的内容，未选中的那一条
        同样说明这条回合成功回答过。
        """
        async with self._engine.connect() as conn:
            row = (await conn.execute(
                select(chat_message.c.id)
                .where(and_(chat_message.c.turn_id == turn_id,
                            chat_message.c.owner_id == owner_id,
                            chat_message.c.session_id == session_id,
                            chat_message.c.role == "assistant",
                            chat_message.c.deleted == False))  # noqa: E712
                .limit(1)
            )).first()
        return row is not None

    async def close_turn(self, *, turn_id: str) -> bool:
        """条件更新：只有还挂着 running 的行会被改成终态。返回是否真的改了（幂等判据）。"""
        async with self._engine.begin() as conn:
            res = await conn.execute(
                update(chat_turn)
                .where(and_(chat_turn.c.id == turn_id, chat_turn.c.state == "running"))
                .values(state="failed", error_code=ERROR_CODE, finished_at=_now())
            )
        return res.rowcount == 1

    async def role_of_turn(self, *, turn_id: str) -> str:
        """回合行上记的角色（可能没有行，也可能 role_id 为 NULL —— _upsert_turn 写的是 ``or None``）。"""
        async with self._engine.connect() as conn:
            row = (await conn.execute(
                select(chat_turn.c.role_id).where(chat_turn.c.id == turn_id)
            )).first()
        return (row[0] or "") if row else ""


class TurnRecovery:
    """清扫 + 重驱动。一轮 ``sweep()`` 由 jobs 循环按间隔调用。"""

    def __init__(self, *, store: SqlTurnRecoveryStore, control: TurnControlPort,
                 submit: SubmitService, sessions: Any, queue: QueueStore) -> None:
        self._store = store
        self._control = control
        self._submit = submit
        self._sessions = sessions
        # 重驱动撞上「会话正忙」时把输入转成排队。必须有这一手：本方法在重驱动之前
        # 就已经清掉了 Redis 回合状态，下一轮扫描不会再捞到它——不排队就是永久丢失。
        self._queue = queue

    async def sweep(self) -> SweepOutcome:
        orphans = await self._control.orphan_turns()
        closed = redriven = busy = 0
        for orphan in orphans:
            try:
                outcome = await self._one(orphan)
            except Exception:  # noqa: BLE001 —— 一个会话的失败不能让整轮清扫退出
                log.exception("turn recovery failed turn=%s session=%s",
                              orphan.get("turn_id"), orphan.get("session_id"))
                continue
            if outcome is None:
                continue
            closed += 1
            if outcome == "redriven":
                redriven += 1
            elif outcome == "busy":
                busy += 1
        if closed:
            log.warning("turn recovery: %d orphan turn(s) closed, %d redriven, %d deferred (busy)",
                        closed, redriven, busy)
        return SweepOutcome(len(orphans), closed, redriven, busy)

    async def _one(self, orphan: dict[str, Any]) -> str | None:
        session_id = int(orphan["session_id"])
        turn_id = str(orphan["turn_id"])
        message_ids = [int(i) for i in orphan.get("message_ids", []) if str(i).isdigit()]

        if not message_ids:
            # init_turn 一定带 message_ids，走到这里说明哈希被外部改过：只清状态，不猜输入。
            await self._control.clear_turn_if(session_id=session_id, turn_id=turn_id)
            await self._store.close_turn(turn_id=turn_id)
            log.warning("orphan turn %s session=%s has no message_ids — closed, not redriven",
                        turn_id, session_id)
            return "closed"

        rows = await self._store.load_inputs(message_ids=message_ids)
        rows = [r for r in rows if int(r["session_id"]) == session_id and r["role"] == "user"]
        if not rows:
            # 输入行没了（删除或 id 对不上）：清掉残留状态，不做任何重放。
            await self._control.clear_turn_if(session_id=session_id, turn_id=turn_id)
            await self._store.close_turn(turn_id=turn_id)
            log.warning("orphan turn %s session=%s: inputs gone — closed, not redriven",
                        turn_id, session_id)
            return "closed"

        owner_id = int(rows[0]["owner_id"])

        # 已经回答过：只收尾。**不重驱动**——那会让用户看到两遍同样的话。
        if await self._store.has_assistant_reply(owner_id=owner_id, session_id=session_id, turn_id=turn_id):
            await self._control.clear_turn_if(session_id=session_id, turn_id=turn_id)
            await self._store.close_turn(turn_id=turn_id)
            log.info("orphan turn %s session=%s already answered — closed only", turn_id, session_id)
            return "closed"

        character_id = await self._store.role_of_turn(turn_id=turn_id) or await self._role_of(
            owner_id=owner_id, session_id=session_id)
        if not character_id:
            await self._control.clear_turn_if(session_id=session_id, turn_id=turn_id)
            await self._store.close_turn(turn_id=turn_id)
            log.warning("orphan turn %s session=%s: no character_id — closed, not redriven",
                        turn_id, session_id)
            return "closed"

        # 先清 Redis 残留再重驱动：老回合确实死了，这与后面能不能救回来无关；
        # 先清也保证下一轮扫描不会重复捞同一条。
        await self._control.clear_turn_if(session_id=session_id, turn_id=turn_id)
        await self._store.close_turn(turn_id=turn_id)

        new_turn_id = await self._submit.rerun(
            owner_id=owner_id, session_id=session_id, character_id=character_id,
            text="\n\n".join(str(r["content"]) for r in rows),
            message_ids=[int(r["id"]) for r in rows])
        if new_turn_id is None:
            # 会话正忙。回合状态已经清了，下一轮扫描不会再捞到它——所以必须在这里排队，
            # 否则这条输入就没人负责了。排队是既有语义：占场回合收尾后排空会接手。
            for row in rows:
                await self._queue.enqueue(owner_id=owner_id, session_id=session_id,
                                          message_id=int(row["id"]), client_message_id=None,
                                          text=str(row["content"]))
            log.warning("orphan turn %s session=%s: session busy — %d input(s) queued",
                        turn_id, session_id, len(rows))
            return "busy"
        log.warning("redrove orphan turn %s -> %s session=%s inputs=%d",
                    turn_id, new_turn_id, session_id, len(rows))
        return "redriven"

    async def _role_of(self, *, owner_id: int, session_id: int) -> str:
        if self._sessions is None:
            return ""
        record = await self._sessions.get(owner_id=owner_id, session_id=session_id)
        return getattr(record, "role_id", "") or ""
