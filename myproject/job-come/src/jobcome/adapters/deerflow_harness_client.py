"""JobCome adapter — thin SSE bridge over embedded DeerFlow harness."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentkit.adapters.deerflow.client import AgentRunMetadata, DeerFlowClientConfig, DeerFlowSessionClient
from agentkit.common.ids import new_id

from jobcome.config import settings

logger = logging.getLogger(__name__)

_CLIENT_CACHE: dict[str, Any] = {}
_THREAD_META: dict[str, AgentRunMetadata] = {}
_SESSION_CANCEL: dict[str, threading.Event] = {}
_PLAN_MODE_SKILLS = frozenset({"apply-pipeline"})
_SKILL_SCOPE: dict[str, frozenset[str]] = {
    "resume-coach": frozenset({"resume-coach"}),
    "resume-writer": frozenset({"resume-writer", "resume-reviewer"}),
    "resume-reviewer": frozenset({"resume-reviewer"}),
    "coach-mock": frozenset({"coach-mock", "coach-answer"}),
    "coach-answer": frozenset({"coach-answer"}),
    "coach-archive": frozenset({"coach-archive"}),
    "jd-parser": frozenset({"jd-parser"}),
    "apply-pipeline": frozenset(
        {"apply-pipeline", "resume-writer", "resume-reviewer", "jd-parser"}
    ),
}


@dataclass(slots=True)
class _ThreadState:
    metadata: AgentRunMetadata


def _jobcome_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_mcp_python_in_extensions(
    src: Path,
    *,
    python_executable: str,
    package_src: Path,
    dest: Path,
) -> Path:
    """Rewrite stdio `python -m jobcome.mcp.server` to the API interpreter.

    Bare `python` follows PATH (often pyenv) and cannot import `jobcome`.
    """
    data = json.loads(src.read_text(encoding="utf-8"))
    src_dir = str(package_src)
    for spec in (data.get("mcpServers") or {}).values():
        if not isinstance(spec, dict):
            continue
        args = [str(a) for a in (spec.get("args") or [])]
        command = str(spec.get("command") or "")
        uses_jobcome_module = "jobcome.mcp.server" in " ".join(args)
        if not uses_jobcome_module:
            continue
        if Path(command).name in {"python", "python3", "python3.12"} or command in {"python", "python3"}:
            spec["command"] = python_executable
        env = dict(spec.get("env") or {})
        existing = env.get("PYTHONPATH") or ""
        env["PYTHONPATH"] = src_dir if not existing else f"{src_dir}{os.pathsep}{existing}"
        spec["env"] = env
        spec.setdefault("cwd", str(package_src.parent))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dest


def _configure_deerflow_paths(config: DeerFlowClientConfig) -> None:
    """Tell DeerFlow where config, extensions, and skills live (required, not optional)."""
    import sys

    root = _jobcome_root()
    os.environ["DEER_FLOW_CONFIG_PATH"] = str(root / settings.job_come_deerflow_config_path)
    os.environ["JOB_COME_SUMMARIZATION_TRIGGER_TOKENS"] = str(
        settings.resolved_summarization_trigger_tokens
    )
    os.environ.setdefault(
        "JOB_COME_SUMMARIZATION_KEEP_MESSAGES",
        str(settings.job_come_summarization_keep_messages),
    )
    raw_ext = root / config.extensions_config_path
    runtime_ext = resolve_mcp_python_in_extensions(
        raw_ext,
        python_executable=sys.executable,
        package_src=root / "src",
        dest=root / ".data" / "deerflow" / "extensions_config.runtime.json",
    )
    os.environ["DEER_FLOW_EXTENSIONS_CONFIG_PATH"] = str(runtime_ext)
    os.environ["DEER_FLOW_SKILLS_PATH"] = str(root / settings.job_come_skills_root)
    os.environ["JOB_COME_PRODUCT_RULES_PATH"] = str(
        root / "deploy" / "deerflow" / "product_rules.md"
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


def _jobcome_deerflow_client_class() -> type:
    from deerflow.client import DeerFlowClient
    from langchain_core.runnables import RunnableConfig

    class JobComeDeerFlowClient(DeerFlowClient):
        """Embedded client with JobCome defaults (no blocking human-input tools)."""

        def _get_runnable_config(self, thread_id: str, **overrides) -> RunnableConfig:
            base = super()._get_runnable_config(thread_id, **overrides)
            configurable = dict(base.get("configurable") or {})
            configurable["non_interactive"] = True
            return RunnableConfig(
                configurable=configurable,
                recursion_limit=base.get("recursion_limit", 100),
                callbacks=base.get("callbacks"),
            )

    return JobComeDeerFlowClient


def _get_embedded_client(config: DeerFlowClientConfig, skill: str) -> Any:
    available = _SKILL_SCOPE.get(skill, frozenset({skill, "resume-coach"}))
    key = ":".join(
        [
            config.extensions_config_path,
            config.checkpoint_dsn or "",
            ",".join(sorted(available)),
        ]
    )
    if key not in _CLIENT_CACHE:
        _configure_deerflow_paths(config)
        client_cls = _jobcome_deerflow_client_class()
        _CLIENT_CACHE[key] = client_cls(
            config_path=os.environ["DEER_FLOW_CONFIG_PATH"],
            subagent_enabled=True,
            plan_mode=False,
            available_skills=set(available),
        )
    return _CLIENT_CACHE[key]


def _apply_mcp_env(metadata: AgentRunMetadata) -> None:
    if metadata.user_id:
        os.environ["JOB_COME_MCP_USER_ID"] = metadata.user_id
    if metadata.profile_id:
        os.environ["JOB_COME_MCP_PROFILE_ID"] = metadata.profile_id
    if metadata.session_id:
        os.environ["JOB_COME_MCP_SESSION_ID"] = metadata.session_id
    elif "JOB_COME_MCP_SESSION_ID" in os.environ:
        del os.environ["JOB_COME_MCP_SESSION_ID"]
    if metadata.skill_hint:
        os.environ["JOB_COME_AGENT_SKILL"] = metadata.skill_hint
    elif "JOB_COME_AGENT_SKILL" in os.environ:
        del os.environ["JOB_COME_AGENT_SKILL"]
    job_id = metadata.extra.get("job_id")
    if job_id:
        os.environ["JOB_COME_MCP_JOB_ID"] = str(job_id)
    elif "JOB_COME_MCP_JOB_ID" in os.environ:
        del os.environ["JOB_COME_MCP_JOB_ID"]
    reply_locale = metadata.extra.get("reply_locale")
    if reply_locale:
        os.environ["JOB_COME_AGENT_REPLY_LOCALE"] = str(reply_locale)
    elif "JOB_COME_AGENT_REPLY_LOCALE" in os.environ:
        del os.environ["JOB_COME_AGENT_REPLY_LOCALE"]


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
                "name": (args or {}).get("subagent_type") or (args or {}).get("agent") or "subagent",
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
                out.append({"type": "thinking", "content": str(reasoning)[:4000]})
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
            out.append({"type": "tool_result", "name": name, "result": content[:2000]})
            _maybe_emit_confirm(name, content, out)
            if name == "task":
                out.append({"type": "subagent_done", "name": name, "result": content[:500]})
    elif event_type == "end":
        usage = _usage_from_end(data if isinstance(data, dict) else None)
        if usage:
            out.append({"type": "usage", **usage})
        out.append({"type": "done"})
    return out


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
) -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    def _put(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, ("event", event))

    try:
        seen_tool_ids: set[str] = set()
        open_tools: list[str] = []
        for raw in client.stream(message, thread_id=thread_id, **stream_kwargs):
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
        loop.call_soon_threadsafe(queue.put_nowait, ("error", exc))
    finally:
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

    async def stream_events(self, session_id: str, *, db: Any = None) -> AsyncIterator[dict[str, Any]]:
        yield {"type": "error", "message": "stream_events not used; send a message via stream_message"}
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
        from jobcome.agent.message_content import flatten_message_for_text_agent
        from jobcome.schemas.agent import AgentAttachment

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

        _apply_mcp_env(meta)
        client = _get_embedded_client(self._config, skill)
        stream_kwargs: dict[str, Any] = {
            "user_id": meta.user_id or "default",
            "subagent_enabled": True,
            "plan_mode": skill in _PLAN_MODE_SKILLS,
        }
        if meta.trace_id:
            stream_kwargs["run_id"] = meta.trace_id

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        session_key = meta.session_id or thread_id
        cancel_event = register_session_cancel(session_key)
        worker = threading.Thread(
            target=_stream_producer,
            args=(client, message),
            kwargs={
                "thread_id": thread_id,
                "stream_kwargs": stream_kwargs,
                "loop": loop,
                "queue": queue,
                "cancel_event": cancel_event,
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
                    logger.exception("DeerFlow harness stream failed", exc_info=payload)
                    yield {"type": "error", "message": str(payload)}
                    yield {"type": "done"}
                    break
                if payload.get("type") == "done":
                    saw_done = True
                yield payload
        finally:
            clear_session_cancel(session_key)
