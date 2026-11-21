"""Deterministic generators for the five task types (the STUB runtime). No model is ever called."""
from __future__ import annotations

from typing import Any

from agent_worker.snapshot import SnapshotView
from agent_worker.stub import (
    annotation_draft,
    compile_triage,
    content_review,
    gap_analysis,
    script_draft,
)

GENERATORS = {
    "GAP_ANALYSIS": gap_analysis.generate,
    "ANNOTATION_DRAFT": annotation_draft.generate,
    "SCRIPT_DRAFT": script_draft.generate,
    "COMPILE_TRIAGE": compile_triage.generate,
    "CONTENT_REVIEW": content_review.generate,
}


def generate(task_type: str, view: SnapshotView) -> dict[str, Any]:
    """The agent-output/1 dict for ``task_type``. The editor's instructions are deliberately not an input."""
    generator = GENERATORS.get(task_type)
    if generator is None:
        raise ValueError(f"unsupported task_type: {task_type}")
    # A KeyError raised *inside* a generator is a real bug and must surface as itself, not be
    # relabelled as an unsupported task type.
    return generator(view)
