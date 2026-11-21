"""Shared helpers for the deterministic generators.

The STUB never calls a model and never reads the editor's free-text instructions as anything but data
(they are ignored). Its output goes through exactly the same validator as a model's output.
"""
from __future__ import annotations

from typing import Any

from agent_worker.vocab import SCHEMA_ID

SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, None: 3}


def item(
    kind: str,
    epistemic: str,
    body: str,
    *,
    target_ref: str | None = None,
    evidence_refs: list[str] | None = None,
    severity: str | None = None,
    annotation: dict[str, Any] | None = None,
    source_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    refs: list[str] = []
    for ref in evidence_refs or []:
        if ref not in refs:
            refs.append(ref)
    return {
        "kind": kind, "epistemic": epistemic, "target_ref": target_ref, "body": body[:7000],
        "evidence_refs": refs[:20], "severity": severity, "annotation": annotation,
        "source_request": source_request,
    }


def line_ref(version_id: str, line_seq: int) -> str:
    return f"line:{version_id}#{line_seq}"


def ids_ref(prefix: str, ids: list[str], limit: int = 18) -> list[str]:
    return [f"{prefix}:{i}" for i in ids[:limit]]


def sort_by_severity(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda it: SEVERITY_ORDER.get(it.get("severity"), 3))  # stable


def output(task_type: str, summary: str, items: list[dict[str, Any]], unknowns: list[str], question: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA_ID, "task_type": task_type, "summary": summary[:1500],
        "items": items[:50], "unknowns": [u[:2000] for u in unknowns[:50]],
        "human_review_question": question,
    }


def cn_join(values: list[str], limit: int = 6) -> str:
    shown = "、".join(values[:limit])
    return shown + (f" 等 {len(values)} 项" if len(values) > limit else "")


def snippet(text: str, limit: int = 40) -> str:
    one = " ".join(str(text).split())
    return one if len(one) <= limit else one[: limit - 1] + "…"
