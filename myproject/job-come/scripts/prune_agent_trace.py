#!/usr/bin/env python3
"""Enforce the retention window on the agent ledger.

`jc_agent_trace` holds what a session said and did — including the wrapped model
input, which contains the candidate's profile and resume text.
`JC_AGENT_TRACE_RETENTION_DAYS` (default 60) is the promise that this does not
live forever, and this script is what makes that promise true. Run it from cron
on the production host.

Two modes:
  --dry-run   report what would go, change nothing (the default)
  --apply     delete

Deleting a session's ledger rows is not the same as deleting the session: the
session, its interview, its report and the audit log all stay. Only the
turn-by-turn transcript ages out.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from lib.bootstrap import ensure_project_env

ensure_project_env()

from jc.config import settings  # noqa: E402
from jc.db.session import AsyncSessionLocal  # noqa: E402
from jc.models.agent_trace import AgentTrace  # noqa: E402
from sqlalchemy import delete, func, select  # noqa: E402

BATCH = 2000


async def _run(days: int, apply: bool) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    async with AsyncSessionLocal() as db:
        doomed = await db.scalar(
            select(func.count()).select_from(AgentTrace).where(AgentTrace.created_at < cutoff)
        )
        print(f"ledger rows older than {days}d (< {cutoff.isoformat()}): {doomed or 0}")

        if not apply:
            print("dry run: nothing changed (pass --apply to execute)")
            return 0

        # Delete by id in batches rather than one unbounded DELETE: a single
        # statement over a year of rows holds locks and grows WAL in a way that is
        # hard to interrupt cleanly. Reading ids first makes each batch a small,
        # committable unit.
        removed = 0
        while True:
            ids = (
                await db.execute(
                    select(AgentTrace.id)
                    .where(AgentTrace.created_at < cutoff)
                    .limit(BATCH)
                )
            ).scalars().all()
            if not ids:
                break
            await db.execute(delete(AgentTrace).where(AgentTrace.id.in_(ids)))
            await db.commit()
            removed += len(ids)
            print(f"  deleted {removed} ...")
        print(f"deleted {removed} ledger rows")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days",
        type=int,
        default=settings.jc_agent_trace_retention_days,
        help="delete ledger rows older than this many days",
    )
    parser.add_argument("--apply", action="store_true", help="execute instead of reporting")
    args = parser.parse_args()
    return asyncio.run(_run(args.days, args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
