"""渲染「关于用户」与「近期事件」两段，供记忆召回中间件与提示词组装共用。"""

from __future__ import annotations

from typing import Any

from companion.agent.prompt.instructions import build_memory_block


def _format_at(value: Any) -> str:
    """时间只给到「月-日 时:分」，模型不需要秒与微秒。"""
    try:
        return value.strftime("%m-%d %H:%M")
    except AttributeError:
        return str(value)


def render_events(events: Any, *, limit: int = 5) -> str:
    """把事件列表拼成一段。按时间排序，只取将来最近的几条。

    过去的与已取消的都不进提示词：模型提「你上周那个面试」而用户已经结束了，
    只会显得它没在听。
    """
    lines: list[str] = []
    upcoming = [
        e
        for e in (events or ())
        if getattr(e, "status", None) is not None
        and getattr(getattr(e, "status"), "value", "") == "scheduled"
    ]
    upcoming.sort(key=lambda e: getattr(e, "at", None) or "")
    for event in upcoming[:limit]:
        title = getattr(event, "title", "")
        at = getattr(event, "at", None)
        if title:
            lines.append(f"- {_format_at(at)} {title}")
    return "\n".join(lines)


def _render(facts: Any, events: Any) -> str:
    parts = []
    facts_block = build_memory_block(facts)
    if facts_block:
        parts.append(facts_block)
    events_block = render_events(events)
    if events_block:
        parts.append("近期事件：\n" + events_block)
    return "\n\n".join(parts)
