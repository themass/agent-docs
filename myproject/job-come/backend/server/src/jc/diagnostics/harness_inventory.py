"""Read-only harness inventory: what the agent is actually carrying right now.

This deliberately sits outside `jc.services`. It is a diagnostic that reports on the
agent runtime, so it reads across the tool adapter, the tool catalog, the role scope
and the skill packages at once — breadth that is correct for an operator report and
wrong for a business service. Keeping it here means `jc.services` never has to import
the tool surface, and it keeps the direction honest: diagnostics depend on everything,
and nothing depends on diagnostics.

Everything it reports is derived from the same sources the runtime uses. An inventory
that maintains its own idea of what exists is an inventory that eventually lies.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from jc.agent.roles import SKILL_PROMPT_PREFIX, hints_by_skill
from jc.agent.tool_catalog import OPENAI_TOOLS, SKILL_TOOLS, tool_names
from jc.config import settings
from jc.mcp.handlers import TOOL_HANDLERS
from jc.paths import agent_file, resolve_under_server
from jc.schemas.admin_session import (
    AdminInventoryResponse,
    AdminMcpResourceInfo,
    AdminMcpServerInfo,
    AdminSkillInfo,
    AdminToolInfo,
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _mcp_registered_tools() -> set[str]:
    return set(TOOL_HANDLERS.keys())


def _load_skill_bodies() -> dict[str, str]:
    bodies: dict[str, str] = {}
    # Read canonical skill sources only.  DeerFlow's skills_view is a generated
    # sandbox projection and may be stale; it is never an inventory source.
    candidates = [
        resolve_under_server(settings.jc_skills_dir),
        agent_file("skills", "public"),
    ]
    seen: set[str] = set()
    for skills_root in candidates:
        if not skills_root.exists():
            continue
        for path in skills_root.glob("*/SKILL.md"):
            skill_id = path.parent.name
            if skill_id in seen:
                continue
            seen.add(skill_id)
            bodies[skill_id] = path.read_text(encoding="utf-8")
    return bodies


def _role_prompt(spec: dict[str, Any]) -> str:
    """What a declared role's prompt actually resolves to.

    `config.yaml` stores a pointer (`skill:resume-writer`) rather than prose, so that the
    role is defined once. The inventory is where an operator checks what the agent is
    carrying, and showing them the pointer answers a different question than the one they
    asked — so it is resolved here, the same way the runtime resolves it.

    Falls back to the raw value on a bad pointer rather than raising: the runtime already
    fails loudly on that, and an inventory that cannot render is worse for diagnosing it.
    """
    declared = str(spec.get("system_prompt") or "")
    if not declared.strip().startswith(SKILL_PROMPT_PREFIX):
        return declared
    skill_id = declared.strip()[len(SKILL_PROMPT_PREFIX) :].strip()
    try:
        from jc.skills.composer import compose_role_baseline

        return compose_role_baseline(skill_id)
    except LookupError:
        return declared


def build_harness_inventory() -> AdminInventoryResponse:
    ext_path = resolve_under_server(settings.jc_deerflow_extensions_config)
    cfg_path = resolve_under_server(settings.jc_deerflow_config_path)
    rules_path = agent_file("deerflow", "product_rules.md")

    ext = _read_json(ext_path)
    cfg = _read_yaml(cfg_path)
    mcp_registered = _mcp_registered_tools()
    catalog_names = tool_names()
    scope_reverse = hints_by_skill()
    skill_bodies = _load_skill_bodies()
    skills_cfg = ext.get("skills") or {}

    mcp_servers: list[AdminMcpServerInfo] = []
    for name, raw in (ext.get("mcpServers") or {}).items():
        if not isinstance(raw, dict):
            continue
        raw_resources = raw.get("resources") or []
        resources = []
        if isinstance(raw_resources, list):
            for item in raw_resources:
                if not isinstance(item, dict):
                    continue
                uri = str(item.get("uri") or item.get("name") or "")
                if not uri:
                    continue
                resources.append(
                    AdminMcpResourceInfo(
                        uri=uri,
                        name=str(item.get("name") or uri),
                        description=item.get("description"),
                        mime_type=item.get("mimeType") or item.get("mime_type"),
                    )
                )
        server_tools = list(raw.get("tools") or [])
        if not server_tools and name.lower() == "jc":
            server_tools = [n for n in catalog_names if n in mcp_registered or n.startswith("jc_")]
        mcp_servers.append(
            AdminMcpServerInfo(
                name=name,
                enabled=bool(raw.get("enabled", True)),
                type=raw.get("type"),
                description=raw.get("description"),
                command=raw.get("command"),
                args=list(raw.get("args") or []),
                tools=server_tools,
                resources=resources,
            )
        )

    if not mcp_servers:
        mcp_servers.append(
            AdminMcpServerInfo(
                name="jc",
                enabled=True,
                type="stdio",
                description="JC business tools: profile, interview bank, JD fit",
                command="python -m jc.mcp.server",
                args=[],
                tools=[n for n in catalog_names if n in mcp_registered or n.startswith("jc_")],
                resources=[],
            )
        )

    tool_skills: dict[str, list[str]] = {}
    for skill_id, skill_tool_names in SKILL_TOOLS.items():
        for tool_name in skill_tool_names:
            tool_skills.setdefault(tool_name, []).append(skill_id)

    tools: list[AdminToolInfo] = []
    for entry in OPENAI_TOOLS:
        fn = entry.get("function") or {}
        name = str(fn.get("name") or "")
        if not name:
            continue
        tools.append(
            AdminToolInfo(
                name=name,
                description=fn.get("description"),
                parameters=fn.get("parameters") or {},
                registered_on_mcp_server=name in mcp_registered,
                skills=tool_skills.get(name, []),
            )
        )

    skills: list[AdminSkillInfo] = []
    all_skill_ids = sorted(
        set(skills_cfg.keys()) | set(SKILL_TOOLS.keys()) | set(skill_bodies.keys())
    )
    for skill_id in all_skill_ids:
        cfg_row = skills_cfg.get(skill_id) if isinstance(skills_cfg.get(skill_id), dict) else {}
        # `enabled` means "this skill can be selected for a turn", not "the model can
        # read its SKILL.md". No skill body is model-readable in JC: the host composes
        # the text (see jc.skills.composer) and the agent has no file tools. A skill is
        # therefore considered enabled when the harness config says so, and otherwise
        # when it owns a tool surface in SKILL_TOOLS. A skill that has a SKILL.md but
        # neither of those is methodology the host does not currently route to anything.
        enabled = (
            bool(cfg_row.get("enabled", True))
            if skill_id in skills_cfg
            else skill_id in SKILL_TOOLS
        )
        body = skill_bodies.get(skill_id, "")
        desc = None
        if body:
            for line in body.splitlines():
                if line.startswith("description:"):
                    desc = line.split(":", 1)[1].strip()
                    break
        skills.append(
            AdminSkillInfo(
                id=skill_id,
                enabled=enabled,
                description=desc,
                body_preview=body[:1200] if body else None,
                tools=SKILL_TOOLS.get(skill_id, []),
                scope_for_hints=scope_reverse.get(skill_id, []),
            )
        )

    models = cfg.get("models") or []
    subagents = []
    custom = (cfg.get("subagents") or {}).get("custom_agents") or {}
    for name, spec in custom.items():
        if isinstance(spec, dict):
            subagents.append({"name": name, **spec, "system_prompt": _role_prompt(spec)})

    rules_preview = rules_path.read_text(encoding="utf-8")[:2000] if rules_path.exists() else None

    return AdminInventoryResponse(
        mcp_servers=mcp_servers,
        middlewares=list(ext.get("middlewares") or []),
        mcp_interceptors=list(ext.get("mcpInterceptors") or []),
        tools=tools,
        skills=skills,
        models=models if isinstance(models, list) else [],
        subagents=subagents,
        product_rules_preview=rules_preview,
    )
