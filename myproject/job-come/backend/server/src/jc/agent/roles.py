"""Agent roles and skills: the loader for `backend/agent/roles.yaml`, the one declaration of both.

A **role** is who the agent is to the user and what it may do: its product, whether a session can
be opened on it, its run mode, its model scenario and its delegation. A **skill** is one way of
working: a methodology package under `skills/public/<id>/` together with the tools that way of
working needs. A role owns one or more skills; a run executes as exactly one of them and holds
only that skill's tools. These used to be spelled out separately in five modules and a harness
config file, and they drifted. Every consumer now reads this module instead:

- the harness takes a run's tool surface from `skill(...)`, and its model, plan mode and delegates
  from `role_of(...)`;
- `subagent_specs()` gives DeerFlow the subagent definitions, generated at boot;
- the API accepts only `entry_roles()` as a session's `skill_hint`;
- the composer reads each skill's `always_loaded` fragments from here;
- the isolation tests read each role's product and tools from here.

Skill *methodology* reaches the model through host-side composition in `jc.skills.composer`,
because the harness would load a SKILL.md body via `read_file` and V1 does not grant that tool.
`SKILL_PROMPT_PREFIX` marks a subagent `system_prompt` as "compose this from the named skill
package", so a role's wording is defined once in its SKILL.md.

Structure is validated here, at load, and a bad file fails the process rather than a request.
What needs other files to check (skill packages exist, scenarios are routed, DeerFlow models are
declared, tools are registered) is checked in `tests/test_roles.py`.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Any

import yaml

from jc.paths import agent_file

SKILL_PROMPT_PREFIX = "skill:"

MODES = frozenset({"session", "subtask", "single"})
PRODUCTS = frozenset({"resume", "interview", "apply", "shared"})

_ROLE_FIELDS = frozenset(
    {
        "product", "entry", "mode", "scenario", "plan_mode",
        "max_turns", "timeout_seconds", "skills",
    }
)
_SKILL_FIELDS = frozenset({"tools", "mcp", "always_loaded", "delegates"})


class RoleConfigError(ValueError):
    """`roles.yaml` is malformed or contradicts itself."""


class UnknownRoleError(LookupError):
    """A name that matches no declared role."""


class UnknownSkillError(LookupError):
    """A name that matches no declared skill."""


@dataclass(frozen=True, slots=True)
class Skill:
    id: str
    role_id: str
    tools: tuple[str, ...]
    mcp: tuple[str, ...]
    always_loaded: tuple[str, ...]
    delegates: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Role:
    id: str
    product: str
    mode: str
    scenario: str
    entry: bool
    plan_mode: bool
    max_turns: int | None
    timeout_seconds: int | None
    skills: tuple[Skill, ...]

    @property
    def default_skill(self) -> Skill:
        """The skill a session on this role starts as; it carries the role's own id."""
        return self.skills[0]

    @property
    def tools(self) -> tuple[str, ...]:
        """Every tool any of the role's skills may use. A single run holds only its skill's."""
        seen: dict[str, None] = {}
        for skill in self.skills:
            seen.update(dict.fromkeys(skill.tools))
        return tuple(seen)

    @property
    def model_name(self) -> str | None:
        """The DeerFlow model this role runs on, `jc-<scenario>`. Single calls bypass DeerFlow."""
        return None if self.mode == "single" else f"jc-{self.scenario}"


def _names(owner: str, spec: dict[str, Any], key: str) -> tuple[str, ...]:
    raw = spec.get(key) or []
    if not isinstance(raw, list) or not all(isinstance(item, str) and item for item in raw):
        raise RoleConfigError(f"{owner}.{key} must be a list of names")
    if len(set(raw)) != len(raw):
        raise RoleConfigError(f"{owner}.{key} lists a name twice")
    return tuple(raw)


def _build_skill(role_id: str, skill_id: str, spec: Any) -> Skill:
    owner = f"{role_id}.skills.{skill_id}"
    if spec is None:
        spec = {}
    if not isinstance(spec, dict):
        raise RoleConfigError(f"{owner} must be a mapping")
    unknown = set(spec) - _SKILL_FIELDS
    if unknown:
        raise RoleConfigError(f"{owner} has unknown fields: {sorted(unknown)}")
    return Skill(
        id=skill_id,
        role_id=role_id,
        tools=_names(owner, spec, "tools"),
        mcp=_names(owner, spec, "mcp"),
        always_loaded=_names(owner, spec, "always_loaded"),
        delegates=_names(owner, spec, "delegates"),
    )


