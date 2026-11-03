"""How a session turn is prepared: the context its message carries, and the skill that runs it.

A role declares, in `backend/agent/roles.yaml`, a `turn` provider (how the turn's message is built
from the database) and `switch` rules (when a different skill of the role runs this turn). The
names in those declarations refer to the functions registered here. A new provider or condition is
a function here plus its name in the declaration; no code branches on a role or a skill id.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from jc.agent.coach_task import wrap_coach_mock_message
from jc.agent.resume_task import (
    coach_role_family_for,
    coach_shortfall_for,
    wrap_resume_coach_message,
)
from jc.agent.roles import Role
from jc.domain.profile_context import turn_profile_context
from jc.services.profile_intake import build_intake_plan

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TurnContext:
    """What a provider may read to prepare one turn. Built by the service, per turn."""

    db: Any
    profiles: Any
    actor: Any
    profile_id: str | None
    job_id: str | None
    ui_context: Any
    #: The role's default skill, so a provider can tell an interview turn from the default one.
    default_skill: str


class TurnProvider(Protocol):
    async def gather(self, ctx: TurnContext) -> dict[str, Any]:
        """Read what the turn needs from the database. Returns facts; may be empty."""

    def message(self, ctx: TurnContext, facts: dict[str, Any], skill: str, text: str) -> str:
        """The message the model receives: the user's words plus the turn's live context."""


class _ResumeProfile:
    """The resume session's live index: the profile digest, the focus, the role family."""

    async def gather(self, ctx: TurnContext) -> dict[str, Any]:
        if not ctx.profile_id:
            return {}
        try:
            profile = await ctx.profiles.get(ctx.profile_id, actor=ctx.actor)
            focus = ctx.ui_context.focus.path if ctx.ui_context and ctx.ui_context.focus else None
            digest = f"profile_version={profile.version}\n" + turn_profile_context(
                profile.payload, focus_path=focus
            )
            return {
                "profile_payload": profile.payload,
                "digest": digest,
                # Inferred from the profile's own titles, never from a target job: the coach edits
                # the career the user has. None yields the neutral playbook, not a guess.
                "role_family": coach_role_family_for(profile.payload),
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "profile_context unavailable profile_id=%s error_type=%s",
                ctx.profile_id, type(exc).__name__,
            )
            return {}

    def message(self, ctx: TurnContext, facts: dict[str, Any], skill: str, text: str) -> str:
        if not ctx.profile_id:
            return text
        interview = skill != ctx.default_skill
        payload = facts.get("profile_payload")
        return wrap_resume_coach_message(
            text,
            profile_id=ctx.profile_id,
            digest=facts.get("digest", ""),
            ui_context=ctx.ui_context,
            interview=interview,
            # Small live index only; detailed facts are read by tool on demand.
            include_digest=True,
            shortfall=coach_shortfall_for(payload) if interview else (),
        )


class _MockSession:
    """The interview session's live state: the job, the bound mock session, the drawn questions."""

    async def gather(self, ctx: TurnContext) -> dict[str, Any]:
        from jc.stores.interview_store import InterviewStore

        if not ctx.profile_id:
            return {}
        store = InterviewStore(ctx.db)
        mock_id = ctx.ui_context.mock_session_id if ctx.ui_context else None
        mock = await store.get_mock_session(mock_id) if mock_id else None
        drawn: list[str] = []
        if mock is not None:
            for qid in list(mock.question_ids or [])[: int(mock.bank_draw_count or 0)]:
                question = await store.get_question(qid)
                if question is not None:
                    drawn.append(question.stem)
        return {"mock_session_id": mock.id if mock is not None else None, "drawn_stems": drawn}

    def message(self, ctx: TurnContext, facts: dict[str, Any], skill: str, text: str) -> str:
        return wrap_coach_mock_message(
            text,
            profile_id=ctx.profile_id,
            job_id=ctx.job_id,
            mock_session_id=facts.get("mock_session_id"),
            drawn_stems=list(facts.get("drawn_stems", [])),
        )


TURN_PROVIDERS: dict[str, TurnProvider] = {
    "resume_profile": _ResumeProfile(),
    "mock_session": _MockSession(),
}


def _profile_cannot_generate(facts: dict[str, Any]) -> bool:
    """A profile that cannot produce a resume yet needs material, not polish."""
    payload = facts.get("profile_payload")
    return payload is not None and not build_intake_plan(payload).can_generate


def _intent_archive(facts: dict[str, Any]) -> bool:
    return facts.get("intent") == "archive"


PREDICATES: dict[str, Callable[[dict[str, Any]], bool]] = {
    "profile_cannot_generate": _profile_cannot_generate,
    "intent_archive": _intent_archive,
}


def facts_common(ui_context: Any) -> dict[str, Any]:
    """Facts every turn carries, whatever its role: the page's declared intent."""
    return {"intent": getattr(ui_context, "intent", None)}


def resolve_turn_skill(role: Role, facts: dict[str, Any]) -> str:
    """The skill this turn runs as: the first switch rule that holds, else the default skill."""
    for rule in role.switch:
        if PREDICATES[rule.when](facts):
            return rule.to
    return role.default_skill
