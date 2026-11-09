"""MySQL 实现：认领用 SELECT … FOR UPDATE SKIP LOCKED（O §2.1），多个 worker 不会抢同一条。

租约过期的 running 任务与到期的 queued 任务一起被认领（视为上一个进程已崩溃）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.adapters.store.mysql.schema import agent_job
from companion.ports.jobs import JobRecord


class MysqlJobStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def enqueue(self, *, kind: str, payload: dict[str, Any], run_after: datetime,
                      dedupe_key: str | None = None, max_attempts: int = 5) -> bool:
        from sqlalchemy import insert
        from sqlalchemy.exc import IntegrityError

        now = datetime.utcnow()
        try:
            async with self._engine.begin() as conn:
                await conn.execute(insert(agent_job).values(
                    kind=kind, payload=payload, status="queued", attempts=0, max_attempts=max_attempts,
                    run_after=run_after, dedupe_key=dedupe_key, created_at=now, updated_at=now))
        except IntegrityError:
            return False  # dedupe_key 已存在：同一任务不重复入队
        return True

    async def claim(self, *, owner: str, now: datetime, lease_until: datetime, limit: int) -> list[JobRecord]:
        async with self._engine.begin() as conn:
            rows = (await conn.execute(
                select(agent_job).where(or_(
                    and_(agent_job.c.status == "queued", agent_job.c.run_after <= now),
                    and_(agent_job.c.status == "running", agent_job.c.lease_until <= now),
                )).order_by(agent_job.c.run_after).limit(limit).with_for_update(skip_locked=True)
            )).mappings().all()
            claimed = []
            for row in rows:
                await conn.execute(update(agent_job).where(agent_job.c.id == row["id"]).values(
                    status="running", lease_owner=owner, lease_until=lease_until, attempts=row["attempts"] + 1,
                    updated_at=now))
                claimed.append(JobRecord(row["id"], row["kind"], dict(row["payload"] or {}),
                                         row["attempts"] + 1, row["max_attempts"], row["dedupe_key"]))
        return claimed

    async def renew(self, *, job_id: int, owner: str, lease_until: datetime) -> bool:
        async with self._engine.begin() as conn:
            res = await conn.execute(update(agent_job).where(and_(
                agent_job.c.id == job_id, agent_job.c.lease_owner == owner, agent_job.c.status == "running"))
                .values(lease_until=lease_until))
        return res.rowcount == 1

    async def complete(self, *, job_id: int, owner: str) -> bool:
        async with self._engine.begin() as conn:
            res = await conn.execute(update(agent_job).where(and_(
                agent_job.c.id == job_id, agent_job.c.lease_owner == owner, agent_job.c.status == "running"))
                .values(status="done", lease_owner=None, lease_until=None))
        return res.rowcount == 1

    async def fail(self, *, job_id: int, owner: str, status: str, run_after: datetime | None, error: str) -> bool:
        values: dict[str, Any] = {"status": status, "lease_owner": None, "lease_until": None,
                                  "last_error": error[:2000]}
        if run_after is not None:
            values["run_after"] = run_after
        async with self._engine.begin() as conn:
            res = await conn.execute(update(agent_job).where(and_(
                agent_job.c.id == job_id, agent_job.c.lease_owner == owner, agent_job.c.status == "running"))
                .values(**values))
        return res.rowcount == 1
