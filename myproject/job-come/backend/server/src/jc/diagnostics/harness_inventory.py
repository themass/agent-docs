"""Read-only harness inventory: what the agent is actually carrying right now.

This sits outside `jc.services` on purpose: it reports on the agent runtime, so it reads across
the role declarations, the skill packages, the tool catalog and the DeerFlow configuration at once.
Diagnostics depend on everything and nothing depends on diagnostics.

Everything it reports is derived from the sources the runtime itself uses. An inventory that keeps
its own idea of what exists is an inventory that eventually lies.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from jc.agent.roles import roles
from jc.agent.tool_catalog import catalog
from jc.config import settings
from jc.paths import agent_file, resolve_under_server
from jc.schemas.admin_session import (
    AdminInventoryResponse,
    AdminMcpResourceInfo,
    AdminMcpServerInfo,
    AdminRoleInfo,
    AdminSkillInfo,
    AdminToolInfo,
)
from jc.skills.loader import all_skill_ids, require_skill


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _mcp_servers(ext: dict[str, Any], tool_names: list[str]) -> list[AdminMcpServerInfo]:
    servers: list[AdminMcpServerInfo] = []
    for name, raw in (ext.get("mcpServers") or {}).items():
        if not isinstance(raw, dict):
            continue
        resources = []
        for item in raw.get("resources") or []:
            if isinstance(item, dict) and (item.get("uri") or item.get("name")):
                resources.append(
                    AdminMcpResourceInfo(
                        uri=str(item.get("uri") or item.get("name")),
                        name=str(item.get("name") or item.get("uri")),
                        description=item.get("description"),
                        mime_type=item.get("mimeType") or item.get("mime_type"),
                    )
                )
        declared_tools = list(raw.get("tools") or [])
        if not declared_tools and name.lower() == "jc":
            declared_tools = tool_names
        servers.append(
            AdminMcpServerInfo(
                name=name,
                enabled=bool(raw.get("enabled", True)),
                type=raw.get("type"),
                description=raw.get("description"),
                command=raw.get("command"),
                args=list(raw.get("args") or []),
                tools=declared_tools,
                resources=resources,
            )
        )
    return servers


def build_harness_inventory() -> AdminInventoryResponse:
    ext = _read_json(resolve_under_server(settings.jc_deerflow_extensions_config))
    cfg = _read_yaml(resolve_under_server(settings.jc_deerflow_config_path))
    rules_path = agent_file("deerflow", "product_rules.md")

    owners: dict[str, list[str]] = {}
    for declared in roles().values():
        for skill_id in declared.skill_ids:
            for tool_name in require_skill(skill_id).allowed_tools:
                owners.setdefault(tool_name, []).append(skill_id)

    tools = []
    for entry in catalog():
        fn = entry.get("function") or {}
        name = str(fn.get("name") or "")
        if name:
            tools.append(
                AdminToolInfo(
                    name=name,
                    description=fn.get("description"),
                    parameters=fn.get("parameters") or {},
                    registered_on_mcp_server=True,
                    skills=owners.get(name, []),
                )
            )

    owner_of = {s: r.id for r in roles().values() for s in r.skill_ids}
    skills = []
    for skill_id in all_skill_ids():
        package = require_skill(skill_id)
        skills.append(
            AdminSkillInfo(
                id=skill_id,
                description=package.description,
                body_preview=package.body[:1200] or None,
                tools=list(package.allowed_tools),
                always_loaded=list(package.always_loaded),
                borrow_family_from=package.borrow_family_from,
                role=owner_of[skill_id],
            )
        )

    role_rows = [
        AdminRoleInfo(
            id=r.id,
            product=r.product,
            mode=r.mode,
            scenario=r.scenario,
            model=r.model_name,
            entry=r.entry,
            default=r.default,
            plan_mode=r.plan_mode,
            skills=list(r.skill_ids),
            turn=r.turn,
            switch=[{"to": rule.to, "when": rule.when} for rule in r.switch],
        )
        for r in roles().values()
    ]

    models = cfg.get("models")
    rules_preview = rules_path.read_text(encoding="utf-8")[:2000] if rules_path.exists() else None
    return AdminInventoryResponse(
        mcp_servers=_mcp_servers(ext, [str(t['function']['name']) for t in catalog()]),
        middlewares=list(ext.get("middlewares") or []),
        tools=tools,
        skills=skills,
        roles=role_rows,
        models=models if isinstance(models, list) else [],
        product_rules_preview=rules_preview,
    )
