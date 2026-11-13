"""记忆 hook 协议（chat-agent-memory-hooks.md §3–4）。与业务、与具体记忆后端都无关。

三个插槽：
- ``Recaller``：回合前召回，只读，不抛异常（失败写进 ``RecallResult.error``）；
- ``Recorder``：回合后写入，按 ``turn_id`` 幂等，不抛异常；
- ``Forgetter``：删除传播。

编排规则在 ``domain/memory/pipeline.py``，所有实现都遵守同一套规则。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RecallQuery:
    user_id: str                 # 应用内用户 id，hook 不解析其结构
    scope: str                   # 隔离范围（应用名），原样透传
    text: str                    # 本轮用户输入，用于相关性
    limit: int = 5               # 每个来源的条数上限
    budget_chars: int = 800      # 本次召回能占用的总字符数
    role_id: str | None = None   # 角色维度；是否按角色隔离由来源自己决定
    occurred_before: datetime | None = None


@dataclass(frozen=True, slots=True)
class RecalledItem:
    text: str                    # 已可直接放进提示词的一句话
    source: str                  # 来源名，用于溯源与去重
    ref: str                     # 来源内的稳定标识
    occurred_at: datetime | None = None
    score: float | None = None   # 来源内的相关性；不跨来源比较
    tags: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class RecallResult:
    source: str
    items: tuple[RecalledItem, ...] = ()
    truncated: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class TurnRecord:
    scope: str
    user_id: str
    turn_id: str                 # 幂等键
    user_text: str               # 只有用户的话
    assistant_text: str          # 仅作消歧上下文，不得原样写成用户事实
    occurred_at: datetime
    role_id: str | None = None
    session_id: int | None = None


@dataclass(frozen=True, slots=True)
class RecordOutcome:
    source: str
    written: int = 0
    skipped: int = 0
    error: str | None = None


@dataclass(frozen=True, slots=True)
class RecallStats:
    per_source: dict[str, dict[str, object]] = field(default_factory=dict)
    truncated: bool = False


class Recaller(Protocol):
    name: str

    async def recall(self, query: RecallQuery) -> RecallResult: ...


class Recorder(Protocol):
    name: str

    async def record(self, turn: TurnRecord) -> RecordOutcome: ...


class Forgetter(Protocol):
    name: str

    async def forget(self, *, scope: str, user_id: str, ref: str | None) -> int: ...
