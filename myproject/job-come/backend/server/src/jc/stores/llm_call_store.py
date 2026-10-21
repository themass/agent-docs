"""Read queries over the LLM call audit log."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jc.models.llm_call import LlmCall, LlmCallAttempt
from jc.stores.sorting import SortSpec

#: Sortable columns for the LLM audit list. Cost / tokens / latency are the point
#: of this one: "which call burned the most tokens" and "what is the slowest call"
#: are the two questions the list exists to answer, and neither was reachable
#: while the order was pinned to `created_at DESC`.
LLM_CALL_SORT = SortSpec(
    fields={
        "created_at": LlmCall.created_at,
        "latency_ms": LlmCall.latency_ms,
        "total_tokens": LlmCall.total_tokens,
        "prompt_tokens": LlmCall.prompt_tokens,
        "completion_tokens": LlmCall.completion_tokens,
        "cost_micro_usd": LlmCall.cost_micro_usd,
        "attempt_count": LlmCall.attempt_count,
        "scenario": LlmCall.scenario,
        "caller": LlmCall.caller,
        "channel": LlmCall.channel,
        "status": LlmCall.status,
        "final_model": LlmCall.final_model,
        "user_id": LlmCall.user_id,
        "session_id": LlmCall.session_id,
    },
    default="created_at",
    tiebreaker=LlmCall.id,
)


class LlmCallStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_calls(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        user_id: str | None = None,
        profile_id: str | None = None,
        scenario: str | None = None,
        caller: str | None = None,
        channel: str | None = None,
        status: str | None = None,
        trace_id: str | None = None,
        sort_by: str | None = None,
        sort_dir: str | None = None,
    ) -> tuple[list[LlmCall], int, str, str]:
        """Returns `(rows, total, resolved_sort_by, resolved_sort_dir)`.

        The resolved sort travels back with the rows so the table renders its
        arrow from what the server actually ordered by, not from what was asked.
        """
        filters = []
        if user_id:
            filters.append(LlmCall.user_id == user_id)
        if profile_id:
            filters.append(LlmCall.profile_id == profile_id)
        if scenario:
            filters.append(LlmCall.scenario == scenario)
        if caller:
            filters.append(LlmCall.caller == caller)
        if channel:
            filters.append(LlmCall.channel == channel)
        if status:
            filters.append(LlmCall.status == status)
        if trace_id:
            filters.append(LlmCall.trace_id == trace_id)

        order_by, field, direction = LLM_CALL_SORT.order_by(sort_by, sort_dir)
        total = await self._db.scalar(
            select(func.count()).select_from(LlmCall).where(*filters)
        )
        rows = (
            await self._db.execute(
                select(LlmCall)
                .where(*filters)
                .order_by(*order_by)
                .limit(limit)
                .offset(offset)
            )
        ).scalars()
        return list(rows), int(total or 0), field, direction

    async def get_call(self, call_id: str) -> LlmCall | None:
        return await self._db.scalar(select(LlmCall).where(LlmCall.id == call_id))

    async def attempts_for(self, call_id: str) -> list[LlmCallAttempt]:
        rows = (
            await self._db.execute(
                select(LlmCallAttempt)
                .where(LlmCallAttempt.call_id == call_id)
                .order_by(LlmCallAttempt.attempt_index.asc())
            )
        ).scalars()
        return list(rows)

    async def usage_rollup(
        self,
        *,
        days: int = 7,
        group_by: str = "scenario",
    ) -> list[dict[str, Any]]:
        """Aggregate calls/tokens/cost/failures for a window.

        `group_by` answers the two questions the log exists for: "what is one
        category of users doing" (scenario / caller) and "which model is
        actually serving traffic" (final_model).
        """
        columns = {
            "scenario": LlmCall.scenario,
            "caller": LlmCall.caller,
            "channel": LlmCall.channel,
            "final_model": LlmCall.final_model,
            "status": LlmCall.status,
        }
        if group_by not in columns:
            raise ValueError(f"Unsupported group_by: {group_by}")
        column = columns[group_by]
        since = datetime.now(UTC) - timedelta(days=days)

        rows = (
            await self._db.execute(
                select(
                    column.label("key"),
                    func.count().label("calls"),
                    func.sum(
                        case((LlmCall.status == "failed", 1), else_=0)
                    ).label("failed"),
                    func.sum(LlmCall.total_tokens).label("total_tokens"),
                    func.sum(LlmCall.cost_micro_usd).label("cost_micro_usd"),
                    func.avg(LlmCall.latency_ms).label("avg_latency_ms"),
                )
                .where(LlmCall.created_at >= since)
                .group_by(column)
                .order_by(func.count().desc())
            )
        ).all()
        return [
            {
                "key": row.key,
                "calls": int(row.calls or 0),
                "failed": int(row.failed or 0),
                "total_tokens": int(row.total_tokens or 0),
                "cost_micro_usd": int(row.cost_micro_usd or 0),
                "avg_latency_ms": int(row.avg_latency_ms or 0),
            }
            for row in rows
        ]
