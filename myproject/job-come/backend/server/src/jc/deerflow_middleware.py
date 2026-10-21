"""JC DeerFlow harness middleware — product rules + session context injection."""

from __future__ import annotations

import os
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, override

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime

_REMINDER_KEY = "jc_product_rules"


@lru_cache(maxsize=1)
def _load_product_rules() -> str:
    path = os.environ.get("JC_PRODUCT_RULES_PATH")
    if not path:
        return ""
    file_path = Path(path)
    if not file_path.is_file():
        return ""
    return file_path.read_text(encoding="utf-8").strip()


def _authz_attributes(runtime: Runtime | None) -> dict[str, Any]:
    """Return this run's `authz_attributes`, or `{}`.

    Read from `runtime.context` — the per-run LangGraph context that
    `DeerFlowClient._stream_turn` populates from the `authz_attributes`
    kwarg passed into `client.stream(...)` — never from `os.environ`. The
    stdio MCP connection pool and the embedded agent's middleware chain are
    both process-global and reused across concurrent turns for different
    users; a value read from `os.environ` here would be whichever turn
    wrote it last, not necessarily this one. `runtime.context` is this
    turn's own LangGraph `Runtime`, resolved per call by the graph, so it
    cannot be clobbered by a concurrent turn (see ADR-004).
    """
    if runtime is None:
        return {}
    context = getattr(runtime, "context", None)
    attributes = context.get("authz_attributes") if isinstance(context, dict) else None
    return attributes if isinstance(attributes, dict) else {}


def _session_context_block(runtime: Runtime | None) -> str:
    attributes = _authz_attributes(runtime)
    lines: list[str] = []
    skill = attributes.get("jc_agent_skill") or "resume-coach"
    lines.append(f"skill={skill}")
    if user_id := (getattr(runtime, "context", None) or {}).get("user_id"):
        lines.append(f"user_id={user_id}")
    if profile_id := attributes.get("jc_profile_id"):
        lines.append(f"profile_id={profile_id}")
        lines.append("bound_resume=true")
        # `do_not_introduce` / `ask_clarification_when_facts_missing` used to be
        # asserted here as bare key=value flags *and* spelled out in prose inside
        # every user turn. They are now stated once, as prose, in the standing
        # block below -- a flag the model has to interpret is strictly weaker
        # than the sentence it was meant to abbreviate.
    if job_id := attributes.get("jc_job_id"):
        lines.append(f"job_id={job_id}")
    if session_id := attributes.get("jc_session_id"):
        lines.append(f"agent_session_id={session_id}")
    return "\n".join(lines)


def _reply_language_block(runtime: Runtime | None) -> str:
    from jc.agent.reply_locale import reply_language_instruction

    locale = _authz_attributes(runtime).get("jc_reply_locale") or "zh-CN"
    return reply_language_instruction(locale)


def _standing_block(runtime: Runtime | None) -> str:
    """This session's standing instructions — framing, conduct, methodology.

    Previously these were prepended to every `HumanMessage` as literal text (see
    `jc.agent.standing_instructions` for why that was wrong and what moved).
    `jc_role_family` rides in `authz_attributes` alongside the ids the rest of
    this module reads, so the methodology is selected per run without any
    process-global state.
    """
    from jc.agent.standing_instructions import build_standing_block

    attributes = _authz_attributes(runtime)
    return build_standing_block(
        skill_id=attributes.get("jc_agent_skill"),
        role_family=attributes.get("jc_role_family"),
        reply_language=_reply_language_block(runtime),
    )


