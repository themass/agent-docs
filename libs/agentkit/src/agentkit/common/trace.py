from __future__ import annotations
import contextvars
from typing import Any
from agentkit.common.ids import new_id

_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)
_actor_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("actor_id", default=None)

def new_trace_id() -> str:
    return new_id("trc")

def get_trace_id() -> str | None:
    return _trace_id.get()

def bind_trace_context(*, trace_id: str | None = None, actor_id: str | None = None) -> dict[str, Any]:
    ctx: dict[str, Any] = {}
    if trace_id is not None:
        _trace_id.set(trace_id)
        ctx["trace_id"] = trace_id
    if actor_id is not None:
        _actor_id.set(actor_id)
        ctx["actor_id"] = actor_id
    return ctx

def clear_trace_context() -> None:
    _trace_id.set(None)
    _actor_id.set(None)
