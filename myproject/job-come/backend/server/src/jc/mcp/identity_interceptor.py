"""Inject this run's identity into every `jc` MCP tool call.

The `jc` MCP server is a pooled stdio subprocess (deerflow.mcp.session_pool):
one process instance serves many turns and many users across the process's
lifetime, so a value set once at process/connection start (env vars) cannot
carry a per-turn identity — a concurrent turn for a different user would
read or clobber it mid-flight. See ADR-004 for the incident this interceptor
replaces (a process-wide run lock papering over exactly that race).

Identity instead travels as explicit tool-call arguments on the JSON-RPC
`tools/call` request, scoped to that one call:
  - `jc_user_id` resolves through DeerFlow's own
    `resolve_runtime_user_id` (the framework's single source of truth for a
    tool/middleware's effective user, with LangGraph Agent Server and
    gateway fallbacks already built in).
  - `jc_profile_id` / `jc_session_id` / `jc_job_id` / `jc_mock_session_id`
    are JC's own business identity, carried through LangGraph's
    `context["authz_attributes"]` — the same request-scoped channel
    DeerFlow uses for `user_role` / `oauth_id` / `channel_user_id`, read
    from `request.runtime.context` (never from `os.environ`).

Every `jc_*` tool declares these as ordinary parameters so the model's JSON
schema includes them (FastMCP has no mechanism to hide one of several
non-context parameters from the schema while still receiving it — see the
ADR for the alternatives this rules out). The model may see or try to fill
them; it does not matter. This interceptor runs last in the composed chain
(registered after the review-gate interceptor) and *always* overwrites them,
so whatever the model supplies is replaced before the call reaches
`jc.mcp.server`. A call that somehow reaches the server without this
interceptor (a bypassed dispatch path, a unit test) gets unset identity,
which every guard in `jc.authz.ownership` fails closed on.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_IDENTITY_ARG_NAMES = (
    "jc_user_id",
    "jc_profile_id",
    "jc_session_id",
    "jc_job_id",
    "jc_mock_session_id",
)


def _current_runtime() -> Any | None:
    """Best-effort access to the LangGraph runtime for the current tool call.

    Mirrors `deerflow.mcp.user_scoped_auth._current_runtime`: `get_runtime()`
    raises outside a runtime context (embedded clients outside a run, unit
    tests, discovery paths). A failure here means identity resolves to
    unset, not to a stale or foreign value — the ownership guards fail
    closed on that.
    """
    try:
        from langgraph.runtime import get_runtime

        return get_runtime()
    except Exception:
        return None


def _resolve_identity(runtime: Any | None) -> dict[str, str]:
    """Resolve this call's identity from the run's authenticated context.

    `user_id` goes through DeerFlow's own resolver so it shares every
    fallback (Agent Server `server_info`, `langgraph_auth_user_id`,
    gateway-injected `context["user_id"]`, the request ContextVar) that the
    framework's other identity consumers already rely on. The JC-specific
    fields are plain lookups in `context["authz_attributes"]`, which is
    exactly where DeerFlowClient._stream_turn places the `authz_attributes`
    kwarg passed into `client.stream(...)` (see `deerflow_harness_client.py`).
    """
    from deerflow.runtime.user_context import resolve_runtime_user_id

    resolved: dict[str, str] = {}
    user_id = resolve_runtime_user_id(runtime)
    if user_id:
        resolved["jc_user_id"] = user_id

    context = getattr(runtime, "context", None)
    attributes = context.get("authz_attributes") if isinstance(context, dict) else None
    if isinstance(attributes, dict):
        for key in ("jc_profile_id", "jc_session_id", "jc_job_id", "jc_mock_session_id"):
            value = attributes.get(key)
            if isinstance(value, str) and value:
                resolved[key] = value

    return resolved


def build_jc_identity_interceptor(*, server_name: str = "jc") -> Any:
    """Build the interceptor that stamps every `jc` tool call with run identity."""

    async def interceptor(request: Any, handler: Any) -> Any:
        if request.server_name != server_name:
            return await handler(request)

        runtime = getattr(request, "runtime", None)
        if runtime is None:
            runtime = _current_runtime()

        identity = _resolve_identity(runtime)
        if not identity:
            logger.warning(
                "jc identity interceptor resolved no identity for tool '%s'; "
                "the call will reach jc.mcp.server unauthenticated",
                getattr(request, "name", "?"),
            )
            return await handler(request)

        args = dict(getattr(request, "args", None) or {})
        for name in _IDENTITY_ARG_NAMES:
            args.pop(name, None)
        args.update(identity)
        return await handler(request.override(args=args))

    return interceptor
