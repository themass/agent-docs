"""The layer contract, enforced instead of documented.

Every rule here was a real defect, not a style preference. `jc.services` and `jc.mcp`
imported each other and only survived because some of those imports were hidden
inside functions, where Python resolves them late enough to miss the cycle at
startup. A review cannot reliably catch the next one; an import graph test can.

If one of these fails, the fix is almost never to edit the test. It is to move the
code to the layer that is allowed to hold it. The one case that justifies changing a
rule is a new layer, which should arrive with its own entry here.
"""

from __future__ import annotations

import ast
import pathlib
import re

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "jc"

#: Layers a given layer may NOT import. Read "mcp" as "the agent tool surface".
FORBIDDEN: dict[str, set[str]] = {
    # Business logic must not depend on any inbound adapter. A tool call, an HTTP
    # request and a script are all callers; a caller is never a dependency.
    "services": {"mcp", "api", "diagnostics"},
    # The tool surface is an adapter: it may use services, never the reverse.
    "mcp": {"api", "diagnostics"},
    # Model transport is infrastructure. It had to import a business service to log
    # a call once, which made the audit log unusable from anywhere but a service.
    "llm": {"services", "mcp", "api", "agent", "adapters", "diagnostics"},
    # Pure domain knowledge: data and functions, no I/O, no orchestration.
    "domain": {"services", "mcp", "api", "llm", "agent", "adapters", "stores", "diagnostics"},
    # Ownership guards sit below everything that needs to authorize anything.
    "authz": {"services", "mcp", "api", "llm", "agent", "adapters", "diagnostics"},
    # Persistence maps rows; it does not decide anything.
    "stores": {"services", "mcp", "api", "llm", "agent", "adapters", "diagnostics"},
    # Skill composition is prompt assembly over domain knowledge.
    "skills": {"services", "mcp", "api", "agent", "adapters", "diagnostics"},
    # The agent layer owns roles, tool catalog and message shaping, not the tool
    # handlers themselves.
    "agent": {"mcp", "api", "diagnostics"},
}


def _imports(path: pathlib.Path) -> set[str]:
    """Every `jc.<layer>` this file imports, including imports inside functions.

    Walking the whole tree rather than the module top level is the point: a
    function-local import is still a dependency, and hiding a cycle inside a
    function is exactly how the previous one survived.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if parts[0] == "jc" and len(parts) > 1:
                found.add(parts[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "jc" and len(parts) > 1:
                    found.add(parts[1])
    return found


def test_layer_dependencies_point_one_way() -> None:
    violations: list[str] = []
    for layer, banned in FORBIDDEN.items():
        root = SRC / layer
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            for imported in sorted(_imports(path) & banned):
                violations.append(
                    f"{path.relative_to(SRC)} imports jc.{imported} "
                    f"(layer '{layer}' may not depend on '{imported}')"
                )
    assert not violations, "Layer violations:\n" + "\n".join(violations)


def test_no_module_imports_itself_across_layers() -> None:
    """A cycle between two specific modules, which the layer rules can miss.

    Same-layer cycles are legal by the rules above but still deadly at import time,
    so the pair that previously existed (`services.agent_service` <-> `mcp.handlers`)
    gets checked directly.
    """
    pairs = [
        ("services/agent_service.py", "mcp"),
        ("services/interview_service.py", "mcp"),
        ("services/question_bank_service.py", "mcp"),
        ("services/answer_attempt_service.py", "mcp"),
        ("services/profile_patch_service.py", "mcp"),
    ]
    for rel, banned in pairs:
        path = SRC / rel
        assert path.exists(), rel
        assert banned not in _imports(path), f"{rel} must not import jc.{banned}"


def test_domain_layer_is_io_free() -> None:
    """Domain modules must not reach the network, disk or a database.

    The value of the domain layer is that it can be tested with no fixtures at all.
    One `open()` or one database import takes that away.
    """
    banned_modules = {"sqlalchemy", "aiomysql", "redis", "litellm", "httpx", "requests"}
    offenders: list[str] = []
    for path in sorted((SRC / "domain").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in banned_modules:
                        offenders.append(f"{path.name}: {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in banned_modules:
                    offenders.append(f"{path.name}: {node.module}")
    assert not offenders, "Domain layer must stay I/O free: " + ", ".join(offenders)


def test_multimodal_wire_format_has_one_owner() -> None:
    """Only `jc.llm.vision` may hand-assemble an OpenAI image content part.

    This was duplicated in resume OCR and in agent chat attachments, each with its
    own base64 handling. Two copies of a provider wire format means the next fix
    lands in one of them.
    """
    owner = SRC / "llm" / "vision.py"
    # Matches *constructing* an image part (`"image_url": {...}`), not reading one.
    # The audit log inspects `type == "image_url"` to redact images, which is a
    # consumer and entirely correct.
    construct = re.compile(r"""["\']image_url["\']\s*:\s*\{""")
    offenders: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        if path == owner:
            continue
        if construct.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(SRC)))
    assert not offenders, (
        "Build image parts via jc.llm.vision.image_part instead of inline dicts: "
        + ", ".join(offenders)
    )
