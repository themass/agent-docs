"""One model call for a single-call role: the skill is the prompt, the role names the model.

A single-call role (`mode: single` in roles.yaml) has no tools and no conversation. Its skill body
and fragments are the system prompt; its scenario picks the failover chain. Services call this with
the skill id and the user's messages, and never name a model or a scenario themselves.
"""

from __future__ import annotations

from typing import Any

from jc.agent.roles import role_of
from jc.llm.router import get_llm_router
from jc.skills.composer import compose_skill_prompt


def chain_length(skill_id: str) -> int:
    """How many endpoints the skill's model chain has, for sizing per-attempt budgets."""
    return len(get_llm_router().chain_for(role_of(skill_id).scenario))


async def run_single(
    skill_id: str,
    *,
    messages: list[dict[str, Any]],
    system: str | None = None,
    **options: Any,
) -> Any:
    """Call the skill's model once with the skill as the system prompt.

    `system` replaces the default composition when the caller composes a per-request prompt (the
    writer and the reviewer add a playbook). `options` are the router's own (`response_validator`,
    `log_context`, `timeout_seconds`, ...), passed through unchanged.
    """
    declared = role_of(skill_id)
    if declared.mode != "single":
        raise RuntimeError(f"{skill_id} is a {declared.mode} role, not a single call")
    system_text = system if system is not None else compose_skill_prompt(skill_id)
    return await get_llm_router().acompletion(
        declared.scenario,
        messages=[{"role": "system", "content": system_text}, *messages],
        **options,
    )
