"""JobCome DeerFlow harness middleware — product rules + session context injection."""

from __future__ import annotations

import os
import uuid
from functools import lru_cache
from pathlib import Path
from typing import override

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime


_REMINDER_KEY = "jobcome_product_rules"


@lru_cache(maxsize=1)
def _load_product_rules() -> str:
    path = os.environ.get("JOB_COME_PRODUCT_RULES_PATH")
    if not path:
        return ""
    file_path = Path(path)
    if not file_path.is_file():
        return ""
    return file_path.read_text(encoding="utf-8").strip()


def _session_context_block() -> str:
    lines: list[str] = []
    skill = os.environ.get("JOB_COME_AGENT_SKILL") or "resume-coach"
    lines.append(f"skill={skill}")
    if user_id := os.environ.get("JOB_COME_MCP_USER_ID"):
        lines.append(f"user_id={user_id}")
    if profile_id := os.environ.get("JOB_COME_MCP_PROFILE_ID"):
        lines.append(f"profile_id={profile_id}")
        lines.append("bound_resume=true")
        lines.append("do_not_introduce=true")
        lines.append("never_ask_clarification=true")
    if job_id := os.environ.get("JOB_COME_MCP_JOB_ID"):
        lines.append(f"job_id={job_id}")
    if session_id := os.environ.get("JOB_COME_MCP_SESSION_ID"):
        lines.append(f"agent_session_id={session_id}")
    return "\n".join(lines)


def _reply_language_block() -> str:
    from jobcome.agent.reply_locale import reply_language_instruction

    locale = os.environ.get("JOB_COME_AGENT_REPLY_LOCALE") or "zh-CN"
    return reply_language_instruction(locale)


def _build_reminder() -> str:
    rules = _load_product_rules()
    context = _session_context_block()
    parts = ["<system-reminder>", "<jobcome_context>"]
    if rules:
        parts.extend(["<product_rules>", rules, "</product_rules>"])
    if context:
        parts.extend(["<session>", context, "</session>"])
    parts.extend(["<reply_language>", _reply_language_block(), "</reply_language>"])
    parts.extend(["</jobcome_context>", "</system-reminder>"])
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


class JobComeProductRulesMiddleware(AgentMiddleware):
    """Inject L1 product rules once per thread (frozen-snapshot on first user turn)."""

    @override
    def before_agent(self, state, runtime: Runtime) -> dict:  # noqa: ANN001
        return self._inject(state)

    @override
    async def abefore_agent(self, state, runtime: Runtime) -> dict:  # noqa: ANN001
        return self._inject(state)

    def _inject(self, state) -> dict:  # noqa: ANN001
        messages = list(state.get("messages") or [])
        if _already_injected(messages):
            return {}

        reminder = _build_reminder()
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