def _build_reminder(runtime: Runtime | None) -> str:
    rules = _load_product_rules()
    context = _session_context_block(runtime)
    parts = ["<system-reminder>", "<jc_context>"]
    if rules:
        parts.extend(["<product_rules>", rules, "</product_rules>"])
    if context:
        parts.extend(["<session>", context, "</session>"])
    # `<reply_language>` is no longer emitted separately: it is the first section
    # of the standing block, which is where the rest of the per-session policy
    # now lives. Emitting both is what made the language rule arrive twice.
    standing = _standing_block(runtime)
    if standing:
        parts.extend(["<session_instructions>", standing, "</session_instructions>"])
    parts.extend(["</jc_context>", "</system-reminder>"])
    return "\n".join(parts)


def _already_injected(messages: list) -> bool:
    for message in messages:
        kwargs = getattr(message, "additional_kwargs", None) or {}
        if kwargs.get(_REMINDER_KEY):
            return True
    return False


def _last_human(messages: list) -> HumanMessage | None:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return message
    return None


class JCProductRulesMiddleware(AgentMiddleware):
    """Inject L1 product rules once per thread (frozen-snapshot on first user turn).

    Also captures the run's system message on the way to the provider — see
    `wrap_model_call`. The two jobs live in one middleware because they are the
    same concern viewed from both ends: this class is the only JC-owned code in
    the model-call path, so it is both what adds JC's instructions and the only
    place that can observe the final text they ended up inside.
    """

    @override
    def before_agent(self, state, runtime: Runtime) -> dict:  # noqa: ANN001
        return self._inject(state, runtime)

    @override
    async def abefore_agent(self, state, runtime: Runtime) -> dict:  # noqa: ANN001
        return self._inject(state, runtime)

    @override
    def wrap_model_call(self, request, handler):  # noqa: ANN001, ANN201
        self._capture_system_prompt(request)
        return handler(request)

    @override
    async def awrap_model_call(self, request, handler):  # noqa: ANN001, ANN201
        self._capture_system_prompt(request)
        return await handler(request)

    def _capture_system_prompt(self, request) -> None:  # noqa: ANN001
        """Record the system message this call is about to send.

        Taken from `ModelRequest.system_message` rather than from the client or
        the prompt template: this is the text after the whole middleware chain
        has run, which is what the model actually receives and therefore the
        only version worth replaying from `jc_agent_trace`.

        `session_id` comes from this run's `authz_attributes`, the same per-run
        `runtime.context` the rest of this class reads, so a concurrent turn for
        a different user cannot be credited with this prompt (see ADR-004).

        Wrapped in a blanket `except` on purpose: this is observability on the
        hot path of every model call. A capture that fails must not take the
        user's conversation down with it.
        """
        try:
            from jc.agent import system_prompt_capture

            session_id = _authz_attributes(getattr(request, "runtime", None)).get(
                "jc_session_id"
            )
            message = getattr(request, "system_message", None)
            text = getattr(message, "content", None) if message is not None else None
            if isinstance(text, list):
                # Multi-part content: keep only the text parts, in order.
                text = "\n".join(
                    str(part.get("text", ""))
                    for part in text
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            if isinstance(text, str):
                system_prompt_capture.record(session_id, text)
        except Exception:  # noqa: BLE001, S110
            pass

    def _inject(self, state, runtime: Runtime | None) -> dict:  # noqa: ANN001
        messages = list(state.get("messages") or [])
        if _already_injected(messages):
            return {}

        reminder = _build_reminder(runtime)
        if not reminder.strip():
            return {}

        target = _last_human(messages)
        if target is None:
            return {
                "messages": [
                    SystemMessage(
                        content=reminder,
                        additional_kwargs={"hide_from_ui": True, _REMINDER_KEY: True},
                    )
                ]
            }

        stable_id = target.id or str(uuid.uuid4())
        reminder_msg = SystemMessage(
            id=stable_id,
            content=reminder,
            additional_kwargs={"hide_from_ui": True, _REMINDER_KEY: True},
        )
        user_copy = HumanMessage(
            id=f"{stable_id}__user",
            content=target.content,
            additional_kwargs=dict(getattr(target, "additional_kwargs", None) or {}),
        )
        return {"messages": [reminder_msg, user_copy]}
