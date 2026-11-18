"""Cue 意图：模型侧建议 → 编译器输入（§11 / v1 §7.1）。

纯数据，不发网络。``kind`` 是意图名（``emotion`` / ``gesture`` / ``gaze``），
不是 wire 上的 ``presentation.*``——那一层由 :mod:`cue_compiler` 映射，
这样标签回落与结构化片段共用同一种输入。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: 端侧 ``at.phase`` 的四个取值（§9.2）。标签回落默认 ``start``。
PHASES = frozenset({"before", "start", "during", "after"})

#: 模型 / 标签可能写出的 kind → 规范意图名。
KIND_ALIASES: dict[str, str] = {
    "emotion": "emotion",
    "avatar.expression": "emotion",
    "expression": "emotion",
    "presentation.emotion": "emotion",
    "gesture": "gesture",
    "avatar.gesture": "gesture",
    "presentation.gesture": "gesture",
    "gaze": "gaze",
    "avatar.gaze": "gaze",
    "presentation.gaze": "gaze",
}

#: 意图名 → wire 上的 ``t``。
EVENT_FOR_KIND: dict[str, str] = {
    "emotion": "presentation.emotion",
    "gesture": "presentation.gesture",
    "gaze": "presentation.gaze",
}

#: 结构化片段的 anchor 词 → phase。
ANCHOR_TO_PHASE: dict[str, str] = {
    "segment_start": "start",
    "segment_end": "after",
    "before": "before",
    "start": "start",
    "during": "during",
    "after": "after",
}


@dataclass(frozen=True)
class CueIntent:
    """一条待编译的表现意图。

    ``params`` 只保留模型给的参数；``intensity`` 等由编译器原样放进 args。
    """

    kind: str
    name: str
    params: dict[str, Any] = field(default_factory=dict)
    phase: str = "start"

    def __post_init__(self) -> None:
        if self.phase not in PHASES:
            object.__setattr__(self, "phase", "start")


def normalize_kind(raw: str | None) -> str | None:
    """未知 kind 返回 None，调用方丢弃并计数。"""
    if not isinstance(raw, str) or not raw.strip():
        return None
    return KIND_ALIASES.get(raw.strip().lower())


def phase_of_anchor(raw: str | None, *, default: str = "start") -> str:
    if not isinstance(raw, str) or not raw.strip():
        return default
    return ANCHOR_TO_PHASE.get(raw.strip().lower(), default)
