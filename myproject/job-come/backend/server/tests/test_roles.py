"""`roles.yaml` and the skill packages are one model. These checks hold them to each other.

`jc.agent.roles` checks the file's structure at load, and checks against the skill packages that
every skill is owned by exactly one role. What remains is checked here: that every scenario is
routed, every DeerFlow model is declared, every turn provider and switch predicate is registered,
every tool a skill names exists, and that no other file re-declares a role or a skill.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from jc.agent.roles import (
    RoleConfigError,
    UnknownRoleError,
    default_role,
    entry_roles,
    role,
    role_of,
    roles,
)
from jc.agent.tool_catalog import OPENAI_TOOLS
from jc.agent.turn import PREDICATES, TURN_PROVIDERS
from jc.skills.loader import all_skill_ids, require_skill

BACKEND = Path(__file__).resolve().parents[2]
SKILLS = BACKEND / "agent" / "skills" / "public"


def _yaml(*parts: str) -> dict:
    return yaml.safe_load(BACKEND.joinpath(*parts).read_text("utf-8"))


def test_exactly_one_default_role_and_it_is_an_entry_role():
    defaults = [r.id for r in roles().values() if r.default]
    assert defaults == ["resume-coach"]
    assert default_role().id in entry_roles()


def test_the_entry_roles_are_the_three_agents_a_user_can_open():
    assert entry_roles() == ("resume-coach", "coach-mock", "apply-pipeline")


def test_every_skill_package_is_owned_by_exactly_one_role():
    declared = [skill_id for r in roles().values() for skill_id in r.skill_ids]
    assert sorted(declared) == sorted(all_skill_ids())
    assert len(declared) == len(set(declared))


def test_every_scenario_a_role_names_is_routed():
    scenarios = set(_yaml("agent", "llm", "routing.yaml")["scenarios"])
    for r in roles().values():
        assert r.scenario in scenarios, f"{r.id} uses unrouted scenario {r.scenario}"


def test_every_deerflow_model_a_session_or_subtask_runs_on_is_declared_for_its_scenario():
    declared = {m["name"]: m["model"] for m in _yaml("agent", "deerflow", "config.yaml")["models"]}
    for r in roles().values():
        if r.model_name is not None:
            assert declared.get(r.model_name) == r.scenario, (
                f"{r.id} runs on {r.model_name}, which must be declared with model: {r.scenario}"
            )


def test_config_yaml_declares_no_subagents_and_no_skill_switches():
    config = _yaml("agent", "deerflow", "config.yaml")
    assert "subagents" not in config and "subagent_runtime" not in config
    for name in ("extensions_config.json", "extensions_config.example.json"):
        text = BACKEND.joinpath("agent", "deerflow", name).read_text("utf-8")
        assert '"skills"' not in json.loads(re.sub(r"^\s*//.*$", "", text, flags=re.M)), name


def test_every_turn_provider_and_switch_predicate_a_role_names_is_registered():
    for r in roles().values():
        if r.turn is not None:
            assert r.turn in TURN_PROVIDERS, f"{r.id} names unregistered turn {r.turn}"
        for rule in r.switch:
            assert rule.when in PREDICATES, f"{r.id} names unregistered predicate {rule.when}"


def test_every_tool_a_skill_names_exists_on_the_catalog():
    catalog = {t["function"]["name"] for t in OPENAI_TOOLS}
    for skill_id in all_skill_ids():
        unknown = sorted(set(require_skill(skill_id).allowed_tools) - catalog)
        assert not unknown, f"{skill_id} names unknown tools {unknown}"


def test_a_skill_text_names_only_tools_that_skill_may_use():
    for skill_id in all_skill_ids():
        text = (SKILLS / skill_id / "SKILL.md").read_text("utf-8")
        named = set(re.findall(r"\bjc_[a-z_]+\b", text))
        extra = sorted(named - set(require_skill(skill_id).allowed_tools))
        assert not extra, f"{skill_id} SKILL.md names tools it cannot call: {extra}"


def test_the_coach_archive_skill_belongs_to_the_interview_role_and_is_reached_by_intent():
    assert role_of("coach-archive").id == "coach-mock"
    assert role("coach-mock").switch[0].to == "coach-archive"
    assert role("coach-mock").switch[0].when == "intent_archive"


def test_the_profile_interview_skill_is_reached_by_switch_only():
    assert role_of("profile-interview").id == "resume-coach"
    assert role("resume-coach").switch[0].to == "profile-interview"


def test_each_skill_declares_exactly_what_it_may_use():
    assert set(require_skill("resume-coach").allowed_tools) == {
        "jc_profile_photo_set", "jc_profile_get", "jc_profile_patch", "jc_intake_plan",
    }
    assert "jc_intake_record" in require_skill("profile-interview").allowed_tools
    assert "jc_intake_record" not in require_skill("resume-coach").allowed_tools
    assert "jc_interview_save" in require_skill("coach-archive").allowed_tools
    assert "jc_interview_save" not in require_skill("coach-mock").allowed_tools


def test_an_unknown_role_is_an_error_not_a_default():
    with pytest.raises(UnknownRoleError):
        role("no-such-role")
    with pytest.raises(UnknownRoleError):
        role_of("no-such-skill")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["coach-mock"].update(mode="single"),
        lambda d: d["resume-coach"].update(default=False),
        lambda d: d["jd-parser"].update(surprise=1),
        lambda d: d["jd-parser"].update(skills=["resume-writer"]),
        lambda d: d["coach-mock"].update(switch=[{"to": "resume-coach", "when": "intent_archive"}]),
        lambda d: d["coach-mock"].update(switch=[{"to": "coach-archive", "when": "x", "extra": 1}]),
        lambda d: d["interview-reviewer"].pop("timeout_seconds"),
        lambda d: d["resume-writer"].update(skills=["resume-writer", "resume-writer"]),
        lambda d: d["resume-writer"].update(skills=["resume-writer", "jd-parser"]),
    ],
)
def test_a_contradictory_declaration_fails_at_load(mutate, tmp_path, monkeypatch):
    import jc.agent.roles as module

    declared = _yaml("agent", "roles.yaml")
    mutate(declared)
    broken = tmp_path / "roles.yaml"
    broken.write_text(yaml.safe_dump(declared), "utf-8")
    monkeypatch.setattr(module, "agent_file", lambda *_: broken)
    module.reload_roles()
    try:
        with pytest.raises(RoleConfigError):
            module.roles()
    finally:
        monkeypatch.undo()
        module.reload_roles()
