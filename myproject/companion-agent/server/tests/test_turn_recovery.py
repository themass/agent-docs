"""孤儿回合的判定与重新驱动（service/chat/recovery.py）。

判活的依据是 Redis 里「回合状态哈希在、锁没了」这个组合，所以核心几个用例跑真 Redis
（和 tests/test_turn_redis.py 同一个约定：设 COMPANION_TEST_REDIS_URL 才跑）。
用假的 control 只会把我对 Redis 行为的假设重述一遍，证不出任何东西——
尤其是 `orphan_turns` 的键解析（`ca:sess:39:turn` 里前缀本身含冒号）。
"""

import os
import random
from dataclasses import dataclass, field
from typing import Any

import pytest
from sqlalchemy import insert

from companion.db.schema import chat_message, chat_turn
from companion.service.chat.recovery import SqlTurnRecoveryStore, TurnRecovery

REDIS_URL = os.environ.get("COMPANION_TEST_REDIS_URL", "")


def _session_id() -> int:
    return random.randint(10**9, 10**10)


# ---------------------------------------------------------------- Redis：判活

@pytest.fixture
async def redis_client():
    if not REDIS_URL:
        pytest.skip("COMPANION_TEST_REDIS_URL not set")
    import redis.asyncio as redis

    client = redis.from_url(REDIS_URL, decode_responses=False)
    yield client
    await client.aclose()


@pytest.fixture
async def control(redis_client):
    from companion.service.turn.redis_control import RedisTurnControl

    return RedisTurnControl(redis_client)


async def test_orphan_turn_detected_when_lock_is_gone(control, redis_client):
    """崩溃留下的状态：哈希在、锁过期了 → 必须是孤儿。这就是线上 session 39 的形态。"""
    sid = _session_id()
    await control.init_turn(session_id=sid, turn_id="T-ORPHAN", message_ids=[11, 12])
    # 不拿锁（等价于锁已过期）
    orphans = await control.orphan_turns()
    mine = [o for o in orphans if o["session_id"] == sid]
    assert len(mine) == 1
    assert mine[0]["turn_id"] == "T-ORPHAN"
    assert mine[0]["message_ids"] == ["11", "12"]


async def test_running_turn_is_not_an_orphan(control):
    """正常在跑的回合绝不能被捞走：它每 10 秒续租，锁在。"""
    sid = _session_id()
    assert await control.acquire_lock(session_id=sid, owner="p1:T-LIVE")
    await control.init_turn(session_id=sid, turn_id="T-LIVE", message_ids=[21])
    orphans = await control.orphan_turns()
    assert not [o for o in orphans if o["session_id"] == sid]


async def test_clean_finish_leaves_no_candidate(control):
    """正常收尾（finish_turn 一个 pipeline 里删哈希 + 放锁）之后不该有残留。"""
    sid = _session_id()
    await control.acquire_lock(session_id=sid, owner="p1:T-DONE")
    await control.init_turn(session_id=sid, turn_id="T-DONE", message_ids=[31])
    await control.finish_turn(session_id=sid, owner="p1:T-DONE", turn_id="T-DONE",
                              event="message.done", data={})
    assert not [o for o in await control.orphan_turns() if o["session_id"] == sid]


async def test_clear_turn_if_refuses_to_delete_another_turns_state(control):
    """安全关键：孤儿判定与动手之间会话可能已起了新回合。

    无条件 clear_turn 会把**新**回合的控制状态删掉，merge/steer 全断。
    """
    sid = _session_id()
    await control.init_turn(session_id=sid, turn_id="T-NEW", message_ids=[41])
    assert not await control.clear_turn_if(session_id=sid, turn_id="T-OLD")
    # 新回合的状态还在
    assert (await redis_hgetall(control, sid)).get("turn_id") == "T-NEW"
    assert await control.clear_turn_if(session_id=sid, turn_id="T-NEW")
    assert (await redis_hgetall(control, sid)) == {}


