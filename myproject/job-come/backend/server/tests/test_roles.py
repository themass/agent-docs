"""`roles.yaml` is the one declaration of every role. These checks hold it to the files it names.

`jc.agent.roles` validates the file's own structure when it loads. What needs another file to
decide is checked here: that each role has a skill package, that its scenario is routed, that its
DeerFlow model is declared, that the tools it names exist, and that no other file re-declares a
role.
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
    UnknownSkillError,
    entry_roles,
    hints_by_skill,
    role,
    role_of,
    roles,
    skill,
    skills,
)
from jc.agent.tool_catalog import OPENAI_TOOLS
from jc.mcp.handlers import TOOL_HANDLERS

BACKEND = Path(__file__).resolve().parents[2]
SKILLS = BACKEND / "agent" / "skills" / "public"


def _yaml(*parts: str) -> dict:
    return yaml.safe_load(BACKEND.joinpath(*parts).read_text("utf-8"))


def test_every_declared_skill_has_exactly_one_package_and_no_package_is_orphaned():
    packages = {p.name for p in SKILLS.iterdir() if p.is_dir()}
    assert set(skills()) == packages


def test_a_role_leads_with_the_skill_of_its_own_name():
    for r in roles().values():
        assert r.default_skill.id == r.id


def test_every_role_scenario_is_routed():
    scenarios = set(_yaml("agent", "llm", "routing.yaml")["scenarios"])
    for r in roles().values():
        assert r.scenario in scenarios, f"{r.id} uses unrouted scenario {r.scenario}"


def test_every_deerflow_model_a_role_runs_on_is_declared_for_its_scenario():
    declared = {m["name"]: m["model"] for m in _yaml("agent", "deerflow", "config.yaml")["models"]}
    for r in roles().values():
        if r.model_name is not None:
            assert declared.get(r.model_name) == r.scenario, (
                f"{r.id} runs on {r.model_name}, which must be declared with model: {r.scenario}"
            )


def test_config_yaml_does_not_redeclare_subagents():
    subagents = _yaml("agent", "deerflow", "config.yaml").get("subagents") or {}
    assert not subagents.get("custom_agents"), "subagents come from roles.yaml"


def test_the_extensions_skill_switches_name_exactly_the_roles():
    for name in ("extensions_config.json", "extensions_config.example.json"):
        text = BACKEND.joinpath("agent", "deerflow", name).read_text("utf-8")
        switches = json.loads(re.sub(r"^\s*//.*$", "", text, flags=re.M))["skills"]
        assert set(switches) == set(skills()), name


def test_the_tool_catalog_the_handlers_and_the_server_agree():
    catalog = {t["function"]["name"] for t in OPENAI_TOOLS}
    server_text = (BACKEND / "server" / "src" / "jc" / "mcp" / "server.py").read_text("utf-8")
    served = set(re.findall(r"async def (jc_[a-z_]+)\(", server_text))
    assert catalog == served == set(TOOL_HANDLERS)


def test_every_tool_a_role_names_exists():
    catalog = {t["function"]["name"] for t in OPENAI_TOOLS}
    for s in skills().values():
        unknown = sorted(set(s.tools) - catalog)
        assert not unknown, f"{s.id} names unknown tools {unknown}"


def test_no_external_mcp_is_declared_yet():
    for s in skills().values():
        assert s.mcp == (), f"{s.id}: external MCP is reserved, not connected"


def test_a_skill_text_names_only_tools_that_skill_holds():
    for s in skills().values():
        text = (SKILLS / s.id / "SKILL.md").read_text("utf-8")
        named = set(re.findall(r"\bjc_[a-z_]+\b", text))
        extra = sorted(named - set(s.tools))
        assert not extra, f"{s.id} SKILL.md names tools it cannot call: {extra}"


def test_only_session_roles_open_sessions_and_the_public_ones_are_the_three_agents():
    assert entry_roles() == ("resume-coach", "coach-mock", "apply-pipeline")


def test_a_skill_belongs_to_exactly_one_role():
    assert role_of("profile-interview").id == "resume-coach"
    assert role_of("coach-archive").id == "coach-mock"
    assert hints_by_skill()["profile-interview"] == ["resume-coach"]
    owners = [s.role_id for r in roles().values() for s in r.skills]
    assert len(owners) == len(set(s.id for r in roles().values() for s in r.skills))


def test_a_run_holds_only_the_tools_of_the_skill_it_runs_as():
    assert "jc_intake_record" not in skill("resume-coach").tools
    assert "jc_intake_record" in skill("profile-interview").tools
    assert "jc_interview_save" not in skill("coach-mock").tools
    assert "jc_interview_save" in skill("coach-archive").tools


def test_the_fragments_a_skill_loads_are_declared_on_the_skill():
    assert skill("resume-writer").always_loaded == ("structure", "method", "targeting")
    assert skill("resume-reviewer").always_loaded == ("severity", "method", "structure", "evidence")
    assert skill("interview-reviewer").always_loaded == ()


def test_an_unknown_role_is_an_error_not_a_default():
    with pytest.raises(UnknownRoleError):
        role("no-such-role")
    with pytest.raises(UnknownSkillError):
        skill("no-such-skill")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["coach-mock"].update(mode="single"),
        lambda d: d["resume-writer"]["skills"]["resume-writer"].update(tools=["jc_profile_get"]),
        lambda d: d["interview-reviewer"].pop("timeout_seconds"),
        lambda d: d["coach-mock"]["skills"]["coach-mock"].update(delegates=["resume-coach"]),
        lambda d: d["resume-writer"]["skills"]["resume-writer"].update(
            delegates=["interview-reviewer"]
        ),
        lambda d: d["jd-parser"].update(product="elsewhere"),
        lambda d: d["jd-parser"].update(surprise=1),
        lambda d: d["jd-parser"]["skills"]["jd-parser"].update(surprise=1),
        lambda d: d["jd-parser"].update(skills={"other": {}}),
        lambda d: d["jd-parser"]["skills"].update({"resume-coach": {}}),
        lambda d: d["resume-writer"]["skills"].update({"extra": {}}),
        lambda d: d["resume-coach"].pop("skills"),
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


def test_every_skill_hint_the_frontend_sends_is_an_entry_role():
    pages = BACKEND.parent / "frontend" / "web"
    sent = set()
    for path in [*pages.glob("app/**/page.tsx"), *pages.glob("components/**/*.tsx")]:
        sent |= set(re.findall(r'skillHint="([a-z-]+)"', path.read_text("utf-8")))
    assert sent, "expected the agent pages to pass a skillHint"
    assert sent <= set(entry_roles()), sorted(sent - set(entry_roles()))
