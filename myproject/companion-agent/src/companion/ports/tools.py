"""工具审计端口（T §2.5）。只存参数指纹，不存参数原文。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ToolCallRecord:
    turn_id: str
    owner_id: int
    tool: str
    permission: str
    args_fingerprint: str
    status: str            # executed | needs_confirmation | invalid_args | not_available | failed | timeout
    latency_ms: int
    result_chars: int


class ToolCallStore(Protocol):
    async def append(self, record: ToolCallRecord) -> None: ...
