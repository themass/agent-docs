"""`@method_metrics` — timing and counting for any sync or async callable.

Usage::

    @method_metrics()
    async def build_agent(...): ...

    @method_metrics(phase="tool")
    def call_tool(...): ...

What it records
--------------
``method_duration_seconds`` and ``method_calls_total``, labelled by
``target`` (``ClassName.method`` or ``module.function``), ``status`` and, on
failure, ``error_type``.

What it deliberately does not do
--------------------------------
- **No arguments or return values in labels.** They are unbounded (a session id,
  a prompt) and would blow up the series count — the classic way a metrics
  backend falls over under load.
- **No swallowed exceptions.** The wrapped call's exception propagates
  unchanged; only the observation is wrapped.
- **No overhead when disabled.** The timing check is one attribute read.
"""

from __future__ import annotations

import functools
import inspect
import logging
import time
from typing import Any, Callable, TypeVar

from .metrics import metrics_enabled, record_agent_phase, record_method

F = TypeVar("F", bound=Callable[..., Any])

logger = logging.getLogger(__name__)


def _target_name(func: Callable[..., Any], args: tuple[Any, ...]) -> str:
    """``Class.method`` when called on an instance, else ``module.function``."""
    if args:
        first = args[0]
        cls = type(first)
        if getattr(cls, "__module__", "builtins") != "builtins":
            return f"{cls.__name__}.{func.__name__}"
    qual = getattr(func, "__qualname__", func.__name__)
    if "." in qual:
        return qual
    module = (func.__module__ or "unknown").rsplit(".", 1)[-1]
    return f"{module}.{func.__name__}"


def _error_class(exc: BaseException) -> str:
    """The most specific useful class name, following ``__cause__`` once."""
    if exc.__cause__ is not None:
        return type(exc.__cause__).__name__
    return type(exc).__name__


def method_metrics(
    *, phase: str | None = None, target: str | None = None
) -> Callable[[F], F]:
    """Measure one callable.

    ``phase`` additionally records the call as an agent-turn phase, which is what
    lets a dashboard line up "graph build" against "model call" on one timeline.
    ``target`` overrides the derived name when a stable label is wanted (derived
    names change if a class is renamed).
    """

    def decorator(func: F) -> F:
        name = target or getattr(func, "__name__", "callable")

        def _finish(resolved: str, started: float, exc: BaseException | None) -> None:
            if not metrics_enabled():
                return
            elapsed = time.perf_counter() - started
            status = "error" if exc is not None else "success"
            record_method(
                target=resolved,
                duration=elapsed,
                status=status,
                error_type=_error_class(exc) if exc is not None else None,
            )
            if phase:
                record_agent_phase(phase=phase, duration=elapsed, outcome=status)

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                resolved = target or _target_name(func, args)
                started = time.perf_counter()
                exc: BaseException | None = None
                try:
                    return await func(*args, **kwargs)
                except BaseException as caught:
                    exc = caught
                    raise
                finally:
                    _finish(resolved, started, exc)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            resolved = target or _target_name(func, args)
            started = time.perf_counter()
            exc: BaseException | None = None
            try:
                return func(*args, **kwargs)
            except BaseException as caught:
                exc = caught
                raise
            finally:
                _finish(resolved, started, exc)

        return sync_wrapper  # type: ignore[return-value]

    return decorator