def _build(role_id: str, spec: Any) -> Role:
    if not isinstance(spec, dict):
        raise RoleConfigError(f"{role_id} must be a mapping")
    unknown = set(spec) - _ROLE_FIELDS
    if unknown:
        raise RoleConfigError(f"{role_id} has unknown fields: {sorted(unknown)}")
    product, mode, scenario = spec.get("product"), spec.get("mode"), spec.get("scenario")
    if product not in PRODUCTS:
        raise RoleConfigError(f"{role_id}.product must be one of {sorted(PRODUCTS)}")
    if mode not in MODES:
        raise RoleConfigError(f"{role_id}.mode must be one of {sorted(MODES)}")
    if not isinstance(scenario, str) or not scenario:
        raise RoleConfigError(f"{role_id}.scenario is required")
    entry = spec.get("entry", False)
    plan_mode = spec.get("plan_mode", False)
    if not isinstance(entry, bool) or not isinstance(plan_mode, bool):
        raise RoleConfigError(f"{role_id}.entry and plan_mode must be true or false")
    raw_skills = spec.get("skills")
    if not isinstance(raw_skills, dict) or not raw_skills:
        raise RoleConfigError(f"{role_id}.skills must map skill ids to their declarations")
    return Role(
        id=role_id,
        product=product,
        mode=mode,
        scenario=scenario,
        entry=entry,
        plan_mode=plan_mode,
        max_turns=spec.get("max_turns"),
        timeout_seconds=spec.get("timeout_seconds"),
        skills=tuple(_build_skill(role_id, str(sid), s) for sid, s in raw_skills.items()),
    )


def _check(by_id: dict[str, Role]) -> None:
    owner_of: dict[str, str] = {}
    for role in by_id.values():
        if role.default_skill.id != role.id:
            raise RoleConfigError(
                f"{role.id}: the first skill must be the role's own, not {role.default_skill.id}"
            )
        for skill in role.skills:
            if skill.id in owner_of:
                raise RoleConfigError(
                    f"skill {skill.id} is declared by {owner_of[skill.id]} and {role.id}"
                )
            owner_of[skill.id] = role.id

        if role.entry and role.mode != "session":
            raise RoleConfigError(f"{role.id} is an entry role, so its mode must be session")
        if role.mode != "session" and (role.plan_mode or any(s.delegates for s in role.skills)):
            raise RoleConfigError(f"{role.id} is not a session, so it cannot delegate or plan")
        if role.mode != "session" and len(role.skills) != 1:
            raise RoleConfigError(f"{role.id} is not a session, so it has exactly one skill")
        if role.mode == "single" and any(s.tools or s.mcp for s in role.skills):
            raise RoleConfigError(f"{role.id} is a single call: no tools")
        if role.mode == "subtask":
            for key in ("max_turns", "timeout_seconds"):
                value = getattr(role, key)
                if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                    raise RoleConfigError(f"{role.id} is a subtask: {key} must be a positive int")
        for skill in role.skills:
            for target_id in skill.delegates:
                target = by_id.get(target_id)
                if target is None or target.mode != "subtask":
                    raise RoleConfigError(
                        f"{skill.id} delegates to {target_id}, which is not a subtask"
                    )
                if target.product not in {role.product, "shared"}:
                    raise RoleConfigError(f"{skill.id} delegates across products to {target_id}")


@functools.cache
def roles() -> dict[str, Role]:
    raw = yaml.safe_load(agent_file("roles.yaml").read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise RoleConfigError("roles.yaml must map role ids to their declarations")
    by_id = {str(role_id): _build(str(role_id), spec) for role_id, spec in raw.items()}
    _check(by_id)
    return by_id


def reload_roles() -> None:
    roles.cache_clear()


def role(role_id: str) -> Role:
    try:
        return roles()[role_id]
    except KeyError:
        raise UnknownRoleError(f"no role named {role_id!r}") from None


def skills() -> dict[str, Skill]:
    """Every declared skill, by id."""
    return {skill.id: skill for r in roles().values() for skill in r.skills}


def skill(skill_id: str) -> Skill:
    try:
        return skills()[skill_id]
    except KeyError:
        raise UnknownSkillError(f"no skill named {skill_id!r}") from None


def role_of(skill_id: str) -> Role:
    """The role a skill belongs to, and so the model, run mode and delegation a run of it gets."""
    return role(skill(skill_id).role_id)


def entry_roles() -> tuple[str, ...]:
    """Roles a user may open a session on, in declaration order."""
    return tuple(r.id for r in roles().values() if r.entry)


def hints_by_skill() -> dict[str, list[str]]:
    """Reverse index: which role each skill belongs to. For operator reporting."""
    return {s.id: [s.role_id] for s in skills().values()}


def subagent_specs() -> dict[str, dict[str, Any]]:
    """DeerFlow `subagents.custom_agents` entries, one per subtask role, derived from the roles."""
    from jc.skills.loader import require_skill

    return {
        r.id: {
            "description": require_skill(r.id).description,
            "system_prompt": f"{SKILL_PROMPT_PREFIX}{r.id}",
            "tools": list(r.default_skill.tools),
            "skills": [r.default_skill.id],
            "model": r.model_name,
            "max_turns": r.max_turns,
            "timeout_seconds": r.timeout_seconds,
        }
        for r in roles().values()
        if r.mode == "subtask"
    }
