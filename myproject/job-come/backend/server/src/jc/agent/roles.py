"""Agent roles: the loader for `backend/agent/roles.yaml`.

A role is who the agent is to the user and how it runs. The skills it works with, and what each
skill may do, are declared by the skill packages (`jc.skills.loader`), not here. ADR-006 states the
model: roles own skills, skills declare tools, tools live on the MCP server.

Structure is checked here, at load. The cross-file invariants are checked here too, because a
skill that no role owns is dead methodology and a role that names a missing skill fails at its first
turn: every skill package is declared by exactly one role, and every role's skills exist.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Any

import yaml

from jc.paths import agent_file

MODES = frozenset({"session", "subtask", "single"})
PRODUCTS = frozenset({"resume", "interview", "apply", "shared"})

_FIELDS = frozenset(
    {
        "product", "entry", "default", "mode", "scenario", "plan_mode", "max_turns",
        "timeout_seconds", "skills", "turn", "switch",
    }
)
_SWITCH_FIELDS = frozenset({"to", "when"})


class RoleConfigError(ValueError):
    """`roles.yaml` is malformed, or disagrees with the skill packages."""


class UnknownRoleError(LookupError):
    """A name that matches no declared role."""


@dataclass(frozen=True, slots=True)
class Switch:
    to: str
    when: str


@dataclass(frozen=True, slots=True)
class Role:
    id: str
    product: str
    mode: str
    scenario: str
    entry: bool
    default: bool
    plan_mode: bool
    max_turns: int | None
    timeout_seconds: int | None
    skill_ids: tuple[str, ...]
    turn: str | None
    switch: tuple[Switch, ...]

    @property
    def default_skill(self) -> str:
        """The skill a turn runs as unless a switch rule moves it. Carries the role's own id."""
        return self.skill_ids[0]

    @property
    def model_name(self) -> str | None:
        """The DeerFlow model this role runs on, `jc-<scenario>`. Single calls bypass DeerFlow."""
        return None if self.mode == "single" else f"jc-{self.scenario}"


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
    if mode != "single" and (not isinstance(scenario, str) or not scenario):
        raise RoleConfigError(f"{role_id}.scenario is required")
    flags = {key: spec.get(key, False) for key in ("entry", "default", "plan_mode")}
    if not all(isinstance(value, bool) for value in flags.values()):
        raise RoleConfigError(f"{role_id}: entry, default and plan_mode must be true or false")
    skill_ids = spec.get("skills")
    if not isinstance(skill_ids, list) or not skill_ids or not all(
        isinstance(s, str) and s for s in skill_ids
    ):
        raise RoleConfigError(f"{role_id}.skills must be a non-empty list of skill ids")
    if len(set(skill_ids)) != len(skill_ids):
        raise RoleConfigError(f"{role_id}.skills lists a skill twice")
    turn = spec.get("turn")
    if turn is not None and not isinstance(turn, str):
        raise RoleConfigError(f"{role_id}.turn must name a turn provider")
    raw_switch = spec.get("switch") or []
    if not isinstance(raw_switch, list):
        raise RoleConfigError(f"{role_id}.switch must be a list")
    switch = []
    for rule in raw_switch:
        if not isinstance(rule, dict) or set(rule) != _SWITCH_FIELDS:
            raise RoleConfigError(f"{role_id}.switch rules take exactly `to` and `when`")
        if rule["to"] not in skill_ids:
            raise RoleConfigError(f"{role_id}.switch goes to {rule['to']}, which is not its skill")
        switch.append(Switch(to=rule["to"], when=rule["when"]))
    return Role(
        id=role_id,
        product=product,
        mode=mode,
        scenario=str(scenario or ""),
        entry=flags["entry"],
        default=flags["default"],
        plan_mode=flags["plan_mode"],
        max_turns=spec.get("max_turns"),
        timeout_seconds=spec.get("timeout_seconds"),
        skill_ids=tuple(skill_ids),
        turn=turn,
        switch=tuple(switch),
    )


def _check(by_id: dict[str, Role]) -> None:
    if sum(1 for r in by_id.values() if r.default) != 1:
        raise RoleConfigError("exactly one role must be the default")
    for role in by_id.values():
        if role.default and not role.entry:
            raise RoleConfigError(f"{role.id} is the default, so it must be an entry role")
        if role.entry and role.mode != "session":
            raise RoleConfigError(f"{role.id} is an entry role, so its mode must be session")
        if role.mode != "session" and (role.turn or role.switch or role.plan_mode):
            raise RoleConfigError(f"{role.id} is not a session: no turn, switch or plan mode")
        if role.mode == "single" and len(role.skill_ids) != 1:
            raise RoleConfigError(f"{role.id} is a single call: exactly one skill")
        if role.mode == "subtask":
            for key in ("max_turns", "timeout_seconds"):
                value = getattr(role, key)
                if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                    raise RoleConfigError(f"{role.id} is a subtask: {key} must be a positive int")


def _check_against_skills(by_id: dict[str, Role]) -> None:
    from jc.skills.loader import all_skill_ids

    declared = [s for r in by_id.values() for s in r.skill_ids]
    packages = set(all_skill_ids())
    missing = sorted(set(declared) - packages)
    if missing:
        raise RoleConfigError(f"roles name skills with no package: {missing}")
    orphans = sorted(packages - set(declared))
    if orphans:
        raise RoleConfigError(f"skill packages no role declares: {orphans}")
    if len(declared) != len(set(declared)):
        raise RoleConfigError("a skill is declared by more than one role")


@functools.cache
def roles() -> dict[str, Role]:
    raw = yaml.safe_load(agent_file("roles.yaml").read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise RoleConfigError("roles.yaml must map role ids to their declarations")
    by_id = {str(role_id): _build(str(role_id), spec) for role_id, spec in raw.items()}
    _check(by_id)
    _check_against_skills(by_id)
    return by_id


def reload_roles() -> None:
    roles.cache_clear()


def role(role_id: str) -> Role:
    try:
        return roles()[role_id]
    except KeyError:
        raise UnknownRoleError(f"no role named {role_id!r}") from None


def default_role() -> Role:
    """The role a session runs as when the caller names none."""
    return next(r for r in roles().values() if r.default)


def role_of(skill_id: str) -> Role:
    """The role that owns a skill, and so its model, run mode and plan mode."""
    for r in roles().values():
        if skill_id in r.skill_ids:
            return r
    raise UnknownRoleError(f"no role owns the skill {skill_id!r}")


def entry_roles() -> tuple[str, ...]:
    """Roles a user may open a session on, in declaration order."""
    return tuple(r.id for r in roles().values() if r.entry)
