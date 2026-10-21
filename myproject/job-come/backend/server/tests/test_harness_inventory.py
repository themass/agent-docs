from jc.agent.roles import SKILL_SCOPE
from jc.agent.tool_catalog import OPENAI_TOOLS, SKILL_TOOLS
from jc.diagnostics.harness_inventory import build_harness_inventory


def test_inventory_exposes_tool_descriptions_and_mcp_lists() -> None:
    inv = build_harness_inventory()
    assert inv.tools
    described = [t for t in inv.tools if t.description]
    assert described, "tools should carry OpenAI schema descriptions"
    names = {t.name for t in inv.tools}
    registry_names = {str((e.get("function") or {}).get("name")) for e in OPENAI_TOOLS}
    assert names == registry_names
    assert inv.mcp_servers
    jc = next((s for s in inv.mcp_servers if s.name.lower() == "jc"), inv.mcp_servers[0])
    assert isinstance(jc.tools, list)
    assert isinstance(jc.resources, list)
    if jc.tools:
        assert set(jc.tools).issubset(names)


def test_inventory_does_not_use_legacy_deerflow_projection(monkeypatch, tmp_path) -> None:
    """A stale generated projection cannot resurrect pre-JC tools or copy."""
    import jc.diagnostics.harness_inventory as inventory
    from jc import paths

    canonical = tmp_path / "skills" / "public" / "resume-coach"
    canonical.mkdir(parents=True)
    (canonical / "SKILL.md").write_text(
        "---\nname: resume-coach\ndescription: Canonical JC skill\n---\nUse jc_profile_get.\n",
        encoding="utf-8",
    )
    legacy = tmp_path / ".deer-flow" / "skills_view" / "public" / "resume-coach"
    legacy.mkdir(parents=True)
    (legacy / "SKILL.md").write_text(
        "---\nname: resume-coach\ndescription: Legacy JobCome skill\n---\n"
        "Use jobcome_profile_get.\n",
        encoding="utf-8",
    )

    # Layout now has one owner (`jc.paths`), so redirect the roots there rather than
    # a per-module copy. `resolve_under_server` and `agent_file` read these globals at
    # call time, which is what makes them patchable at all.
    monkeypatch.setattr(paths, "SERVER_ROOT", tmp_path)
    monkeypatch.setattr(paths, "AGENT_ROOT", tmp_path)
    monkeypatch.setattr(inventory.settings, "jc_skills_dir", "skills/public")

    bodies = inventory._load_skill_bodies()
    assert bodies["resume-coach"] == (canonical / "SKILL.md").read_text(encoding="utf-8")
    assert "jobcome_" not in "\n".join(bodies.values())


def test_every_skill_with_a_body_is_reported_as_enabled() -> None:
    """A skill shipped on disk must not show up in admin as a dead package.

    `profile-interview` was the case that exposed this: it is real methodology the
    host injects on an interview turn, but it owned no row in the harness config and
    no tool surface, so the inventory rendered it `enabled=False, tools=[]` — which
    reads as "this skill never runs". The inventory is the only place an operator can
    check what the agent is carrying, so it may not understate what is wired up.
    """
    inv = build_harness_inventory()
    by_id = {s.id: s for s in inv.skills}
    interview = by_id["profile-interview"]
    assert interview.enabled
    assert interview.tools == [
        "jc_profile_photo_set",
        "jc_profile_get",
        "jc_profile_patch",
        "jc_intake_plan",
        "jc_intake_record",
    ]
    assert interview.description
    for skill in inv.skills:
        if skill.body_preview:
            assert skill.enabled, f"{skill.id} ships a SKILL.md but reports as disabled"


def test_interview_tool_surface_never_reaches_the_export_gate() -> None:
    """An interview turn asks and records. It must not reach the export gate.

    The interview surface is deliberately *wider* than the coach's by exactly the two
    intake tools: it is the only turn that transcribes a user's spoken answer into a
    named plan slot. What it must never gain is `jc_resume_review`, which is the gate
    an export passes through — a turn whose job is to collect material has no business
    marking a draft reviewed.

    Stated as a containment rule rather than set equality so adding a tool to the coach
    does not silently add it to the interview, and vice versa.
    """
    interview = set(SKILL_TOOLS["profile-interview"])
    coach = set(SKILL_TOOLS["resume-coach"])
    assert coach <= interview
    assert interview - coach == {"jc_intake_record"}
    assert "jc_resume_review" not in interview
    assert SKILL_SCOPE["profile-interview"] == frozenset({"profile-interview"})


def test_only_the_interview_may_write_interview_answers() -> None:
    """`jc_intake_record` bypasses the confirm card, so its reach must stay minimal.

    Every other write path to a profile goes through `jc_profile_patch`, which the user
    approves in the UI. The interview is the one exception, justified by the plan
    bounding which paths it can touch. That exception has to stay attached to the turn
    that earned it — if the coach, the writer or the apply pipeline picked it up, a
    model could write unconfirmed prose into a profile the user already reviewed.
    """
    holders = {
        skill for skill, tools in SKILL_TOOLS.items() if "jc_intake_record" in tools
    }
    assert holders == {"profile-interview"}


def test_inventory_resolves_a_role_pointer_into_the_real_prompt() -> None:
    """An operator checking what the writer is told must not be shown `skill:resume-writer`.

    The pointer exists so the role is defined once, in its skill package. That is the
    right storage form and the wrong display form: the inventory is the one place to
    answer "what is this agent actually carrying".
    """
    from jc.skills.composer import compose_role_baseline

    inv = build_harness_inventory()
    writer = next(s for s in inv.subagents if s["name"] == "resume-writer")
    assert not str(writer["system_prompt"]).startswith("skill:")
    assert writer["system_prompt"] == compose_role_baseline("resume-writer")
