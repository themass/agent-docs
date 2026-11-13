"""后台任务存储（O §2.1）。多个 worker 不会抢同一条：

- Postgres：一条 ``SELECT … FOR UPDATE SKIP LOCKED`` 在同一事务里取候选并改为 running；
- MySQL 5.6（兼容方言，没有 SKIP LOCKED）：先取候选，再逐条做条件 UPDATE，rowcount == 1 才算拿到。

租约过期的 running 任务与到期的 queued 任务一起被认领（视为上一个进程已崩溃）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.adapters.store.sql.schema import agent_job
from companion.jobs.port import JobRecord


def _sec(value: datetime) -> datetime:
    """MySQL 5.6 的 DATETIME 不保存小数秒，写入时会四舍五入。
    写入与比较两侧都截到整秒，否则刚到期的任务会因为「进位」而暂时不可认领。"""
    return value.replace(microsecond=0)


class SqlJobStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def enqueue(self, *, kind: str, payload: dict[str, Any], run_after: datetime,
                      dedupe_key: str | None = None, max_attempts: int = 5) -> bool:
        from sqlalchemy import insert
        from sqlalchemy.exc import IntegrityError

        now = _sec(datetime.utcnow())
        try:
            async with self._engine.begin() as conn:
                await conn.execute(insert(agent_job).values(
                    kind=kind, payload=payload, status="queued", attempts=0, max_attempts=max_attempts,
                    run_after=_sec(run_after), dedupe_key=dedupe_key, created_at=now, updated_at=now))
        except IntegrityError:
            return False  # dedupe_key 已存在：同一任务不重复入队
        return True

    async def claim(self, *, owner: str, now: datetime, lease_until: datetime, limit: int) -> list[JobRecord]:
        if self._engine.dialect.name == "postgresql":
            return await self._claim_skip_locked(owner=owner, now=now, lease_until=lease_until, limit=limit)
        return await self._claim_conditional(owner=owner, now=now, lease_until=lease_until, limit=limit)

    async def _claim_skip_locked(self, *, owner: str, now: datetime, lease_until: datetime,
                                 limit: int) -> list[JobRecord]:
        due = or_(
            and_(agent_job.c.status == "queued", agent_job.c.run_after <= now),
            and_(agent_job.c.status == "running", agent_job.c.lease_until <= now),
        )
        async with self._engine.begin() as conn:
            ids = (await conn.execute(
                select(agent_job.c.id).where(due).order_by(agent_job.c.run_after)
                .limit(limit).with_for_update(skip_locked=True)
            )).scalars().all()
            if not ids:
                return []
            rows = (await conn.execute(
                update(agent_job).where(agent_job.c.id.in_(ids))
                .values(status="running", lease_owner=owner, lease_until=lease_until,
                        attempts=agent_job.c.attempts + 1, updated_at=now)
                .returning(agent_job)
            )).mappings().all()
        return [JobRecord(r["id"], r["kind"], dict(r["payload"] or {}), r["attempts"], r["max_attempts"],
                          r["dedupe_key"]) for r in sorted(rows, key=lambda r: r["run_after"])]

    async def _claim_conditional(self, *, owner: str, now: datetime, lease_until: datetime,
                                 limit: int) -> list[JobRecord]:
        """MySQL 5.6 没有 SKIP LOCKED：先取候选，再逐条做条件更新。只有一个 worker 的 UPDATE 能命中（rowcount == 1）。"""
        now, lease_until = _sec(now), _sec(lease_until)
        async with self._engine.connect() as conn:
            candidates = (await conn.execute(
                select(agent_job.c.id).where(or_(
                    and_(agent_job.c.status == "queued", agent_job.c.run_after <= now),
                    and_(agent_job.c.status == "running", agent_job.c.lease_until <= now),
                )).order_by(agent_job.c.run_after).limit(limit)
            )).scalars().all()
        claimed: list[JobRecord] = []
        for job_id in candidates:
            async with self._engine.begin() as conn:
                res = await conn.execute(update(agent_job).where(and_(
                    agent_job.c.id == job_id,
                    or_(
                        and_(agent_job.c.status == "queued", agent_job.c.run_after <= now),
                        and_(agent_job.c.status == "running", agent_job.c.lease_until <= now),
                    ),
                )).values(status="running", lease_owner=owner, lease_until=lease_until,
                          attempts=agent_job.c.attempts + 1, updated_at=now))
                if res.rowcount != 1:
                    continue  # 别的 worker 先拿到了
                row = (await conn.execute(select(agent_job).where(agent_job.c.id == job_id))).mappings().one()
            claimed.append(JobRecord(row["id"], row["kind"], dict(row["payload"] or {}), row["attempts"],
                                     row["max_attempts"], row["dedupe_key"]))
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
