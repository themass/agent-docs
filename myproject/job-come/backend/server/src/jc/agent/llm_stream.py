"""LLM streaming helpers for agent runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StreamedCompletion:
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: Any | None = None


def accumulate_tool_delta(
    acc: dict[int, dict[str, str]],
    tool_calls: list[Any] | None,
) -> None:
    if not tool_calls:
        return
    for tc in tool_calls:
        idx = tc.index if getattr(tc, "index", None) is not None else 0
        entry = acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
        if getattr(tc, "id", None):
            entry["id"] = tc.id
        fn = getattr(tc, "function", None)
        if fn is None:
            continue
        if getattr(fn, "name", None):
            entry["name"] = fn.name
        if getattr(fn, "arguments", None):
            entry["arguments"] += fn.arguments


def tool_calls_from_accumulator(acc: dict[int, dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx in sorted(acc):
        entry = acc[idx]
        if not entry.get("name"):
            continue
        out.append(
            {
                "id": entry.get("id") or f"call_{idx}",
                "type": "function",
                "function": {
                    "name": entry["name"],
                    "arguments": entry.get("arguments") or "{}",
                },
            }
        )
    return out
