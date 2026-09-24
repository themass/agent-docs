"""Read-only DeerFlow harness inventory (MCP, tools, skills)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from jobcome.adapters.deerflow_harness_client import _SKILL_SCOPE
from jobcome.config import settings
from jobcome.mcp.registry import OPENAI_TOOLS, SKILL_TOOLS
from jobcome.mcp.handlers import TOOL_HANDLERS
from jobcome.schemas.admin_session import (
    AdminInventoryResponse,
    AdminMcpResourceInfo,
    AdminMcpServerInfo,
    AdminSkillInfo,
    AdminToolInfo,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


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


def _skill_scope_reverse() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for hint, skills in _SKILL_SCOPE.items():
        for skill in skills:
            out.setdefault(skill, []).append(hint)
    return out


def _load_skill_bodies() -> dict[str, str]:
    bodies: dict[str, str] = {}
    candidates = [
        _PROJECT_ROOT / settings.job_come_skills_dir,
        _PROJECT_ROOT / "skills" / "public",
        _PROJECT_ROOT / ".deer-flow" / "skills_view" / "public",
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


def build_harness_inventory() -> AdminInventoryResponse:
    ext_path = _PROJECT_ROOT / settings.job_come_deerflow_extensions_config
    cfg_path = _PROJECT_ROOT / settings.job_come_deerflow_config_path
    rules_path = _PROJECT_ROOT / "deploy" / "deerflow" / "product_rules.md"

    ext = _read_json(ext_path)
    cfg = _read_yaml(cfg_path)
    mcp_registered = _mcp_registered_tools()
    tool_names = [
        str((entry.get("function") or {}).get("name") or "")
        for entry in OPENAI_TOOLS
        if (entry.get("function") or {}).get("name")
    ]
    scope_reverse = _skill_scope_reverse()
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
        if not server_tools and name.lower() in {"jobcome", "job-come"}:
            server_tools = [n for n in tool_names if n in mcp_registered or n.startswith("jobcome_")]
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
                name="jobcome",
                enabled=True,
                type="stdio",
                description="JobCome business tools: profile, interview bank, JD fit",
                command="python -m jobcome.mcp.server",
                args=[],
                tools=[n for n in tool_names if n in mcp_registered or n.startswith("jobcome_")],
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
    all_skill_ids = sorted(set(skills_cfg.keys()) | set(SKILL_TOOLS.keys()) | set(skill_bodies.keys()))
    for skill_id in all_skill_ids:
        cfg_row = skills_cfg.get(skill_id) if isinstance(skills_cfg.get(skill_id), dict) else {}
        enabled = bool(cfg_row.get("enabled", True)) if skill_id in skills_cfg else skill_id in SKILL_TOOLS
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
            subagents.append({"name": name, **spec})

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
