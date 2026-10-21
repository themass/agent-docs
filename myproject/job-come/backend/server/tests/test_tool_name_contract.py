"""Keep JC's configured MCP tool names aligned with its prompts and catalog.

JC tool functions already carry the jc_ prefix; server-side prefixing must not
add it again. This guards a real configuration mismatch, not a claim that name
mismatch was the only reason a particular model run failed to invoke a tool.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from jc.agent.tool_catalog import OPENAI_TOOLS, SKILL_TOOLS

BACKEND = Path(__file__).resolve().parents[2]
AGENT_DIR = BACKEND / "agent" / "deerflow"
SKILLS_DIR = BACKEND / "agent" / "skills" / "public"


def _catalog_names() -> set[str]:
    return {str(t["function"]["name"]) for t in OPENAI_TOOLS}


def test_server_tools_are_not_double_prefixed() -> None:
    """The JC server does not add another prefix to its self-prefixed tools."""
    from jc.mcp import server as mcp_server

    tool_fns = [n for n in dir(mcp_server) if n.startswith("jc_")]
    assert tool_fns, "expected jc_-prefixed tool functions in jc.mcp.server"

    # Scoped to the server that actually hosts these functions. A third-party
    # server in the same file (markitdown) names its own tools and is entitled
    # to whatever prefix policy it likes; asserting against it would be
    # asserting something this contract knows nothing about.
    for config_name in ("extensions_config.json", "extensions_config.example.json"):
        data = json.loads((AGENT_DIR / config_name).read_text(encoding="utf-8"))
        spec = (data.get("mcpServers") or {}).get("jc")
        assert spec is not None, f"{config_name}: no 'jc' MCP server declared"
        assert spec.get("tool_name_prefix") is False, (
            f"{config_name}: the 'jc' server has tool_name_prefix enabled while "
            f"jc.mcp.server already prefixes its tools ({tool_fns[:3]}...). "
            "The model would be offered jc_jc_* and every prompt names jc_*."
        )


def test_catalog_names_match_the_mcp_server_functions() -> None:
    """The catalog the model is shown and the surface that serves it agree."""
    from jc.mcp import server as mcp_server

    served = {n for n in dir(mcp_server) if n.startswith("jc_") and callable(getattr(mcp_server, n))}
    for name in _catalog_names():
        assert name in served, f"catalog advertises {name!r} with no function in jc.mcp.server"


def test_every_tool_named_in_a_prompt_exists_in_the_catalog() -> None:
    """A prompt may only name a tool the model is actually given.

    This is the direct inverse of the bug: the prompts were right and the bound
    name was wrong, so asserting the prompts against the catalog catches the
    disagreement from either direction.
    """
    catalog = _catalog_names()
    sources = list(SKILLS_DIR.rglob("SKILL.md")) + [AGENT_DIR / "product_rules.md"]
    assert sources, "no prompt sources found"

    referenced: dict[str, list[str]] = {}
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for name in re.findall(r"\bjc_[a-z_]+\b", text):
            referenced.setdefault(name, []).append(path.name)

    assert referenced, "no jc_* tool references found in any prompt"
    unknown = {n: where for n, where in referenced.items() if n not in catalog}
    assert not unknown, (
        f"prompts name tools that are not in the catalog: {unknown}. "
        "A model cannot call a name it was not given."
    )


def test_per_tool_output_overrides_use_bound_tool_names() -> None:
    """`tool_output.tool_overrides` is keyed on the name the harness sees.

    The `jc_profile_patch` override exists to stop that tool's JSON result from
    being externalized into a text synopsis, which would break the confirm-card
    parse in `_maybe_emit_confirm`. Keyed on a name no tool has, the override is
    inert and the guard it provides is gone — silently.
    """
    text = (AGENT_DIR / "config.yaml").read_text(encoding="utf-8")
    block = re.search(r"^tool_output:\n(?:[ \t].*\n|\n)*", text, re.M)
    assert block, "config.yaml has no tool_output block"
    catalog = _catalog_names()
    for key in re.findall(r"^\s{4}([A-Za-z0-9_]+):", block.group(0), re.M):
        assert key in catalog, (
            f"tool_output.tool_overrides names {key!r}, which is not a bound tool "
            f"name. Known: {sorted(catalog)}"
        )


def test_skill_tool_scopes_reference_real_catalog_entries() -> None:
    catalog = _catalog_names()
    for skill, names in SKILL_TOOLS.items():
        for name in names:
            assert name in catalog, f"skill {skill!r} allows unknown tool {name!r}"
