#!/usr/bin/env python3
"""Fast structural guard for the committed Poetry Agent profile (not a runtime test suite).

Reads only profile files plus deploy/{compose.yaml,.env.example,k8s/staging.yaml}. It never reads
deploy/.env, never starts a service and never connects to anything.
PyYAML is used when importable; otherwise the structural checks that need parsed YAML are skipped
with a notice and only the conservative text checks run.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - environment dependent
    yaml = None

ROOT = Path(__file__).resolve().parents[3]  # content-agent/
PROFILE = ROOT / "agent" / "deerflow-profile"
DEPLOY = ROOT / "deploy"

CONFIG_VERSION = 63
SKILLS = (
    "authoring-orchestrator",
    "poem-gap-analysis",
    "annotation-design",
    "scene-script-draft",
    "compile-triage",
    "content-review",
)
TASK_SKILLS = {
    "GAP_ANALYSIS": "poem-gap-analysis",
    "ANNOTATION_DRAFT": "annotation-design",
    "SCRIPT_DRAFT": "scene-script-draft",
    "COMPILE_TRIAGE": "compile-triage",
    "CONTENT_REVIEW": "content-review",
}
ROLES = ("poetry_editor_lead", "gap_analyst", "annotation_editor", "scene_dramaturg", "compiler_triage",
         "content_reviewer")
ROLE_PROMPTS = (
    "poetry_editor_lead",
    "gap_analyst",
    "annotation_editor",
    "scene_dramaturg",
    "compiler_triage",
    "content_reviewer",
)
# Profile fingerprint inputs (A-contract section 14; the BFF's profile.py is the final authority).
REQUIRED_FILES = (
    "config/config.yaml",
    "config/extensions_config.json",
    "config/mcp-policy.yaml",
    "config/budgets.yaml",
    "config/roles.yaml",
    "config/poetry-policy.yaml",
    "prompts/core-soul.md",
    "agents/poetry-editor-lead/config.yaml",
    "agents/poetry-editor-lead/SOUL.md",
    "extensions/poetry_agent_extension/contracts.py",
    *(f"prompts/roles/{name}.md" for name in ROLE_PROMPTS),
    *(f"skills/{name}/SKILL.md" for name in SKILLS),
)
ALLOWED_TOOLS = {
    "read_file",
    "poetry-domain_get_work_snapshot",
    "poetry-domain_get_integrity_gap_report",
}
# Capabilities that must never be reachable by an agent.
FORBIDDEN_NAMES = (
    "publish",
    "retract",
    "verify",
    "delete",
    "apply",
    "sql",
    "update_published",
    "request_compile",
    "create_draft_proposal",
    "bash",
    "shell",
    "write_file",
    "str_replace",
    "web_search",
    "web_fetch",
)
CORE_PROHIBITED = ("publish", "retract", "verify_source", "set_verified", "delete_content", "execute_sql")
VOCAB_AUDIENCE = ("PRIMARY", "JUNIOR", "SENIOR")
SKILL_SECTIONS = ("目标", "输入", "允许工具", "禁止行为", "输出", "事实 / 解释", "质量门", "失败处理", "示例")
GATEWAY_FORBIDDEN_ENV = (
    "POETRY_DOMAIN_CONTROL_TOKEN",
    "POETRY_DOMAIN_REVIEW_TOKEN",
    "POETRY_STUDIO_REVIEWER_TOKEN",
    "POETRY_WORKER_TOKEN",
    "POETRY_AGENT_INTERNAL_TOKEN",
)

errors: list[str] = []
notes: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_yaml(path: Path) -> Any:
    if yaml is None:
        return None
    try:
        return yaml.safe_load(read(path))
    except yaml.YAMLError as exc:
        fail(f"{rel(path)}: invalid YAML: {exc}")
        return None


def is_env_ref(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"\$[A-Za-z_][A-Za-z0-9_]*", value) is not None


# --------------------------------------------------------------------------------------------
# 1. File presence
# --------------------------------------------------------------------------------------------
def check_files() -> None:
    for name in REQUIRED_FILES:
        if not (PROFILE / name).is_file():
            fail(f"missing required profile artifact: agent/deerflow-profile/{name}")


# --------------------------------------------------------------------------------------------
# 2. Secrets: no literal credential anywhere in the profile or deploy files we own
# --------------------------------------------------------------------------------------------
SECRET_KEY = re.compile(r"""^\s*["']?(api[_-]?key|apikey|token|secret|password|authorization)["']?\s*[:=]\s*(.*)$""", re.IGNORECASE)
LITERAL_SECRET_VALUE = re.compile(r"(sk-[A-Za-z0-9]{16,}|Bearer\s+[A-Za-z0-9._~+/=-]{16,}|eyJ[A-Za-z0-9_-]{20,})")


def check_no_literal_secrets() -> None:
    files = [p for p in PROFILE.rglob("*") if p.is_file() and p.suffix in {".yaml", ".yml", ".json", ".md", ".py"}]
    files += [DEPLOY / "compose.yaml", DEPLOY / ".env.example", DEPLOY / "k8s" / "staging.yaml"]
    for path in files:
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        for number, line in enumerate(read(path).splitlines(), 1):
            if LITERAL_SECRET_VALUE.search(line):
                fail(f"{rel(path)}:{number}: looks like a literal credential")
            if path.suffix in {".yaml", ".yml"} and path.name != "staging.yaml":
                match = SECRET_KEY.match(line)
                if not match:
                    continue
                key, value = match.group(1).lower(), match.group(2).split("#", 1)[0].strip().strip("\"'")
                if key in {"api_key", "apikey", "api-key"} and value and not is_env_ref(value):
                    fail(f"{rel(path)}:{number}: api_key must be a $VAR reference, not a value")


def check_env_example() -> None:
    path = DEPLOY / ".env.example"
    if not path.is_file():
        fail("missing deploy/.env.example")
        return
    values: dict[str, str] = {}
    for number, line in enumerate(read(path).splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
        if re.search(r"(KEY|TOKEN|SECRET)$", key.strip()) and value.strip() and not value.strip().startswith("change-me"):
            fail(f".env.example:{number}: {key.strip()} must be empty or a change-me placeholder")
    for key in ("POETRY_LLM_API_BASE", "POETRY_LLM_API_KEY", "POETRY_LLM_MODEL_PRIMARY", "POETRY_LLM_MODEL_FALLBACK"):
        if key not in values:
            fail(f".env.example: missing {key}")
        elif values[key] != "":
            fail(f".env.example: {key} must be an empty placeholder (managed by sync_llm_env.py)")
    for key in ("POETRY_WORKER_TOKEN", "POETRY_STUDIO_REVIEWER_TOKEN", "POETRY_STUDIO_ORIGINS",
                "POETRY_DOMAIN_REVIEW_TOKEN"):
        if key not in values:
            fail(f".env.example: missing {key}")


# --------------------------------------------------------------------------------------------
# 3. DeerFlow config.yaml
# --------------------------------------------------------------------------------------------
def check_config(policy: dict[str, Any] | None, budgets: dict[str, Any] | None) -> dict[str, Any] | None:
    path = PROFILE / "config/config.yaml"
    text = read(path) if path.is_file() else ""
    if not re.search(rf"^config_version:\s*{CONFIG_VERSION}\s*$", text, re.MULTILINE):
        fail(f"config.yaml: config_version must be {CONFIG_VERSION}")
    cfg = load_yaml(path) if path.is_file() else None
    if cfg is None:
        if yaml is None:
            notes.append("PyYAML not available: structural YAML checks skipped")
        return None
    if cfg.get("config_version") != CONFIG_VERSION:
        fail(f"config.yaml: config_version must be {CONFIG_VERSION}")

    models = cfg.get("models") or []
    names = [m.get("name") for m in models if isinstance(m, dict)]
    if names[:2] != ["poetry-primary", "poetry-fallback"]:
        fail("config.yaml: models must start with poetry-primary then poetry-fallback")
    expected = {"poetry-primary": "$POETRY_LLM_MODEL_PRIMARY", "poetry-fallback": "$POETRY_LLM_MODEL_FALLBACK"}
    for model in models:
        if not isinstance(model, dict):
            continue
        for key in ("api_key", "api_base", "model"):
            if not is_env_ref(model.get(key)):
                fail(f"config.yaml: model {model.get('name')}: {key} must be a $VAR reference")
        if model.get("name") in expected and model.get("model") != expected[model["name"]]:
            fail(f"config.yaml: model {model['name']}: model must be {expected[model['name']]}")
        if model.get("api_key") != "$POETRY_LLM_API_KEY":
            fail(f"config.yaml: model {model.get('name')}: api_key must be $POETRY_LLM_API_KEY")
        if model.get("api_base") != "$POETRY_LLM_API_BASE":
            fail(f"config.yaml: model {model.get('name')}: api_base must be $POETRY_LLM_API_BASE")
        # Conservative thinking handling: no thinking payload is sent to the gateway.
        for key in ("when_thinking_enabled", "when_thinking_disabled", "thinking", "reasoning", "extra_body"):
            if key in model:
                fail(f"config.yaml: model {model.get('name')}: {key} must not be set (gateway support unverified)")
        if model.get("supports_thinking") is True:
            fail(f"config.yaml: model {model.get('name')}: supports_thinking must be false")

    # Token budget aligned with budgets.yaml
    budget = cfg.get("token_budget") or {}
    if budget.get("enabled") is not True:
        fail("config.yaml: token_budget.enabled must be true")
    authoring = ((budgets or {}).get("profiles") or {}).get("authoring") or {}
    if authoring and budget.get("max_tokens") != authoring.get("max_tokens"):
        fail("config.yaml: token_budget.max_tokens must equal budgets.yaml authoring.max_tokens")
    if authoring:
        limit = cfg.get("recursion_limit")
        if not isinstance(limit, int) or limit < 2 * int(authoring.get("max_turns", 0)):
            fail("config.yaml: recursion_limit must be at least 2 * budgets max_turns")
        if isinstance(limit, int) and isinstance(cfg.get("max_recursion_limit"), int) and cfg["max_recursion_limit"] < limit:
            fail("config.yaml: max_recursion_limit must be >= recursion_limit")
        breaker = authoring.get("circuit_breaker") or {}
        cb = cfg.get("circuit_breaker") or {}
        if breaker and (
            cb.get("failure_threshold") != breaker.get("failure_threshold")
            or cb.get("recovery_timeout_sec") != breaker.get("open_seconds")
        ):
            fail("config.yaml: circuit_breaker must match budgets.yaml circuit_breaker (open_seconds)")

    # Tools: only read_file
    allowed_builtin = set((policy or {}).get("allowed_builtin_tools") or ["read_file"])
    tool_names = {t.get("name") for t in (cfg.get("tools") or []) if isinstance(t, dict)}
    if not tool_names <= allowed_builtin:
        fail(f"config.yaml: tools must be limited to {sorted(allowed_builtin)}; found {sorted(tool_names - allowed_builtin)}")
    for tool in cfg.get("tools") or []:
        use = str(tool.get("use", ""))
        if any(word in use for word in ("bash", "write_file", "str_replace", "web_", "image_search", "browser")):
            fail(f"config.yaml: tool {tool.get('name')} uses a forbidden implementation: {use}")
    sandbox = cfg.get("sandbox") or {}
    if sandbox.get("allow_host_bash") is not False:
        fail("config.yaml: sandbox.allow_host_bash must be false")

    # Skills path matches the compose mount
    skills = cfg.get("skills") or {}
    if skills.get("path") != "/app/skills":
        fail("config.yaml: skills.path must be /app/skills (compose mounts the profile at /app/skills/public)")

    # Guardrails
    guard = cfg.get("guardrails") or {}
    provider = guard.get("provider") or {}
    if guard.get("enabled") is not True or guard.get("fail_closed") is not True:
        fail("config.yaml: guardrails must be enabled with fail_closed: true")
    if provider.get("use") != "deerflow.guardrails.builtin:AllowlistProvider":
        fail("config.yaml: guardrails.provider.use must be the built-in AllowlistProvider")
    guard_cfg = provider.get("config") or {}
    allowed = guard_cfg.get("allowed_tools")
    if not isinstance(allowed, list) or set(allowed) != ALLOWED_TOOLS:
        fail(f"config.yaml: guardrails allowed_tools must be exactly {sorted(ALLOWED_TOOLS)}")
    denied = set(guard_cfg.get("denied_tools") or [])
    for name in ("publish", "retract", "verify_source", "set_verified", "delete_content", "execute_sql",
                 "poetry-domain_create_draft_proposal", "poetry-domain_apply_approved_draft",
                 "poetry-domain_request_compile"):
        if name not in denied:
            fail(f"config.yaml: guardrails denied_tools must list {name}")

    # Features that must stay off
    for section in ("memory", "title", "suggestions", "input_polish", "summarization", "knowledge_base",
                    "skill_evolution", "agents_api", "scheduler", "mcp_tasks", "subagent_batches"):
        block = cfg.get(section)
        if not isinstance(block, dict) or block.get("enabled") is not False:
            fail(f"config.yaml: {section}.enabled must be false")
    if (cfg.get("tool_search") or {}).get("enabled") is not False:
        fail("config.yaml: tool_search.enabled must be false")
    # DeerFlow-format keys only: the self-invented fields must not come back.
    for key in ("runtime", "agent_profiles", "project_name"):
        if key in cfg:
            fail(f"config.yaml: '{key}' is not a DeerFlow field (move platform policy to poetry-policy.yaml)")
    return cfg


# --------------------------------------------------------------------------------------------
# 4. extensions_config.json
# --------------------------------------------------------------------------------------------
def check_extensions() -> None:
    path = PROFILE / "config/extensions_config.json"
    if not path.is_file():
        return
    raw = read(path)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"extensions_config.json: invalid JSON: {exc}")
        return
    if LITERAL_SECRET_VALUE.search(raw):
        fail("extensions_config.json: contains a literal token")
    servers = data.get("mcpServers", {})
    if set(servers) != {"poetry-domain"}:
        fail("extensions_config.json: must expose exactly one MCP server: poetry-domain")
        return
    server = servers["poetry-domain"]
    headers = server.get("headers", {})
    # DeerFlow only expands a WHOLE-string $VAR (extensions_config.py:566-587): "Bearer $X" is sent literally.
    if headers.get("Authorization") != "$POETRY_DOMAIN_MCP_AUTHORIZATION":
        fail("extensions_config.json: Authorization must be the whole-string $POETRY_DOMAIN_MCP_AUTHORIZATION")
    for key, value in headers.items():
        if isinstance(value, str) and "$" in value and not is_env_ref(value):
            fail(f"extensions_config.json: header {key} mixes text and $VAR; DeerFlow will not expand it")
    if (server.get("capability") or {}).get("id") != "poetry-domain-mcp-v1":
        fail("extensions_config.json: capability.id must be poetry-domain-mcp-v1")
    if server.get("tool_name_prefix") is not True:
        fail("extensions_config.json: tool_name_prefix must be true (policy names are poetry-domain_*)")
    if server.get("type") != "http" or not str(server.get("url", "")).startswith("http://poetry-domain-mcp:8101/"):
        fail("extensions_config.json: poetry-domain must be an http server at poetry-domain-mcp:8101")
    skills = data.get("skills", {})
    if set(skills) != set(SKILLS):
        fail(f"extensions_config.json: skills must be exactly {sorted(SKILLS)}")
    for name, state in skills.items():
        if state.get("enabled") is not True:
            fail(f"extensions_config.json: skill {name} must be enabled")


# --------------------------------------------------------------------------------------------
# 5. mcp-policy.yaml, roles.yaml, budgets.yaml, poetry-policy.yaml
# --------------------------------------------------------------------------------------------
def check_mcp_policy() -> None:
    path = PROFILE / "config/mcp-policy.yaml"
    if not path.is_file():
        return
    policy = load_yaml(path)
    if policy is None:
        return
    principals = policy.get("principals") or {}
    if set(principals) != set(ROLES):
        fail(f"mcp-policy.yaml: principals must be exactly {sorted(ROLES)}")
    for role, spec in principals.items():
        allow = spec.get("allow") or []
        for tool in allow:
            lowered = tool.lower()
            if any(word in lowered for word in FORBIDDEN_NAMES):
                fail(f"mcp-policy.yaml: {role} allows a forbidden capability: {tool}")
            if tool not in ALLOWED_TOOLS:
                fail(f"mcp-policy.yaml: {role} allows an unknown tool: {tool}")
    lead = set((principals.get("poetry_editor_lead") or {}).get("allow") or [])
    if lead != ALLOWED_TOOLS:
        fail(f"mcp-policy.yaml: poetry_editor_lead.allow must be exactly {sorted(ALLOWED_TOOLS)}")

    # 单一语义：只写 allow，不写 deny（旧版的 deny 通配符 DeerFlow 根本不解释，见文件头注释）。
    # 唯一被接受的 deny 是 ""*"" 那种自相矛盾的写法 —— 一并拒绝，免得读者以为它生效。
    for role, spec in principals.items():
        if spec.get("deny"):
            fail(f"mcp-policy.yaml: {role}.deny must be removed — DeerFlow does not interpret it; "
                 f"restrict tools with allow here plus config.yaml guardrails.allowed_tools")

    # 角色 → skill → allowed-tools 的闭环：每个角色绑定的 skill，其 allowed-tools 必须是这个角色
    # 的 allow 的子集。这样"角色能做什么"在三处（roles.yaml / mcp-policy.yaml / SKILL.md）
    # 必须一致，任何一处放宽都会被这里抓到。
    roles = (load_yaml(PROFILE / "config/roles.yaml") or {}).get("roles") or {}
    for role, spec in roles.items():
        skill = spec.get("skill")
        if not skill:
            continue
        allowed_for_role = set((principals.get(role) or {}).get("allow") or [])
        skill_path = PROFILE / "skills" / skill / "SKILL.md"
        if not skill_path.is_file():
            continue
        meta, _ = parse_frontmatter(read(skill_path))
        if not isinstance(meta, dict):
            continue
        declared = set(meta.get("allowed-tools") or [])
        extra = declared - allowed_for_role
        if extra:
            fail(f"skills/{skill}: allowed-tools {sorted(extra)} are not allowed by role {role} "
                 f"(mcp-policy.yaml {role}.allow = {sorted(allowed_for_role)})")


def check_roles() -> None:
    path = PROFILE / "config/roles.yaml"
    if not path.is_file():
        return
    data = load_yaml(path)
    if data is None:
        return
    roles = data.get("roles") or {}
    if set(roles) != set(ROLES):
        fail(f"roles.yaml: roles must be exactly {sorted(ROLES)}")
    for role in ROLE_PROMPTS:
        if role not in roles:
            continue
    for role, spec in roles.items():
        if spec.get("can_delegate"):
            fail(f"roles.yaml: {role}.can_delegate must be empty (max_subagents is 0)")
        skill = spec.get("skill")
        if skill and TASK_SKILLS.get(spec.get("task_type")) != skill:
            fail(f"roles.yaml: {role}: task_type/skill mismatch")


def check_budgets() -> dict[str, Any] | None:
    path = PROFILE / "config/budgets.yaml"
    if not path.is_file():
        return None
    data = load_yaml(path)
    if data is None:
        return None
    if data.get("version") != 2:
        fail("budgets.yaml: version must be 2")
    authoring = (data.get("profiles") or {}).get("authoring") or {}
    for key in ("max_turns", "max_subagents", "max_tool_calls", "max_wall_seconds", "max_output_chars",
                "max_tokens", "require_human_review_before_apply", "retry", "circuit_breaker", "per_task_type"):
        if key not in authoring:
            fail(f"budgets.yaml: authoring.{key} is missing")
    if authoring.get("max_subagents") != 0:
        fail("budgets.yaml: authoring.max_subagents must be 0")
    if authoring.get("require_human_review_before_apply") is not True:
        fail("budgets.yaml: require_human_review_before_apply must be true")
    if set(authoring.get("per_task_type") or {}) != set(TASK_SKILLS):
        fail(f"budgets.yaml: per_task_type must cover {sorted(TASK_SKILLS)}")
    retry = authoring.get("retry") or {}
    if len(retry.get("backoff_seconds") or []) < int(retry.get("max_attempts", 0)):
        fail("budgets.yaml: retry.backoff_seconds must have at least max_attempts entries")
    return data


def check_policy() -> dict[str, Any] | None:
    path = PROFILE / "config/poetry-policy.yaml"
    if not path.is_file():
        return None
    data = load_yaml(path)
    if data is None:
        return None
    runtime = data.get("runtime") or {}
    for key in ("allow_shell_tools", "allow_filesystem_tools", "allow_browser_tools", "allow_web_search",
                "allow_subagents", "allow_memory", "allow_skill_evolution"):
        if runtime.get(key) is not False:
            fail(f"poetry-policy.yaml: runtime.{key} must be false")
    forbidden = set(data.get("forbidden_capabilities") or [])
    for word in ("publish", "retract", "verify", "delete", "apply", "sql", "request_compile", "create_draft_proposal"):
        if word not in forbidden:
            fail(f"poetry-policy.yaml: forbidden_capabilities must include {word}")
    profile = (data.get("agent_profiles") or [{}])[0]
    if set(profile.get("skills") or []) != set(SKILLS):
        fail("poetry-policy.yaml: agent_profiles[0].skills must list the five skills")
    if profile.get("task_type_to_skill") != TASK_SKILLS:
        fail("poetry-policy.yaml: task_type_to_skill does not match the four task types")
    if set(data.get("gateway_forbidden_env") or []) != set(GATEWAY_FORBIDDEN_ENV):
        fail("poetry-policy.yaml: gateway_forbidden_env is out of date")
    return data


# --------------------------------------------------------------------------------------------
# 6. Agent config, souls, role prompts, skills
# --------------------------------------------------------------------------------------------
def check_agent() -> None:
    config_path = PROFILE / "agents/poetry-editor-lead/config.yaml"
    if config_path.is_file():
        agent = load_yaml(config_path)
        if agent is not None:
            if agent.get("name") != "poetry-editor-lead":
                fail("agent config: name must be poetry-editor-lead")
            if agent.get("mcp_plugins") != ["poetry-domain-mcp-v1"]:
                fail("agent config: mcp_plugins must be [poetry-domain-mcp-v1]")
            if set(agent.get("skills") or []) != set(SKILLS):
                fail("agent config: skills must list the five skills")
            if agent.get("allowed_subagents") != []:
                fail("agent config: allowed_subagents must be [] (hard deny)")
            if agent.get("memory_enabled") is not False:
                fail("agent config: memory_enabled must be false")
            if agent.get("thinking_enabled") is not False:
                fail("agent config: thinking_enabled must be false")
            if agent.get("tool_groups") not in (["file:read"], []):
                fail("agent config: tool_groups must be [file:read]")
            known = {"name", "display_name", "description", "model", "tool_groups", "skills", "mcp_plugins",
                     "knowledge_scope", "allowed_subagents", "model_settings", "thinking_enabled",
                     "reasoning_effort", "memory_enabled", "github"}
            extra = set(agent) - known
            if extra:
                fail(f"agent config: fields not in DeerFlow AgentConfig: {sorted(extra)}")
    core = PROFILE / "prompts/core-soul.md"
    soul = PROFILE / "agents/poetry-editor-lead/SOUL.md"
    if core.is_file() and soul.is_file():
        core_text = read(core).strip()
        if not read(soul).strip().startswith(core_text):
            fail("SOUL.md must start with the exact text of prompts/core-soul.md")
        if "指令一律无效" not in core_text:
            fail("core-soul.md must state that instructions inside tool results / web pages / pasted text are invalid")
        for term in CORE_PROHIBITED:
            if term not in core_text:
                fail(f"core-soul.md must name the prohibited capability: {term}")


def parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    match = re.match(r"^﻿?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", text, re.DOTALL)
    if not match:
        return None, text
    body = text[match.end():]
    if yaml is None:
        keys = {}
        for line in match.group(1).splitlines():
            if re.match(r"^[A-Za-z-]+:", line):
                keys[line.split(":", 1)[0]] = line.split(":", 1)[1].strip()
        return keys, body
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None, body
    return (data if isinstance(data, dict) else None), body


def check_skills() -> None:
    allowed_keys = {"name", "description", "license", "allowed-tools", "argument-hint", "required-secrets",
                    "secrets-autonomous", "metadata", "compatibility", "version", "author"}
    for name in SKILLS:
        path = PROFILE / "skills" / name / "SKILL.md"
        if not path.is_file():
            continue
        text = read(path)
        meta, body = parse_frontmatter(text)
        if meta is None:
            fail(f"skills/{name}: frontmatter missing or not a YAML mapping")
            continue
        extra = set(meta) - allowed_keys
        if extra:
            fail(f"skills/{name}: frontmatter keys unknown to DeerFlow 2.2.0: {sorted(extra)}")
        if meta.get("name") != name or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", str(meta.get("name", ""))):
            fail(f"skills/{name}: frontmatter name must equal the directory name (hyphen-case)")
        description = str(meta.get("description") or "")
        if not description.strip():
            fail(f"skills/{name}: description is required (DeerFlow silently skips a skill without it)")
        if "<" in description or ">" in description:
            fail(f"skills/{name}: description must not contain angle brackets")
        if len(description) > 1024:
            fail(f"skills/{name}: description longer than 1024 characters")
        tools = meta.get("allowed-tools")
        if yaml is not None:
            if not isinstance(tools, list):
                fail(f"skills/{name}: allowed-tools must be a list")
            else:
                for tool in tools:
                    if tool not in ALLOWED_TOOLS or any(w in tool.lower() for w in FORBIDDEN_NAMES):
                        fail(f"skills/{name}: allowed-tools contains a non-whitelisted tool: {tool}")
        for section in SKILL_SECTIONS:
            if section not in body:
                fail(f"skills/{name}: missing section containing '{section}'")
        if "agent-output.schema.json" not in body or "A-contract" not in body:
            fail(f"skills/{name}: must reference contracts/agent-output.schema.json and A-contract")
        has_examples = body.count("**正例") >= 1 and body.count("**反例") >= 1
        uses_snapshot = "chun-wang" in body or name == "authoring-orchestrator"
        if not (has_examples and uses_snapshot):
            fail(f"skills/{name}: needs positive and negative examples using the Chun Wang snapshot")
        for needed in ("locator",):
            if needed not in body:
                fail(f"skills/{name}: must state the no-fabricated-locator rule")
        # A skill may mention create_draft_proposal only to forbid it.
        for number, line in enumerate(body.splitlines(), 1):
            if "create_draft_proposal" in line and not re.search(r"不|禁止|拒绝|never|not", line):
                fail(f"skills/{name}:{number}: create_draft_proposal appears without a prohibition")
    orchestrator = PROFILE / "skills/authoring-orchestrator/SKILL.md"
    if orchestrator.is_file():
        body = read(orchestrator)
        for needed in ("run_id", "mandate_id", "actor_role", "idempotency_key", "```json", "唯一"):
            if needed not in body:
                fail(f"skills/authoring-orchestrator: must mention {needed}")
        for task_type, skill in TASK_SKILLS.items():
            if task_type not in body or skill not in body:
                fail(f"skills/authoring-orchestrator: task_type routing for {task_type} is missing")


def check_prompts() -> None:
    for role in ROLE_PROMPTS:
        path = PROFILE / "prompts/roles" / f"{role}.md"
        if path.is_file() and not read(path).strip():
            fail(f"prompts/roles/{role}.md is empty")


def check_contracts_py() -> None:
    path = PROFILE / "extensions/poetry_agent_extension/contracts.py"
    if not path.is_file():
        return
    text = read(path)
    if re.search(r"^\s*(from|import)\s+deerflow", text, re.MULTILINE):
        fail("contracts.py must not import the DeerFlow SDK")
    for needle in ('"PRIMARY", "JUNIOR", "SENIOR"', '"LIKELY", "DISPUTED", "UNKNOWN"', "agent-output/1"):
        if needle not in text:
            fail(f"contracts.py: expected vocabulary missing: {needle}")
    if re.search(r'"(MIDDLE|GENERAL|HIGH|MEDIUM|LOW)"\s*[,)]', text.split("SEVERITIES")[0]):
        fail("contracts.py: old audience/certainty vocabulary found")


# --------------------------------------------------------------------------------------------
# 7. Deploy: compose token split and networks, k8s secret split
# --------------------------------------------------------------------------------------------
def check_compose() -> None:
    path = DEPLOY / "compose.yaml"
    if not path.is_file():
        fail("missing deploy/compose.yaml")
        return
    compose = load_yaml(path)
    if compose is None:
        return
    services = compose.get("services") or {}
    for name in ("agent-bff", "agent-worker", "poetry-domain-mcp", "deerflow-gateway", "redis"):
        if name not in services:
            fail(f"compose.yaml: service {name} is missing")
    networks = compose.get("networks") or {}
    if (networks.get("poetry-agent-internal") or {}).get("internal") is not True:
        fail("compose.yaml: poetry-agent-internal must stay internal: true")
    if "poetry-agent-egress" not in networks or (networks.get("poetry-agent-egress") or {}).get("internal"):
        fail("compose.yaml: poetry-agent-egress must exist and must not be internal")

    def env_of(service: str) -> dict[str, Any]:
        env = (services.get(service) or {}).get("environment") or {}
        return env if isinstance(env, dict) else {item.split("=", 1)[0]: item.split("=", 1)[-1] for item in env}

    def nets_of(service: str) -> list[str]:
        nets = (services.get(service) or {}).get("networks") or []
        return list(nets)

    gateway_env = env_of("deerflow-gateway")
    for key in GATEWAY_FORBIDDEN_ENV:
        if key in gateway_env:
            fail(f"compose.yaml: deerflow-gateway must not receive {key}")
    for key in ("POETRY_LLM_API_BASE", "POETRY_LLM_API_KEY", "POETRY_LLM_MODEL_PRIMARY", "POETRY_LLM_MODEL_FALLBACK"):
        value = str(gateway_env.get(key, ""))
        if not re.fullmatch(rf"\$\{{{key}(:-)?\}}", value):
            fail(f"compose.yaml: gateway {key} must be a ${{{key}}} reference")
    for service in ("agent-bff", "agent-worker", "poetry-domain-mcp"):
        if any(k.startswith("POETRY_LLM") for k in env_of(service)):
            fail(f"compose.yaml: {service} must not receive POETRY_LLM_*")
    bff, worker, mcp = env_of("agent-bff"), env_of("agent-worker"), env_of("poetry-domain-mcp")
    if any(k.startswith("DEERFLOW_") and k != "DEERFLOW_ENABLED" for k in bff):
        fail("compose.yaml: agent-bff may only keep DEERFLOW_ENABLED")
    for key in ("POETRY_WORKER_URL", "POETRY_WORKER_TOKEN", "POETRY_API_BASE_URL", "POETRY_STUDIO_REVIEWER_TOKEN",
                "POETRY_STUDIO_ORIGINS", "POETRY_DOMAIN_CONTROL_TOKEN", "POETRY_DOMAIN_CONTROL_URL",
                "POETRY_DOMAIN_REVIEW_TOKEN"):
        if key not in bff:
            fail(f"compose.yaml: agent-bff is missing {key}")
    for service, env in (("agent-worker", worker), ("poetry-domain-mcp", mcp)):
        if "POETRY_STUDIO_REVIEWER_TOKEN" in env:
            fail(f"compose.yaml: {service} must not receive POETRY_STUDIO_REVIEWER_TOKEN")
    if "POETRY_WORKER_TOKEN" in mcp:
        fail("compose.yaml: poetry-domain-mcp must not receive POETRY_WORKER_TOKEN")
    # A-05 的机械保证：worker 能创建提案，但不能评审或应用它自己产出的提案。
    # 评审/应用需要独立的 review 令牌，worker 一旦拿到它，这条边界就消失了——所以这里必须失败。
    if "POETRY_DOMAIN_REVIEW_TOKEN" in worker:
        fail("compose.yaml: agent-worker must not receive POETRY_DOMAIN_REVIEW_TOKEN "
             "(it would be able to approve its own proposals, A-05)")
    if "POETRY_DOMAIN_REVIEW_TOKEN" not in mcp:
        fail("compose.yaml: poetry-domain-mcp is missing POETRY_DOMAIN_REVIEW_TOKEN")
    for key in ("POETRY_DOMAIN_CONTROL_TOKEN", "POETRY_WORKER_TOKEN", "DEERFLOW_GATEWAY_URL"):
        if key not in worker:
            fail(f"compose.yaml: agent-worker is missing {key}")
    if "POETRY_AGENT_INTERNAL_TOKEN" in bff or "POETRY_AGENT_INTERNAL_TOKEN" in worker:
        fail("compose.yaml: only poetry-domain-mcp may hold POETRY_AGENT_INTERNAL_TOKEN")
    # Egress only where needed.
    for service in ("agent-bff", "poetry-domain-mcp", "deerflow-gateway"):
        if "poetry-agent-egress" not in nets_of(service):
            fail(f"compose.yaml: {service} needs poetry-agent-egress")
    for service in ("agent-worker", "redis"):
        if "poetry-agent-egress" in nets_of(service):
            fail(f"compose.yaml: {service} must not be on poetry-agent-egress")
    # Every published port must bind an explicit address.
    for name, service in services.items():
        for port in service.get("ports") or []:
            if isinstance(port, str) and not re.match(r"^\"?\$\{[A-Z_]+:-[0-9.]+\}:|^[0-9.]+:", port):
                fail(f"compose.yaml: {name}: published port without an explicit bind address: {port}")
    # Skills mount matches config.yaml skills.path.
    volumes = [str(v) for v in (services.get("deerflow-gateway") or {}).get("volumes") or []]
    if not any(v.endswith(":/app/skills/public:ro") and "deerflow-profile/skills" in v for v in volumes):
        fail("compose.yaml: gateway must mount deerflow-profile/skills at /app/skills/public (read-only)")
    if any(v.endswith(":/app/skills:ro") for v in volumes):
        fail("compose.yaml: skills mounted at /app/skills is not discovered; mount at /app/skills/public")
    if not any("deerflow-profile/agents" in v and v.endswith("/agents:ro") for v in volumes):
        fail("compose.yaml: gateway must mount deerflow-profile/agents read-only")


def check_k8s() -> None:
    path = DEPLOY / "k8s" / "staging.yaml"
    if not path.is_file():
        fail("missing deploy/k8s/staging.yaml")
        return
    text = read(path)
    if "poetry-agent-worker" not in text:
        fail("k8s/staging.yaml: worker deployment is missing")
    if re.search(r"^\s*value:\s*[\"']?(sk-|Bearer )", text, re.MULTILINE):
        fail("k8s/staging.yaml: literal credential in env value")
    if yaml is None:
        return
    docs = [d for d in yaml.safe_load_all(text) if d]
    for doc in docs:
        if doc.get("kind") == "Secret":
            fail("k8s/staging.yaml: must not contain Secret objects (values are injected by the platform)")
        if doc.get("kind") != "Deployment":
            continue
        name = doc["metadata"]["name"]
        containers = doc["spec"]["template"]["spec"]["containers"]
        for container in containers:
            secrets = [e["secretRef"]["name"] for e in container.get("envFrom", []) if "secretRef" in e]
            if "poetry-agent-runtime" in secrets:
                fail(f"k8s/staging.yaml: {name} still uses the shared poetry-agent-runtime Secret")
            for env in container.get("env", []) or []:
                if "TOKEN" in env.get("name", "") and "value" in env:
                    fail(f"k8s/staging.yaml: {name}: {env['name']} must come from a Secret, not a literal value")
        if name == "poetry-agent-worker" and not any("worker-secrets" in s for c in containers for s in
                                                      [e.get("secretRef", {}).get("name", "") for e in c.get("envFrom", [])]):
            fail("k8s/staging.yaml: the worker must use poetry-agent-worker-secrets")


def main() -> int:
    check_files()
    check_no_literal_secrets()
    check_env_example()
    budgets = check_budgets()
    policy = check_policy()
    check_config(policy, budgets)
    check_extensions()
    check_mcp_policy()
    check_roles()
    check_agent()
    check_skills()
    check_prompts()
    check_contracts_py()
    check_compose()
    check_k8s()
    for note in notes:
        print(f"note: {note}")
    if errors:
        print(f"profile check FAILED ({len(errors)} problem(s)):")
        for message in errors:
            print(f"  - {message}")
        return 1
    # 技能数量不写死：加 skill 时不该再改这句话（这次就是因为写死 "5 skills" 才发现）。
    print(f"profile check passed: DeerFlow 2.2.0 config, {len(SKILLS)} skills, "
          "read-only MCP policy, token split and networks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
