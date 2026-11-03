"""The tool catalog: what the agent's tools are, as the model sees them.

There is one definition of a tool: its wrapper in `jc.mcp.server`, whose signature is the schema
the model receives. This module derives the catalog from that server, minus the identity arguments
(`jc_user_id` and friends), which the identity interceptor fills in and the model never supplies.

Which role may use which tool is not decided here. That is the `allowed-tools` of each skill
(`jc.skills.loader`). A test checks that every tool a skill names exists in this catalog.
"""

from __future__ import annotations

from typing import Any

_IDENTITY_PREFIX = "jc_"
_IDENTITY_ARGS = frozenset({
    "jc_user_id", "jc_profile_id", "jc_session_id", "jc_job_id", "jc_mock_session_id",
})


def catalog() -> list[dict[str, Any]]:
    """Every tool the MCP server exposes, in the OpenAI function shape, minus identity arguments."""
    from jc.mcp.server import mcp

    out: list[dict[str, Any]] = []
    for tool in mcp._tool_manager.list_tools():
        schema = dict(tool.parameters or {})
        properties = {
            name: spec for name, spec in (schema.get("properties") or {}).items()
            if name not in _IDENTITY_ARGS
        }
        required = [name for name in schema.get("required") or [] if name in properties]
        out.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {**schema, "properties": properties, "required": required},
            },
        })
    return out


def tool_names() -> list[str]:
    """Every tool name in the catalog, in declaration order."""
    return [str(entry["function"]["name"]) for entry in catalog()]
