#!/usr/bin/env python3
"""Enforce the retention window on the LLM call audit log.

The log stores prompts and model responses, which for JC means resume content.
Keeping that forever is neither useful nor defensible, so this script deletes
calls older than ``JC_LLM_LOG_RETENTION_DAYS`` (default 90) along with their
attempt rows. Run it from cron on the production host.

Two modes:
  --dry-run     report what would go, change nothing (default)
  --apply       delete

A middle option, ``--forget-payload-after DAYS``, blanks only the three payload
columns while keeping metrics and failure codes. Use it when the cost and
reliability history is worth more than the content.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from lib.bootstrap import ensure_project_env

ensure_project_env()

from jc.config import settings  # noqa: E402
from jc.db.session import AsyncSessionLocal  # noqa: E402
from jc.models.llm_call import LlmCall, LlmCallAttempt  # noqa: E402
from sqlalchemy import delete, func, select, update  # noqa: E402


async def _run(days: int, forget_after: int | None, apply: bool) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    async with AsyncSessionLocal() as db:
        doomed = await db.scalar(
            select(func.count()).select_from(LlmCall).where(LlmCall.created_at < cutoff)
        )
        print(f"calls older than {days}d (< {cutoff.isoformat()}): {doomed or 0}")

        stale = 0
        payload_cutoff = None
        if forget_after is not None:
            payload_cutoff = datetime.now(UTC) - timedelta(days=forget_after)
            stale = await db.scalar(
                select(func.count())
                .select_from(LlmCall)
                .where(
                    LlmCall.created_at < payload_cutoff,
                    LlmCall.created_at >= cutoff,
                    LlmCall.prompt_text.is_not(None),
                )
            )
            print(f"calls to strip payload from (> {forget_after}d, kept): {stale or 0}")

        if not apply:
            print("dry run: nothing changed (pass --apply to execute)")
            return 0

        if payload_cutoff is not None:
            await db.execute(
                update(LlmCall)
                .where(
                    LlmCall.created_at < payload_cutoff,
                    LlmCall.created_at >= cutoff,
                )
                .values(prompt_text=None, response_text=None, reasoning_text=None)
            )

        # Attempts first: they are keyed by call_id with no cascade, so deleting
        # the parent first would orphan them.
        ids = (
            await db.execute(select(LlmCall.id).where(LlmCall.created_at < cutoff))
        ).scalars()
        id_list = list(ids)
        for start in range(0, len(id_list), 500):
            batch = id_list[start : start + 500]
            await db.execute(delete(LlmCallAttempt).where(LlmCallAttempt.call_id.in_(batch)))
        await db.execute(delete(LlmCall).where(LlmCall.created_at < cutoff))
        await db.commit()
        print(f"deleted {len(id_list)} calls and their attempts")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days",
        type=int,
        default=settings.jc_llm_log_retention_days,
        help="delete calls older than this many days",
    )
    parser.add_argument(
        "--forget-payload-after",
        type=int,
        default=None,
        help="blank prompt/response/reasoning text for calls older than this, keeping metrics",
    )
    parser.add_argument("--apply", action="store_true", help="execute instead of reporting")
    args = parser.parse_args()
    return asyncio.run(_run(args.days, args.forget_payload_after, args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
