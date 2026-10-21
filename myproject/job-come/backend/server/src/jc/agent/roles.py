"""Agent roles: what a role is allowed to reach.

Two things live here, both declarative:

- `SKILL_PROMPT_PREFIX` — marks a subagent `system_prompt` as "compose this from the
  named skill package", so a role's wording is defined once in its SKILL.md instead
  of being duplicated into harness config.
- `SKILL_SCOPE` — which skills a session's `skill_hint` may reach. This bounds the
  *tool* surface of a turn, which is the only thing the harness derives from the
  hint. Skill *methodology* reaches the model through host-side composition in
  `jc.skills.composer`, because the harness would load a SKILL.md body via
  `read_file` and V1 does not grant that tool.

This was previously private state inside the DeerFlow adapter, which meant the admin
inventory had to import underscore-prefixed names out of a transport module to answer
"what can this role do". Role permissions are a product decision and belong where
both the runtime and the inventory can read them as a first-class contract.
"""

from __future__ import annotations

SKILL_PROMPT_PREFIX = "skill:"

SKILL_SCOPE: dict[str, frozenset[str]] = {
    # resume-coach keeps its own narrow tool set on purpose: the coach edits one
    # profile and must not reach `jc_resume_review`, which is the export gate.
    "resume-coach": frozenset({"resume-coach"}),
    # Same tool surface as the coach, by design: an interview turn reads the
    # profile and writes down answers, nothing else. Reachable only if a caller
    # ever passes this as a skill hint; today the host swaps the methodology
    # inside the coach's turn, which is why the hint set stays unchanged.
    "profile-interview": frozenset({"profile-interview"}),
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


def skills_in_scope(skill_hint: str, *, default_companion: str | None = None) -> frozenset[str]:
    """Skills reachable from a hint. Unknown hints resolve to themselves only."""
    fallback = frozenset({skill_hint} | ({default_companion} if default_companion else set()))
    return SKILL_SCOPE.get(skill_hint, fallback)


def hints_by_skill() -> dict[str, list[str]]:
    """Reverse index: which hints can reach each skill. For operator reporting."""
    out: dict[str, list[str]] = {}
    for hint, skills in SKILL_SCOPE.items():
        for skill in skills:
            out.setdefault(skill, []).append(hint)
    return out
