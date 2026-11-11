"""账号注销在关系库里的部分（chat-agent-ops-design.md §3 步骤 1、5、6、7）。

注销是物理删除（软删除只用于误删可恢复的场景）。所有语句按 owner_id 条件删除，重复执行无副作用。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.adapters.store.sql.schema import (
    account_purge_log,
    action_confirmation,
    agent_job,
    chat_message,
    chat_queue,
    chat_session,
    chat_turn,
    persona_cursor,
    persona_entry,
    persona_profile,
    reminder,
    timeline_event,
    tool_call,
    upload,
    user_role,
)
from companion.ports.account import AccountFootprint

# 删除顺序：先子表后会话。没有外键约束，顺序只为了中途失败时不留下「有消息没会话」的孤儿。
_OWNED = (chat_message, chat_turn, chat_queue, action_confirmation, tool_call, reminder, timeline_event,
          upload, persona_profile, persona_entry, persona_cursor, user_role, chat_session)

# 载荷里带用户数据、还没执行的后台任务：注销后不能再跑（否则会把记忆写回来）。
USER_JOB_KINDS = ("memory.record", "session.resummarize", "timeline.record", "persona.update")
_PENDING = ("queued", "running")


def _payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, (str, bytes)):
        try:
            loaded = json.loads(value)
        except ValueError:
            return {}
        return loaded if isinstance(loaded, dict) else {}
    return {}


class SqlAccountStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def footprint(self, *, owner_id: int) -> AccountFootprint:
        async with self._engine.connect() as conn:
            sessions = (await conn.execute(select(chat_session.c.id, chat_session.c.role_id)
                                           .where(chat_session.c.owner_id == owner_id))).all()
            reminder_roles = (await conn.execute(select(reminder.c.role_id).distinct()
                                                 .where(reminder.c.owner_id == owner_id))).scalars().all()
            own_roles = (await conn.execute(select(user_role.c.public_id)
                                            .where(user_role.c.owner_id == owner_id))).scalars().all()
            keys = (await conn.execute(select(upload.c.object_key)
                                       .where(upload.c.owner_id == owner_id))).scalars().all()
        roles = sorted({r for _, r in sessions if r} | {r for r in reminder_roles if r} | {r for r in own_roles if r})
        return AccountFootprint(session_ids=tuple(sorted(s for s, _ in sessions)), role_ids=tuple(roles),
                                object_keys=tuple(keys))

    async def close_sessions(self, *, owner_id: int) -> int:
        async with self._engine.begin() as conn:
            res = await conn.execute(update(chat_session).where(chat_session.c.owner_id == owner_id)
                                     .values(deleted=True, fence=chat_session.c.fence + 1))
        return res.rowcount

    async def purge(self, *, owner_id: int) -> int:
        total = 0
        async with self._engine.begin() as conn:
            jobs = (await conn.execute(select(agent_job.c.id, agent_job.c.payload).where(
                agent_job.c.kind.in_(USER_JOB_KINDS), agent_job.c.status.in_(_PENDING)))).all()
            doomed = [jid for jid, payload in jobs if str(_payload(payload).get("owner_id")) == str(owner_id)]
            if doomed:
                total += (await conn.execute(delete(agent_job).where(agent_job.c.id.in_(doomed)))).rowcount
            for table in _OWNED:
                total += (await conn.execute(delete(table).where(table.c.owner_id == owner_id))).rowcount
        return total

    async def log_purge(self, *, user_hash: str, requested_at: datetime, finished_at: datetime) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(insert(account_purge_log).values(
                user_hash=user_hash, requested_at=requested_at, finished_at=finished_at))
