"""Split prompt tokens into UI buckets using real API usage when present."""

from __future__ import annotations

from typing import Any

# Measured-ish JobCome overhead (MCP tools + skills + product rules), not Claude-sized catalogs.
_OVERHEAD: tuple[tuple[str, str, int], ...] = (
    ("system_prompt", "System prompt", 800),
    ("tool_definitions", "Tool definitions", 4_500),
    ("skills", "Skills", 2_200),
    ("rules", "Rules", 900),
)


def _overhead_total() -> int:
    return sum(tokens for _, _, tokens in _OVERHEAD)


def allocate_buckets(*, prompt_tokens: int) -> list[dict[str, Any]]:
    """Allocate `prompt_tokens` across overhead + conversation.

    Overhead is scaled down when the model reports a smaller prompt than the
    static catalog estimate (common on short greeting turns).
    """
    prompt = max(0, int(prompt_tokens))
    overhead = _overhead_total()
    if prompt <= 0:
        return [
            {"id": bid, "label": label, "tokens": tokens}
            for bid, label, tokens in _OVERHEAD
        ] + [{"id": "conversation", "label": "Conversation", "tokens": 0}]

    if prompt < overhead:
        scale = prompt / overhead
        allocated = [
            {"id": bid, "label": label, "tokens": max(1, int(tokens * scale))}
            for bid, label, tokens in _OVERHEAD
        ]
        used = sum(b["tokens"] for b in allocated)
        drift = prompt - used
        if drift != 0:
            allocated[-1]["tokens"] = max(1, allocated[-1]["tokens"] + drift)
        return allocated + [{"id": "conversation", "label": "Conversation", "tokens": 0}]

    conversation = prompt - overhead
    return [
        {"id": bid, "label": label, "tokens": tokens}
        for bid, label, tokens in _OVERHEAD
    ] + [{"id": "conversation", "label": "Conversation", "tokens": conversation}]


def build_context_usage_event(
    *,
    prompt_tokens: int,
    completion_tokens: int = 0,
    total_tokens: int | None = None,
    limit_tokens: int,
    turns: int = 0,
) -> dict[str, Any]:
    buckets = allocate_buckets(prompt_tokens=prompt_tokens)
    used = sum(int(b["tokens"]) for b in buckets)
    limit = max(1, int(limit_tokens))
    actual_total = total_tokens if total_tokens is not None else prompt_tokens + completion_tokens
    return {
        "type": "context_usage",
        "used_tokens": used,
        "limit_tokens": limit,
        "percent": min(100, round((used / limit) * 100)),
        "estimated": prompt_tokens <= 0,
        "buckets": buckets,
        "turns": turns,
        "actual": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": actual_total,
        },
    }
