"""后台任务端口（O §2.1）。认领与状态转移都是条件更新，返回是否生效。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class JobRecord:
    id: int
    kind: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int
    dedupe_key: str | None


class JobStore(Protocol):
    async def enqueue(self, *, kind: str, payload: dict[str, Any], run_after: datetime,
                      dedupe_key: str | None = None, max_attempts: int = 5) -> bool: ...
    async def claim(self, *, owner: str, now: datetime, lease_until: datetime, limit: int) -> list[JobRecord]: ...
    async def renew(self, *, job_id: int, owner: str, lease_until: datetime) -> bool: ...
    async def complete(self, *, job_id: int, owner: str) -> bool: ...
    async def fail(self, *, job_id: int, owner: str, status: str, run_after: datetime | None,
                   error: str) -> bool: ...