async def redis_hgetall(control: Any, sid: int) -> dict[str, str]:
    from companion.service.turn.redis_control import turn_key

    raw = await control._r.hgetall(turn_key(sid))
    return {(k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
            for k, v in (raw or {}).items()}


# ------------------------------------------------------- SQLite：收尾与输入读取

@pytest.fixture
async def store(sqlite_engine):
    return SqlTurnRecoveryStore(sqlite_engine), sqlite_engine


async def test_close_turn_only_touches_running(store):
    """幂等判据：只有还挂着 running 的行会被改。"""
    turns, engine = store
    async with engine.begin() as conn:
        await conn.execute(insert(chat_turn).values(
            id="T1", session_id=7, owner_id=1, state="running"))
    assert await turns.close_turn(turn_id="T1") is True
    assert await turns.close_turn(turn_id="T1") is False      # 已经是 failed 了


async def test_has_assistant_reply_ignores_deleted(store):
    turns, engine = store
    async with engine.begin() as conn:
        await conn.execute(insert(chat_message).values(
            session_id=7, owner_id=1, role="assistant", content="答过了", kind="chat",
            turn_id="T1", deleted=True))
    assert await turns.has_assistant_reply(owner_id=1, session_id=7, turn_id="T1") is False


async def test_has_assistant_reply_counts_unselected_candidate(store):
    """未选中的候选回复同样说明这条回合回答过——不能重驱动。"""
    turns, engine = store
    async with engine.begin() as conn:
        await conn.execute(insert(chat_message).values(
            session_id=7, owner_id=1, role="assistant", content="候选", kind="chat",
            turn_id="T1", alt_group=99, alt_selected=False))
    assert await turns.has_assistant_reply(owner_id=1, session_id=7, turn_id="T1") is True


# ------------------------------------------------ TurnRecovery：重驱动决策

@dataclass
class FakeControl:
    """只实现 TurnRecovery 用到的那三个方法。"""
    turn_hash: dict[str, str] = field(default_factory=dict)

    async def orphan_turns(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return [dict(self.turn_hash)] if self.turn_hash else []

    async def clear_turn_if(self, *, session_id: int, turn_id: str) -> bool:
        if self.turn_hash.get("turn_id") == turn_id:
            self.turn_hash = {}
            return True
        return False


@dataclass
class FakeSubmit:
    result: str | None
    calls: list[dict] = field(default_factory=list)

    async def rerun(self, **kw: Any) -> str | None:
        self.calls.append(kw)
        return self.result


@dataclass
class FakeQueue:
    enqueued: list[dict] = field(default_factory=list)

    async def enqueue(self, **kw: Any) -> Any:
        self.enqueued.append(kw)
        return type("I", (), {"id": 1})()


def _recovery(*, turn_hash: dict, submit: FakeSubmit, engine: Any) -> TurnRecovery:
    return TurnRecovery(store=SqlTurnRecoveryStore(engine), control=FakeControl(turn_hash=turn_hash),
                        submit=submit, sessions=None, queue=FakeQueue())


async def test_answered_turn_is_closed_without_redrive(sqlite_engine):
    """回答过了只收尾。**重驱动会让用户看到两遍同样的话。**"""
    sid = 7
    async with sqlite_engine.begin() as conn:
        await conn.execute(insert(chat_message).values(
            session_id=sid, owner_id=1, role="user", content="问", kind="chat", turn_id="T1"))
        await conn.execute(insert(chat_message).values(
            session_id=sid, owner_id=1, role="assistant", content="答", kind="chat", turn_id="T1"))
        await conn.execute(insert(chat_turn).values(
            id="T1", session_id=sid, owner_id=1, role_id="r1", state="running"))

    submit = FakeSubmit(result="T-NEW")
    outcome = await _recovery(turn_hash={"session_id": sid, "turn_id": "T1", "message_ids": ["1"]},
                              submit=submit, engine=sqlite_engine).sweep()
    assert submit.calls == []
    assert outcome.redriven == 0 and outcome.closed == 1


async def test_unanswered_turn_is_redriven_with_original_inputs(sqlite_engine):
    """核心用例：session 39 那类被打断的回合要被重新驱动，输入原样。"""
    sid = 8
    async with sqlite_engine.begin() as conn:
        for text in ("附近的医院", "再加一句"):
            await conn.execute(insert(chat_message).values(
                session_id=sid, owner_id=1, role="user", content=text, kind="chat", turn_id="T1"))
        await conn.execute(insert(chat_turn).values(
            id="T1", session_id=sid, owner_id=1, role_id="r1", state="running"))

    submit = FakeSubmit(result="T-NEW")
    rec = _recovery(turn_hash={"session_id": sid, "turn_id": "T1", "message_ids": ["1", "2"]},
                    submit=submit, engine=sqlite_engine)
    outcome = await rec.sweep()
    assert outcome.redriven == 1
    assert submit.calls[0]["character_id"] == "r1"
    assert submit.calls[0]["message_ids"] == [1, 2]
    assert submit.calls[0]["text"] == "附近的医院\n\n再加一句"


async def test_busy_redrive_queues_instead_of_losing_the_input(sqlite_engine):
    """重驱动撞上会话忙：回合状态已经清了，下一轮扫不到——必须排队，否则永久丢失。"""
    sid = 9
    async with sqlite_engine.begin() as conn:
        await conn.execute(insert(chat_message).values(
            session_id=sid, owner_id=1, role="user", content="问", kind="chat", turn_id="T1"))
        await conn.execute(insert(chat_turn).values(
            id="T1", session_id=sid, owner_id=1, role_id="r1", state="running"))

    submit = FakeSubmit(result=None)
    queue = FakeQueue()
    rec = TurnRecovery(store=SqlTurnRecoveryStore(sqlite_engine), control=FakeControl(
        turn_hash={"session_id": sid, "turn_id": "T1", "message_ids": ["1"]}),
        submit=submit, sessions=None, queue=queue)
    outcome = await rec.sweep()
    assert outcome.busy == 1 and outcome.redriven == 0
    assert [e["message_id"] for e in queue.enqueued] == [1]


async def test_turn_without_message_ids_is_closed_not_guessed(sqlite_engine):
    rec = _recovery(turn_hash={"session_id": 10, "turn_id": "T1", "message_ids": []},
                    submit=FakeSubmit(result="T-NEW"), engine=sqlite_engine)
    outcome = await rec.sweep()
    assert outcome.redriven == 0 and outcome.closed == 1


async def test_deleted_inputs_close_the_turn_without_replay(sqlite_engine):
    """输入行被删了就不重放——只清残留状态。"""
    sid = 11
    async with sqlite_engine.begin() as conn:
        await conn.execute(insert(chat_message).values(
            session_id=sid, owner_id=1, role="user", content="删了", kind="chat",
            turn_id="T1", deleted=True))
    rec = _recovery(turn_hash={"session_id": sid, "turn_id": "T1", "message_ids": ["1"]},
                    submit=FakeSubmit(result="T-NEW"), engine=sqlite_engine)
    outcome = await rec.sweep()
    assert outcome.redriven == 0 and outcome.closed == 1
