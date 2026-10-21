"""Ambient business identity for LLM audit rows.

Every model call wants the same four facts — who, which profile, which job,
which session — and none of the services that make the calls receive them as
arguments today.  `ResumeService.elevate` knows the profile id;
`ResumeElevator.build_sections` three frames down does not, and threading the
identity through every signature in between would change four layers of
unrelated APIs to satisfy a log.

So identity is bound once, where it is already known (the auth dependency, the
profile route, the agent runner), and each call site contributes only the one
fact it owns: which code path it is.  This mirrors `bind_trace_context`, which
the request middleware and `get_actor` already use the same way.

ContextVars do not cross into `threading.Thread` workers.  The agent path
therefore binds its own context inside the worker instead of inheriting one.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from jc.llm.call_log import LLMLogContext

_FIELDS = ("user_id", "actor_kind", "profile_id", "job_id", "session_id", "skill_hint")

_ambient: ContextVar[dict[str, str | None]] = ContextVar("jc_llm_ambient", default={})


def bind_llm_context(**fields: str | None) -> None:
    """Merge identity into the ambient context for the rest of this task.

    Unset keys are left alone, so the auth dependency can bind the user and a
    route can later add the profile without either knowing about the other.
    Passing an explicit None clears a key.
    """
    merged = dict(_ambient.get())
    for name, value in fields.items():
        if name not in _FIELDS:
            raise ValueError(f"Unknown LLM context field: {name}")
        if value is None:
            merged.pop(name, None)
        else:
            merged[name] = value
    _ambient.set(merged)


@contextmanager
def llm_context_scope(**fields: str | None) -> Any:
    """Bind identity for one block, then restore it.

    Used where one request drives several profiles or locales in sequence and
    the rows must not inherit each other's ids.
    """
    token = _ambient.set(dict(_ambient.get()))
    try:
        bind_llm_context(**fields)
        yield
    finally:
        _ambient.reset(token)


def clear_llm_context() -> None:
    _ambient.set({})


def llm_context(caller: str, **overrides: str | None) -> LLMLogContext:
    """Build the log context for one call: ambient identity plus this caller."""
    data = dict(_ambient.get())
    for name, value in overrides.items():
        if name not in _FIELDS:
            raise ValueError(f"Unknown LLM context field: {name}")
        if value is not None:
            data[name] = value
    return LLMLogContext(caller=caller, **data)
