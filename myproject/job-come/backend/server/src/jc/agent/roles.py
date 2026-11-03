"""Agent roles: the loader for `backend/agent/roles.yaml`, the one declaration of every role.

A role is a skill package plus a tool allowlist, a run mode, a model scenario and its
delegation. Those used to be spelled out separately in five modules and a harness config file,
and they drifted. Every consumer now reads this module instead:

- the harness takes a run's tool surface, model, plan mode and delegates from `role(...)`;
- `subagent_specs()` gives DeerFlow the subagent definitions, generated at boot;
- the API accepts only `entry_roles()` as a session's `skill_hint`;
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

_FIELDS = frozenset(
    {
        "product", "entry", "mode", "scenario", "tools", "mcp", "delegates", "swap_to",
        "plan_mode", "max_turns", "timeout_seconds",
    }
)


class RoleConfigError(ValueError):
    """`roles.yaml` is malformed or contradicts itself."""


class UnknownRoleError(LookupError):
    """A skill hint that names no declared role."""


@dataclass(frozen=True, slots=True)
class Role:
    id: str
    product: str
    mode: str
    scenario: str
    entry: bool
    tools: tuple[str, ...]
    mcp: tuple[str, ...]
    delegates: tuple[str, ...]
    swap_to: tuple[str, ...]
    plan_mode: bool
    max_turns: int | None
    timeout_seconds: int | None

    @property
    def model_name(self) -> str | None:
        """The DeerFlow model this role runs on, `jc-<scenario>`. Single calls bypass DeerFlow."""
        return None if self.mode == "single" else f"jc-{self.scenario}"


def _names(role_id: str, spec: dict[str, Any], key: str) -> tuple[str, ...]:
    raw = spec.get(key) or []
    if not isinstance(raw, list) or not all(isinstance(item, str) and item for item in raw):
        raise RoleConfigError(f"{role_id}.{key} must be a list of names")
    if len(set(raw)) != len(raw):
        raise RoleConfigError(f"{role_id}.{key} lists a name twice")
    return tuple(raw)


def _build(role_id: str, spec: Any) -> Role:
    if not isinstance(spec, dict):
        raise RoleConfigError(f"{role_id} must be a mapping")
    unknown = set(spec) - _FIELDS
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
    return Role(
        id=role_id,
        product=product,
        mode=mode,
        scenario=scenario,
        entry=entry,
        tools=_names(role_id, spec, "tools"),
        mcp=_names(role_id, spec, "mcp"),
        delegates=_names(role_id, spec, "delegates"),
        swap_to=_names(role_id, spec, "swap_to"),
        plan_mode=plan_mode,
        max_turns=spec.get("max_turns"),
        timeout_seconds=spec.get("timeout_seconds"),
    )


def _check(by_id: dict[str, Role]) -> None:
    for role in by_id.values():
        if role.entry and role.mode != "session":
            raise RoleConfigError(f"{role.id} is an entry role, so its mode must be session")
        if role.mode == "single" and (role.tools or role.mcp or role.delegates or role.swap_to):
            raise RoleConfigError(f"{role.id} is a single call: no tools or delegates")
        if role.mode != "session" and (role.delegates or role.swap_to or role.plan_mode):
            raise RoleConfigError(f"{role.id} is not a session, so it cannot delegate or swap")
        if role.mode == "subtask":
            for key in ("max_turns", "timeout_seconds"):
                value = getattr(role, key)
                if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                    raise RoleConfigError(f"{role.id} is a subtask: {key} must be a positive int")
        for target_id in role.delegates:
            target = by_id.get(target_id)
            if target is None or target.mode != "subtask":
                raise RoleConfigError(f"{role.id} delegates to {target_id}, which is not a subtask")
            if target.product not in {role.product, "shared"}:
                raise RoleConfigError(f"{role.id} delegates across products to {target_id}")
        for target_id in role.swap_to:
            target = by_id.get(target_id)
            if target is None or target.mode != "session" or target.product != role.product:
                raise RoleConfigError(
                    f"{role.id} swaps to {target_id}, which is not a session role of its product"
                )


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


def entry_roles() -> tuple[str, ...]:
    """Roles a user may open a session on, in declaration order."""
    return tuple(r.id for r in roles().values() if r.entry)


def hints_by_skill() -> dict[str, list[str]]:
    """Reverse index: which hints reach each skill, directly or by swapping it in."""
    out: dict[str, list[str]] = {}
    for r in roles().values():
        for skill in (r.id, *r.swap_to):
            out.setdefault(skill, []).append(r.id)
    return out


def subagent_specs() -> dict[str, dict[str, Any]]:
    """DeerFlow `subagents.custom_agents` entries, one per subtask role, derived from the roles."""
    from jc.skills.loader import require_skill

    return {
        r.id: {
            "description": require_skill(r.id).description,
            "system_prompt": f"{SKILL_PROMPT_PREFIX}{r.id}",
            "tools": list(r.tools),
            "skills": [r.id],
            "model": r.model_name,
            "max_turns": r.max_turns,
            "timeout_seconds": r.timeout_seconds,
        }
        for r in roles().values()
        if r.mode == "subtask"
    }
