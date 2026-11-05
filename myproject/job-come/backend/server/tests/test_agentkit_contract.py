"""JC's calls into agentkit must match the agentkit types they construct.

A keyword that agentkit does not declare fails only when that code path runs: session creation
raised `TypeError` in production after a rename on the JC side never reached agentkit. These checks
read the call sites and the dataclass, so the mismatch fails in the suite instead.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

from agentkit.adapters.deerflow.client import AgentRunMetadata

SRC = Path(__file__).resolve().parents[1] / "src" / "jc"


def _calls_to(name: str) -> list[tuple[Path, ast.Call]]:
    found = []
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text("utf-8"), filename=str(path))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == name:
                found.append((path, node))
    return found


def test_every_run_metadata_keyword_is_a_field_agentkit_declares():
    fields = {f.name for f in dataclasses.fields(AgentRunMetadata)}
    calls = _calls_to("AgentRunMetadata")
    assert calls, "no AgentRunMetadata construction found; the check would prove nothing"
    unknown = {
        f"{path.relative_to(SRC)}:{node.lineno}": sorted(
            kw.arg for kw in node.keywords if kw.arg not in fields
        )
        for path, node in calls
        if any(kw.arg not in fields for kw in node.keywords)
    }
    assert not unknown, f"keywords agentkit's AgentRunMetadata does not declare: {unknown}"


def test_every_run_metadata_call_supplies_the_required_fields():
    required = {
        f.name
        for f in dataclasses.fields(AgentRunMetadata)
        if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
    }
    for path, node in _calls_to("AgentRunMetadata"):
        given = {kw.arg for kw in node.keywords}
        missing = required - given
        assert not missing, f"{path.relative_to(SRC)}:{node.lineno} omits {sorted(missing)}"
