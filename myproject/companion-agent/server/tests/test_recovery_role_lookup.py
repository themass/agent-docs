"""重驱动时角色从哪来（recovery._role_of 用真实 SqlSessionStore）。

线上第一次清扫（2026-11-28，部署 d56e174d 后）捞到 3 个孤儿回合，**全部**以
`no character_id — closed, not redriven` 收尾。如果角色查找在真库上根本走不通，
那这次的修复就等于只清状态、不救消息——所以这条路径必须用真的 store 测，
不能用 `sessions=None` 的假装配。
"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import insert

from companion.db.schema import chat_message, chat_session, chat_turn
from companion.db.sql import SqlSessionStore
from companion.service.chat.recovery import SqlTurnRecoveryStore, TurnRecovery


@dataclass
class FakeControl:
    turn_hash: dict[str, Any] = field(default_factory=dict)

    async def orphan_turns(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return [dict(self.turn_hash)] if self.turn_hash else []

    async def clear_turn_if(self, *, session_id: int, turn_id: str) -> bool:
        if self.turn_hash.get("turn_id") == turn_id:
            self.turn_hash = {}
            return True
        return False


@dataclass
class FakeSubmit:
    result: str | None = "T-NEW"
    calls: list[dict] = field(default_factory=list)

    async def rerun(self, **kw: Any) -> str | None:
        self.calls.append(kw)
        return self.result


@dataclass
class FakeQueue:
    async def enqueue(self, **kw: Any) -> Any:
        return type("I", (), {"id": 1})()


def _recovery(*, engine: Any, turn_hash: dict, submit: FakeSubmit, sessions: Any) -> TurnRecovery:
    return TurnRecovery(store=SqlTurnRecoveryStore(engine), control=FakeControl(turn_hash=turn_hash),
                        submit=submit, sessions=sessions, queue=FakeQueue())


async def test_role_comes_from_the_session_row_when_the_turn_row_is_gone(sqlite_engine):
    """被打断得太早 → `ca_chat_turn` 没有行（它由 note_turn_models 在首次 LLM 调用后才写）。

    这时角色只能从会话行取。少了这一手，真实事故里的那条消息就永远救不回来。
    """
    sid = 41
    async with sqlite_engine.begin() as conn:
        await conn.execute(insert(chat_session).values(
            id=sid, owner_id=7, role_id="her_default", name="会话", locale="zh-CN"))
        await conn.execute(insert(chat_message).values(
            session_id=sid, owner_id=7, role="user", content="附近的医院", kind="chat",
            turn_id="T1"))

    submit = FakeSubmit()
    rec = _recovery(engine=sqlite_engine, sessions=SqlSessionStore(sqlite_engine),
                    turn_hash={"session_id": sid, "turn_id": "T1", "message_ids": ["1"]},
                    submit=submit)
    outcome = await rec.sweep()
    assert outcome.redriven == 1, "会话行有 role_id，就必须重驱动"
    assert submit.calls[0]["character_id"] == "her_default"
    assert submit.calls[0]["owner_id"] == 7


async def test_turn_row_role_wins_over_the_session_row(sqlite_engine):
    """回合行上记的角色优先：会话可能换了角色，被打断的那一轮用的是旧角色。"""
    sid = 42
    async with sqlite_engine.begin() as conn:
        await conn.execute(insert(chat_session).values(
            id=sid, owner_id=7, role_id="new_role", name="会话", locale="zh-CN"))
        await conn.execute(insert(chat_message).values(
            session_id=sid, owner_id=7, role="user", content="问", kind="chat", turn_id="T1"))
        await conn.execute(insert(chat_turn).values(
            id="T1", session_id=sid, owner_id=7, role_id="old_role", state="running"))

    submit = FakeSubmit()
    rec = _recovery(engine=sqlite_engine, sessions=SqlSessionStore(sqlite_engine),
                    turn_hash={"session_id": sid, "turn_id": "T1", "message_ids": ["1"]},
                    submit=submit)
    await rec.sweep()
    assert submit.calls[0]["character_id"] == "old_role"


async def test_deleted_session_closes_without_redrive(sqlite_engine):
    """会话被软删了就不重驱动——不该把消息投进一个已经不存在的会话。"""
    sid = 43
    async with sqlite_engine.begin() as conn:
        await conn.execute(insert(chat_session).values(
            id=sid, owner_id=7, role_id="her_default", name="会话", locale="zh-CN", deleted=True))
        await conn.execute(insert(chat_message).values(
            session_id=sid, owner_id=7, role="user", content="问", kind="chat", turn_id="T1"))

    submit = FakeSubmit()
    rec = _recovery(engine=sqlite_engine, sessions=SqlSessionStore(sqlite_engine),
                    turn_hash={"session_id": sid, "turn_id": "T1", "message_ids": ["1"]},
                    submit=submit)
    outcome = await rec.sweep()
    assert submit.calls == []
    assert outcome.redriven == 0 and outcome.closed == 1
