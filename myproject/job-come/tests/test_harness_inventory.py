from jobcome.mcp.registry import OPENAI_TOOLS
from jobcome.services.harness_inventory_service import build_harness_inventory


def test_inventory_exposes_tool_descriptions_and_mcp_lists() -> None:
    inv = build_harness_inventory()
    assert inv.tools
    described = [t for t in inv.tools if t.description]
    assert described, "tools should carry OpenAI schema descriptions"
    names = {t.name for t in inv.tools}
    registry_names = {str((e.get("function") or {}).get("name")) for e in OPENAI_TOOLS}
    assert names == registry_names
    assert inv.mcp_servers
    jobcome = next((s for s in inv.mcp_servers if s.name.lower() in {"jobcome", "job-come"}), inv.mcp_servers[0])
    assert isinstance(jobcome.tools, list)
    assert isinstance(jobcome.resources, list)
    if jobcome.tools:
        assert set(jobcome.tools).issubset(names)
