from jc.mcp.registry import OPENAI_TOOLS
from jc.services.harness_inventory_service import build_harness_inventory


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
    import jc.services.harness_inventory_service as inventory

    canonical = tmp_path / "skills" / "public" / "resume-coach"
    canonical.mkdir(parents=True)
    (canonical / "SKILL.md").write_text(
        "---\nname: resume-coach\ndescription: Canonical JC skill\n---\nUse jc_profile_get.\n",
        encoding="utf-8",
    )
    legacy = tmp_path / ".deer-flow" / "skills_view" / "public" / "resume-coach"
    legacy.mkdir(parents=True)
    (legacy / "SKILL.md").write_text(
        "---\nname: resume-coach\ndescription: Legacy JobCome skill\n---\nUse jobcome_profile_get.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(inventory, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(inventory.settings, "jc_skills_dir", "skills/public")

    bodies = inventory._load_skill_bodies()
    assert bodies["resume-coach"] == (canonical / "SKILL.md").read_text(encoding="utf-8")
    assert "jobcome_" not in "\n".join(bodies.values())
