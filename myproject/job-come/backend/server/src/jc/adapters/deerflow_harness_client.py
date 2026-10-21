"""JC adapter — thin SSE bridge over embedded DeerFlow harness."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import traceback
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from agentkit.adapters.deerflow.client import (
    AgentRunMetadata,
    DeerFlowClientConfig,
    DeerFlowSessionClient,
)
from agentkit.common.ids import new_id

from jc.agent import system_prompt_capture
from jc.agent.roles import SKILL_PROMPT_PREFIX, skills_in_scope
from jc.config import settings
from jc.paths import SERVER_ROOT

logger = logging.getLogger(__name__)

# Embedded upstream configuration and MCP pools are process-global (one
# process serves many concurrent turns, possibly for different users), but
# that no longer requires serializing runs: identity travels as explicit
# per-call arguments all the way down to the `jc` MCP tool invocation (see
# `jc.mcp.identity_interceptor`), not through mutable process state. See
# ADR-004 for the incident this replaces.
_CLIENT_CACHE: dict[str, Any] = {}
_THREAD_META: dict[str, AgentRunMetadata] = {}
_SESSION_CANCEL: dict[str, threading.Event] = {}
_PLAN_MODE_SKILLS = frozenset({"apply-pipeline"})


@contextmanager
def _audit_context(
    metadata: AgentRunMetadata | None, sink: Callable[[Any], None] | None
) -> Iterator[None]:
    """Bind this turn's identity and audit sink for the streaming thread.

    Two separate needs, both thread-scoped. The identity is what litellm cannot
    know (which user, which profile, which session), bound here because
    ContextVars set on the request task do not reach a `threading.Thread`. The
    sink exists because the async database engine's pool belongs to the request
    loop and is unusable from this thread, so finished rows are handed back
    across the queue instead of being written here.
    """
    if metadata is None:
        yield
        return

    from jc.llm import audit_hook
    from jc.llm.call_context import llm_context_scope

    with llm_context_scope(
        user_id=metadata.user_id or None,
        actor_kind="user" if metadata.user_id else None,
        profile_id=metadata.profile_id or None,
        job_id=metadata.extra.get("job_id") or None,
        session_id=metadata.session_id or None,
        skill_hint=metadata.skill_hint or None,
    ):
        if sink is None:
            yield
            return
        with audit_hook.audit_sink(sink):
            yield


#: Maximum traceback text carried into `jc_agent_trace`. A traceback from inside
#: LangGraph can exceed MySQL's TEXT limit once a deep chain re-raises, and a row
#: that fails to insert loses the whole diagnosis — the head of a traceback is the
#: least useful part, so the tail (the actual raise site) is what survives the cut.
_TRACEBACK_CAP = 24_000


@dataclass(frozen=True, slots=True)
class _HarnessFailure:
    """A run that died inside the streaming worker, with its diagnosis attached.

    Before this existed the worker handed the bare exception across the queue and
    the consumer did `str(exc)` — which for most LangGraph/litellm failures is a
    short, context-free string (often empty). The traceback stayed in the server's
    stdout only, so a failure reported by a user could not be diagnosed from the
    database at all: the one artefact that says *where* it broke was never stored.

    `stage` and `open_tools` are recorded because they answer the first question
    about any such failure without reading the traceback: did the run die before
    the model was even reached, while a tool was in flight, or on the final
    natural-language turn after every tool had already returned.
    """

    exc: BaseException
    exc_type: str
    exc_module: str
    message: str
    traceback_text: str
    open_tools: tuple[str, ...]
    stage: str

    @property
    def qualified_type(self) -> str:
        """`module.ClassName`, or the bare name for builtins."""
        if self.exc_module in {"builtins", ""}:
            return self.exc_type
        return f"{self.exc_module}.{self.exc_type}"

    def user_message(self) -> str:
        """Text for the SSE `error` event.

        Still the raw exception string, because the frontend sanitizer
        (`userFacingAgentMessage`) is what decides what a user sees and it needs
        the technical text to classify the failure (rate limit vs timeout vs
        provider outage all get different copy). What changed is that this is no
        longer the *only* surviving record of the failure.
        """
        return self.message or self.qualified_type

    def trace_payload(self) -> dict[str, Any]:
        return {
            "message": self.user_message(),
            "exception_type": self.qualified_type,
            "stage": self.stage,
            "open_tools": list(self.open_tools),
            "traceback": self.traceback_text[-_TRACEBACK_CAP:],
        }


@dataclass(slots=True)
class _ThreadState:
    metadata: AgentRunMetadata


def _jc_root() -> Path:
    return SERVER_ROOT


def resolve_mcp_python_in_extensions(
    src: Path,
    *,
    python_executable: str,
    package_src: Path,
    dest: Path,
) -> Path:
    """Rewrite stdio `python -m jc.mcp.server` to the API interpreter.

    Bare `python` follows PATH (often pyenv) and cannot import `jc`.
    """
    data = json.loads(src.read_text(encoding="utf-8"))
    src_dir = str(package_src)
    for spec in (data.get("mcpServers") or {}).values():
        if not isinstance(spec, dict):
            continue
        args = [str(a) for a in (spec.get("args") or [])]
        command = str(spec.get("command") or "")
        uses_jc_module = "jc.mcp.server" in " ".join(args)
        if not uses_jc_module:
            continue
        interpreters = {"python", "python3", "python3.12"}
        if Path(command).name in interpreters or command in interpreters:
            spec["command"] = python_executable
        env = dict(spec.get("env") or {})
        existing = env.get("PYTHONPATH") or ""
        env["PYTHONPATH"] = src_dir if not existing else f"{src_dir}{os.pathsep}{existing}"
        spec["env"] = env
        spec.setdefault("cwd", str(package_src.parent))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dest


def resolve_subagent_prompts_in_config(src: Path, *, dest: Path) -> Path:
    """Fill each declared role's `system_prompt` from its skill package.

    `config.yaml` declares JC's roles as DeerFlow subagents, and the harness schema
    requires a `system_prompt` string on each. That requirement produced the problem this
    function removes: three hand-written English lines per role, checked in beside the
    skill package that defines the same role in full. Two definitions of one role is the
    drift this codebase keeps paying for — `jc-writer` once named a different model than
    the chain it was supposed to use, in this same file, for this same reason.

    So the checked-in value is a pointer (`skill:resume-writer`) and the real text is
    composed at boot from the skill. Only the audience-independent layers go in, because
    a file written at boot has no request and the family layer is chosen from the user's
    target role; the per-request composition stays in `compose_writing_prompt`, which is
    what the live elevate and review paths already use.

    A pointer that names an unknown skill raises rather than falling back to the literal
    string: a silent fallback here means a role runs with its own id as its instructions.
    """
    from jc.skills.composer import compose_role_baseline

    data = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
    custom = ((data.get("subagents") or {}).get("custom_agents") or {})
    for name, spec in custom.items():
        if not isinstance(spec, dict):
            continue
        declared = str(spec.get("system_prompt") or "").strip()
        if not declared.startswith(SKILL_PROMPT_PREFIX):
            continue
        skill_id = declared[len(SKILL_PROMPT_PREFIX) :].strip()
        composed = compose_role_baseline(skill_id)
        if not composed.strip():
            raise RuntimeError(
                f"subagent {name!r} points at skill {skill_id!r}, which composed to nothing"
            )
        spec["system_prompt"] = composed
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return dest


def _configure_deerflow_paths(config: DeerFlowClientConfig) -> None:
    """Tell DeerFlow where config, extensions, and skills live (required, not optional)."""
    import sys

    root = _jc_root()
    # Keep generated DeerFlow state out of the project-root .deer-flow cache.
    # The cache used to contain JobCome skills, so a fresh JC runtime must never
    # discover or reuse it.  Both values are deliberately assigned (rather than
    # setdefault) to prevent a parent process from injecting another runtime.
    runtime_home = Path(settings.jc_deerflow_runtime_home)
    if not runtime_home.is_absolute():
        runtime_home = root / runtime_home
    os.environ["DEER_FLOW_PROJECT_ROOT"] = str(root)
    os.environ["DEER_FLOW_HOME"] = str(runtime_home.resolve())
    os.environ["DEER_FLOW_CONFIG_PATH"] = str(
        resolve_subagent_prompts_in_config(
            root / settings.jc_deerflow_config_path,
            dest=root / ".data" / "deerflow" / "config.runtime.yaml",
        )
    )
    os.environ["JC_SUMMARIZATION_TRIGGER_TOKENS"] = str(
        settings.resolved_summarization_trigger_tokens
    )
    os.environ.setdefault(
        "JC_SUMMARIZATION_KEEP_MESSAGES",
        str(settings.jc_summarization_keep_messages),
    )
    # PII redaction and token-budget middleware are both opt-in in
    # config.yaml via `$VAR` substitution (same mechanism as the summarization
    # thresholds above) so the on/off decision and the secret live in one
    # place (JC settings / .env), not duplicated into config.yaml literals.
    os.environ["JC_PII_REDACTION_ENABLED"] = (
        "true" if settings.jc_pii_redaction_enabled else "false"
    )
    # DeerFlow requires a >=16 char token_secret only when enabled is true; a
    # placeholder here is inert when the feature is off, so config load never
    # fails over the empty default when the toggle is off.
    os.environ["JC_PII_REDACTION_TOKEN_SECRET"] = (
        settings.jc_pii_redaction_token_secret or "jc-pii-redaction-disabled-placeholder"
    )
    os.environ["JC_TOKEN_BUDGET_ENABLED"] = (
        "true" if settings.jc_token_budget_enabled else "false"
    )
    os.environ["JC_TOKEN_BUDGET_MAX_TOKENS"] = str(settings.jc_token_budget_max_tokens)
    raw_ext = root / config.extensions_config_path
    runtime_ext = resolve_mcp_python_in_extensions(
        raw_ext,
        python_executable=sys.executable,
        package_src=root / "src",
        dest=root / ".data" / "deerflow" / "extensions_config.runtime.json",
    )
    os.environ["DEER_FLOW_EXTENSIONS_CONFIG_PATH"] = str(runtime_ext)
    os.environ["DEER_FLOW_SKILLS_PATH"] = str(root / settings.jc_skills_root)
    os.environ["JC_PRODUCT_RULES_PATH"] = str(
        root / ".." / "agent" / "deerflow" / "product_rules.md"
    )

    if settings.langfuse_public_key:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    if settings.langfuse_secret_key:
        os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    if settings.langfuse_host:
        os.environ.setdefault("LANGFUSE_BASE_URL", settings.langfuse_host)
        os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        os.environ.setdefault("LANGFUSE_TRACING", "true")


def _jc_deerflow_client_class() -> type:
    from deerflow.client import DeerFlowClient
    from langchain_core.runnables import RunnableConfig

    class JCDeerFlowClient(DeerFlowClient):
        """Embedded client with JC defaults (no blocking human-input tools)."""

        def _get_tools(self, *, model_name=None, subagent_enabled=False, mcp_plugins=None):
            from jc.agent.tool_catalog import SKILL_TOOLS
            scope = self._available_skills or set()
            allowed = {name for skill in scope for name in SKILL_TOOLS.get(skill, [])}
            # No host file, shell, browser or generic network tools in V1.
            tools = super()._get_tools(
                model_name=model_name, subagent_enabled=False, mcp_plugins=mcp_plugins
            )
            return [tool for tool in tools if tool.name.removeprefix("jc_") in allowed
                    or tool.name in allowed or tool.name == "write_todos"]

        def _get_runnable_config(self, thread_id: str, **overrides) -> RunnableConfig:
            base = super()._get_runnable_config(thread_id, **overrides)
            configurable = dict(base.get("configurable") or {})
            configurable["non_interactive"] = True
            return RunnableConfig(
                configurable=configurable,
                recursion_limit=base.get("recursion_limit", 100),
                callbacks=list(base.get("callbacks") or []) or None,
            )

    return JCDeerFlowClient


def _get_embedded_client(config: DeerFlowClientConfig, skill: str) -> Any:
    available = skills_in_scope(skill, default_companion="resume-coach")
    key = ":".join(
        [
            config.extensions_config_path,
            config.checkpoint_dsn or "",
            ",".join(sorted(available)),
        ]
    )
    if key not in _CLIENT_CACHE:
        _configure_deerflow_paths(config)
        client_cls = _jc_deerflow_client_class()
        _CLIENT_CACHE[key] = client_cls(
            config_path=os.environ["DEER_FLOW_CONFIG_PATH"],
            subagent_enabled=False,
            plan_mode=False,
            available_skills=set(available),
        )
    return _CLIENT_CACHE[key]


def _extract_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(content)


def _usage_from_end(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not data:
        return None
    usage = data.get("usage") or data.get("usage_metadata")
    if not usage:
        return None
    if isinstance(usage, dict):
        return {
            "prompt_tokens": usage.get("prompt_tokens") or usage.get("input_tokens"),
            "completion_tokens": usage.get("completion_tokens") or usage.get("output_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }
    return None


def _maybe_emit_confirm(name: str, content: str, out: list[dict[str, Any]]) -> None:
    if "profile_patch" not in name:
        return
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # A `profile_patch` tool result that fails to parse as JSON almost
        # certainly means `tool_output_budget_middleware` externalized it (see
        # the comment on `propose_patch`'s return value in
        # `profile_patch_service.py`): the raw JSON got swapped for a typed
        # text synopsis once it crossed `externalize_min_chars`. That silently
        # drops the confirm card the user needs to approve the edit, so the
        # patch is proposed but never applied with no visible error anywhere.
        # This used to `return` here with no trace at all; log loudly so the
        # failure mode shows up instead of looking like a quiet success.
        logger.warning(
            "profile_patch tool result for %r did not parse as JSON (likely "
            "externalized by tool_output_budget_middleware); no confirm event "
            "will be emitted and the user will not see a confirmation card. "
            "content_preview=%r",
            name,
            content[:200],
        )
        return
    if data.get("status") != "pending_confirm":
        return
    out.append(
        {
            "type": "confirm",
            "confirm_id": data.get("confirm_id"),
            "profile_id": data.get("profile_id"),
            "patch": data.get("patch"),
            "preview": data.get("preview"),
        }
    )


def _map_tool_start(tc: dict[str, Any], out: list[dict[str, Any]]) -> None:
    name = tc.get("name") or "tool"
    args = tc.get("args")
    out.append({"type": "tool_start", "name": name, "args": args})
    if name == "task":
        out.append(
            {
                "type": "subagent_start",
                "name": (
                    (args or {}).get("subagent_type") or (args or {}).get("agent") or "subagent"
                ),
                "description": (args or {}).get("description") or (args or {}).get("prompt"),
            }
        )


def _map_raw_event(event: Any, *, seen_tool_ids: set[str] | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    event_type = getattr(event, "type", None)
    data = getattr(event, "data", None) or {}

    if event_type == "messages-tuple":
        if data.get("type") == "ai":
            reasoning = data.get("reasoning_content") or data.get("thinking")
            if reasoning:
                full_reasoning = str(reasoning)
                # `content` is what the UI renders and must stay small — a
                # reasoning block can run to tens of thousands of characters
                # and the composer is not a log viewer. `full_content` is the
                # untruncated text for `jc_agent_trace` only: the trace table
                # is explicitly required to never be lossy (see its model
                # docstring), so the one place this string exists has to carry
                # both the UI-safe cut and the audit-safe original rather than
                # choosing one and losing the other.
                out.append(
                    {
                        "type": "thinking",
                        "content": full_reasoning[:4000],
                        "full_content": full_reasoning,
                    }
                )
            content = _extract_text(data.get("content"))
            if content:
                out.append({"type": "token", "content": content})
            for tc in data.get("tool_calls") or []:
                tc_id = str(tc.get("id") or "")
                if seen_tool_ids is not None and tc_id:
                    if tc_id in seen_tool_ids:
                        continue
                    seen_tool_ids.add(tc_id)
                _map_tool_start(tc, out)
        elif data.get("type") == "tool":
            name = data.get("name") or data.get("tool_name") or "tool"
            content = _extract_text(data.get("content"))
            # Same reasoning as `thinking` above: `result` is UI-sized, `full_result`
            # is what the trace table stores.
            out.append(
                {
                    "type": "tool_result",
                    "name": name,
                    "result": content[:2000],
                    "full_result": content,
                }
            )
            _maybe_emit_confirm(name, content, out)
            if name == "task":
                out.append({"type": "subagent_done", "name": name, "result": content[:500]})
    elif event_type == "end":
        usage = _usage_from_end(data if isinstance(data, dict) else None)
        if usage:
            out.append({"type": "usage", **usage})
        out.append({"type": "done"})
    return out


# The generic lead-agent template (`SYSTEM_PROMPT_TEMPLATE` in
# `deerflow.agents.lead_agent.prompt`) unconditionally renders a `<citations>`
# block (web_search citation formatting) and a `<working_directory>` block
# (the `/mnt/user-data/{uploads,workspace,outputs}` file contract, including
# `present_files`/`skill_manage` tool references). JC's `JCDeerFlowClient`
# never binds `web_search`, `read_file`, `write_file`, `bash`, or
# `present_files` (see `_jc_deerflow_client_class._get_tools` below, which
# filters the tool list down to the per-skill allowlist) -- both sections are
# therefore instructions about tools the model does not have, repeated on
# every call. Stripped once here, right where the rendered prompt first
# reaches JC code, so the same cleaned text also lands in `jc_agent_trace`
# (accurate to what the model actually needed, not the template's superset).
_DEAD_PROMPT_SECTIONS: tuple[re.Pattern[str], ...] = (
    re.compile(r"<citations>.*?</citations>", re.S),
    re.compile(r"<working_directory[^>]*>.*?</working_directory>", re.S),
)


def _strip_dead_prompt_sections(prompt_text: str) -> str:
    """Remove template sections that describe tools JC never binds.

    Idempotent and tolerant of the tags being absent (a future DeerFlow
    template revision that drops or renames them degrades to a no-op, not an
    error) -- this only deletes exact tag pairs, it never raises on a miss.
    Collapses the blank-line gap each removal leaves so the result reads like
    those sections were never templated in, rather than leaving double
    newlines as a tell that something was cut.
    """
    cleaned = prompt_text
    for pattern in _DEAD_PROMPT_SECTIONS:
        cleaned = pattern.sub("", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def close_open_tools(open_tools: list[str]) -> list[dict[str, Any]]:
    """Emit synthetic tool_result events so UI/checkpoint never keep a half-open tool."""
    events: list[dict[str, Any]] = []
    while open_tools:
        name = open_tools.pop()
        events.append({"type": "tool_result", "name": name, "result": "[cancelled]"})
    return events


def _stream_producer(
    client: Any,
    message: str,
    *,
    thread_id: str,
    stream_kwargs: dict[str, Any],
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue[tuple[str, Any]],
    cancel_event: threading.Event | None = None,
    metadata: AgentRunMetadata | None = None,
    config: DeerFlowClientConfig | None = None,
    log_sink: Callable[[Any], None] | None = None,
) -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    def _put(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, ("event", event))

    # Bound before the `try` so the failure handler can report which tools were
    # still open when the run died. That is the single most useful fact for
    # telling "the model never called a tool" apart from "the tool ran and the
    # final-answer turn is what blew up", and a name bound inside the `try`
    # would be unavailable in `except` for exactly the early failures that
    # need explaining most.
    open_tools: list[str] = []
    stage = "startup"
    try:
        if client is None and metadata is not None:
            if cancel_event and cancel_event.is_set():
                return
            client = _get_embedded_client(config, metadata.skill_hint or "resume-coach")
        seen_tool_ids: set[str] = set()
        stage = "stream"
        # The system prompt is captured by `JCProductRulesMiddleware` from inside
        # the model call (see `jc.agent.system_prompt_capture`), which happens
        # after this loop has started: `client.stream` is a generator, so no
        # model call has run until the first item is pulled. Hence the read is
        # retried on each event until it yields something, rather than once
        # after the first — the first raw event can be emitted by graph setup
        # before the model is reached, and a single attempt there would miss
        # the prompt for exactly those runs.
        #
        # The previous implementation read `client.rendered_system_prompt`,
        # which the vendored upstream does not define: the getattr returned
        # None on every run, so this event never fired and every session's
        # trace began at `user_message` instead of `system_prompt`. Reading
        # from JC-owned middleware instead means an upstream sync cannot
        # silently break it again.
        #
        # Emitted as a synthetic event (never produced by DeerFlow itself) so
        # `_stream_producer` has exactly one path for handing anything across
        # the thread boundary: the queue.
        emitted_system_prompt = False
        capture_key = metadata.session_id if metadata is not None else None
        with _audit_context(metadata, log_sink):
            for raw in client.stream(message, thread_id=thread_id, **stream_kwargs):
                if not emitted_system_prompt:
                    prompt_text = system_prompt_capture.take(capture_key)
                    if prompt_text:
                        emitted_system_prompt = True
                        prompt_text = _strip_dead_prompt_sections(prompt_text)
                        _put({"type": "system_prompt_rendered", "content": prompt_text})
                if cancel_event and cancel_event.is_set():
                    for mapped in close_open_tools(open_tools):
                        _put(mapped)
                    _put({"type": "error", "message": "cancelled"})
                    break
                for mapped in _map_raw_event(raw, seen_tool_ids=seen_tool_ids):
                    if mapped.get("type") == "tool_start":
                        open_tools.append(str(mapped.get("name") or "tool"))
                    elif mapped.get("type") in {"tool_result", "tool"} and open_tools:
                        open_tools.pop()
                    _put(mapped)
    except Exception as exc:  # noqa: BLE001
        # The traceback is formatted *here*, inside the `except` block, not by the
        # consumer: once this frame unwinds, `exc.__traceback__` is the only thing
        # left and formatting it across the thread boundary loses the worker frames
        # that say which DeerFlow call actually failed. The consumer gets the text.
        loop.call_soon_threadsafe(
            queue.put_nowait,
            (
                "error",
                _HarnessFailure(
                    exc=exc,
                    exc_type=type(exc).__qualname__,
                    exc_module=type(exc).__module__,
                    message=str(exc),
                    traceback_text="".join(
                        traceback.format_exception(type(exc), exc, exc.__traceback__)
                    ),
                    open_tools=tuple(open_tools),
                    stage=stage,
                ),
            ),
        )
    finally:
        # A run that died before the stream loop could read its captured prompt
        # must not leave the entry behind for this session's *next* run to pick
        # up and write to trace as its own.
        if metadata is not None:
            system_prompt_capture.discard(metadata.session_id)
        loop.call_soon_threadsafe(queue.put_nowait, ("done", None))


def register_session_cancel(session_id: str) -> threading.Event:
    event = threading.Event()
    _SESSION_CANCEL[session_id] = event
    return event


def request_session_cancel(session_id: str) -> bool:
    event = _SESSION_CANCEL.get(session_id)
    if event is None:
        return False
    event.set()
    return True


def clear_session_cancel(session_id: str) -> None:
    _SESSION_CANCEL.pop(session_id, None)


class DeerFlowHarnessSessionClient(DeerFlowSessionClient):
    """Embedded DeerFlow — LangGraph loop, middleware, subagents, compaction."""

    def __init__(self, config: DeerFlowClientConfig, *, db: Any = None) -> None:
        super().__init__(config)
        self._config = config
        self._db = db
        self._thread_state: dict[str, _ThreadState] = {}

    def bind_db(self, db: Any) -> None:
        self._db = db

    async def start_session(self, *, metadata: AgentRunMetadata) -> str:
        thread_id = new_id("thr", length=16)
        self._thread_state[thread_id] = _ThreadState(metadata=metadata)
        _THREAD_META[thread_id] = metadata
        return thread_id

    async def run_once(
        self,
        *,
        skill: str,
        metadata: AgentRunMetadata,
        context: dict[str, Any],
        db: Any = None,
    ) -> str:
        thread_id = await self.start_session(metadata=metadata)
        message = context.get("message") or context.get("prompt") or ""
        if not message:
            return ""
        parts: list[str] = []
        async for event in self.stream_message(thread_id, message, metadata=metadata, db=db):
            if event.get("type") == "token":
                parts.append(event.get("content", ""))
        return "".join(parts)

    async def stream_events(
        self, session_id: str, *, db: Any = None
    ) -> AsyncIterator[dict[str, Any]]:
        yield {
            "type": "error",
            "message": "stream_events not used; send a message via stream_message",
        }
        return

    async def stream_message(
        self,
        thread_id: str,
        message: str,
        *,
        metadata: AgentRunMetadata | None = None,
        db: Any = None,
        attachments: list | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        _ = db
        from jc.agent.message_content import flatten_message_for_text_agent
        from jc.schemas.agent import AgentAttachment

        att_models: list[AgentAttachment] = []
        for raw in attachments or []:
            if isinstance(raw, AgentAttachment):
                att_models.append(raw)
            elif isinstance(raw, dict):
                att_models.append(AgentAttachment.model_validate(raw))

        if att_models:
            message = await flatten_message_for_text_agent(message, att_models)

        meta = metadata or _THREAD_META.get(thread_id)
        if meta is None:
            yield {"type": "error", "message": "Session metadata not found"}
            yield {"type": "done"}
            return

        if thread_id not in self._thread_state:
            self._thread_state[thread_id] = _ThreadState(metadata=meta)

        skill = meta.skill_hint or "resume-coach"
        yield {"type": "skill", "name": skill}

        authz_attributes = {
            k: v
            for k, v in {
                "jc_profile_id": meta.profile_id,
                "jc_session_id": meta.session_id,
                "jc_job_id": meta.extra.get("job_id"),
                "jc_mock_session_id": meta.extra.get("mock_session_id"),
                "jc_agent_skill": meta.skill_hint,
                "jc_reply_locale": meta.extra.get("reply_locale"),
                # Selects the role-family methodology that
                # `JCProductRulesMiddleware` renders into the system layer. It
                # travels as a per-run attribute rather than being baked into
                # the agent because the embedded agent is cached per process and
                # shared across users, while the methodology is per profile.
                "jc_role_family": meta.extra.get("role_family"),
            }.items()
            if v
        }
        stream_kwargs: dict[str, Any] = {
            "user_id": meta.user_id or "default",
            "subagent_enabled": False,
            "plan_mode": skill in _PLAN_MODE_SKILLS,
            "authz_attributes": authz_attributes,
        }
        if meta.trace_id:
            stream_kwargs["run_id"] = meta.trace_id

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        session_key = meta.session_id or thread_id
        cancel_event = register_session_cancel(session_key)

        # The audit handler runs in the worker thread, where the async database
        # engine's pool is not usable. Records cross back to this loop and are
        # written here as they arrive.
        def _log_sink(record: Any) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, ("llm_log", record))

        worker = threading.Thread(
            target=_stream_producer,
            args=(None, message),
            kwargs={
                "thread_id": thread_id,
                "stream_kwargs": stream_kwargs,
                "loop": loop,
                "queue": queue,
                "cancel_event": cancel_event,
                "metadata": meta,
                "config": self._config,
                "log_sink": _log_sink,
            },
            daemon=True,
        )
        worker.start()

        saw_done = False
        try:
            while True:
                kind, payload = await queue.get()
                if kind == "done":
                    if not saw_done:
                        yield {"type": "done"}
                    break
                if kind == "error":
                    # `_HarnessFailure` carries the traceback the worker formatted
                    # while the frame was still alive. The `else` branch is the
                    # defensive path for any future producer that still queues a
                    # bare exception; it must not crash the stream.
                    if isinstance(payload, _HarnessFailure):
                        logger.error(
                            "DeerFlow harness stream failed: stage=%s type=%s\n%s",
                            payload.stage,
                            payload.qualified_type,
                            payload.traceback_text,
                        )
                        # `diagnostics` rides along on the SSE event so the trace
                        # writer in `AgentService` needs no second channel to the
                        # worker. It is stripped before the event reaches the
                        # browser (see `AgentService.stream_message`): a traceback
                        # is for the admin console, not the chat bubble.
                        yield {
                            "type": "error",
                            "message": payload.user_message(),
                            "diagnostics": payload.trace_payload(),
                        }
                    else:
                        logger.exception(
                            "DeerFlow harness stream failed", exc_info=payload
                        )
                        yield {"type": "error", "message": str(payload)}
                    yield {"type": "done"}
                    break
                if kind == "llm_log":
                    from jc.llm.call_log import record_call

                    await record_call(payload)
                    continue
                if payload.get("type") == "done":
                    saw_done = True
                yield payload
        finally:
            cancel_event.set()
            clear_session_cancel(session_key)
