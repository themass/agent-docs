"""agent-output/1 -> v1 DraftProposal (contract sections 5 and 6).

Rules fixed here: ``locator`` is always null; certainty is never KNOWN; ids are minted as
``ann-<run8>-<n>`` / ``claim-ann-<run8>-<n>``; the label prefix carries the fact / interpretation /
dramatization / unknown distinction because the v1 schema has no field for it. The ``generator``
(STUB or DEERFLOW) is deliberately NOT in the proposal body; it lives only in events.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from agent_worker import vocab
from agent_worker.mapping import compose_body, map_item
from agent_worker.output_schema import AgentOutput

ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,63}$")
MAX_CHANGE_BODY = 8000


def run8(run_id: str) -> str:
    """First 8 id-safe characters of the run id (after the ``run_`` prefix)."""
    body = re.sub(r"[^A-Za-z0-9]", "", run_id.removeprefix("run_"))
    if len(body) < 8:
        body = hashlib.sha1(run_id.encode()).hexdigest()
    return body[:8]


def _dedupe(refs: list[str], limit: int = vocab.MAX_EVIDENCE_REFS) -> list[str]:
    out: list[str] = []
    for ref in refs:
        if ref not in out:
            out.append(ref)
    return out[:limit]


def compile_proposal(output: AgentOutput, run_id: str) -> dict[str, Any]:
    r8 = run8(run_id)
    n = 0
    changes: list[dict[str, Any]] = []
    for item in output.items:
        mapped = map_item(item.kind, item.epistemic, item.target_ref)
        if mapped is None:  # unreachable after validation; refuse rather than guess
            raise ValueError(f"unmappable item {item.kind}/{item.epistemic}")
        sr = item.source_request.model_dump() if item.source_request else None
        change: dict[str, Any] = {
            "change_type": mapped.change_type,
            "target_ref": item.target_ref,
            "body": compose_body(item.kind, mapped, item.body, sr),
            "classification": mapped.classification,
            "evidence_refs": _dedupe(item.evidence_refs),
            "draft_payload": None,
        }
        ann = item.annotation
        if ann is not None and item.kind == "ANNOTATION" and item.epistemic in ("INTERPRETATION", "DRAFT_TEXT"):
            n += 1
            change["draft_payload"] = {
                "operation": "CREATE_ANNOTATION",
                "id": f"ann-{r8}-{n}",
                "version_id": ann.version_id,
                "line_seq": ann.line_seq,
                "annotation_kind": ann.annotation_kind,
                "audience": ann.audience,
                "content": ann.content,
                "claim_id": f"claim-ann-{r8}-{n}",
                "claim_value": ann.claim_value or ann.content,
                "certainty": ann.certainty,
                "source_id": ann.source_id,
                "locator": None,
            }
        changes.append(change)
    if not changes:
        # v1 requires a non-empty ``changes``: a read-only report still leaves one GAP_REPORT record.
        changes.append({
            "change_type": "GAP_REPORT", "target_ref": None, "classification": "DRAFT",
            "body": "【缺口】" + output.summary[:7000], "evidence_refs": [], "draft_payload": None,
        })
    return {
        "schema_version": 1,
        "status": "DRAFT",
        "summary": output.summary[:2000],
        "changes": changes,
        "unknowns": list(output.unknowns),
        "human_review_question": output.human_review_question,
    }


def validate_proposal(proposal: dict[str, Any]) -> list[str]:
    """Same invariants as ``proposal.schema.json`` + the BFF/MCP agent rules. Returns problem codes."""
    problems: list[str] = []
    if proposal.get("schema_version") != 1:
        problems.append("P.SCHEMA_VERSION")
    if proposal.get("status") != "DRAFT":
        problems.append("P.STATUS")
    changes = proposal.get("changes")
    if not isinstance(changes, list) or not 1 <= len(changes) <= vocab.MAX_ITEMS:
        problems.append("P.CHANGES_COUNT")
        changes = changes if isinstance(changes, list) else []
    if not 1 <= len(str(proposal.get("summary", ""))) <= 2000:
        problems.append("P.SUMMARY")
    if not 1 <= len(str(proposal.get("human_review_question", ""))) <= 2000:
        problems.append("P.QUESTION")
    if not isinstance(proposal.get("unknowns"), list) or len(proposal["unknowns"]) > vocab.MAX_UNKNOWNS:
        problems.append("P.UNKNOWNS")
    for i, ch in enumerate(changes):
        at = f"changes.{i}"
        if ch.get("change_type") not in vocab.CHANGE_TYPES:
            problems.append(f"P.CHANGE_TYPE@{at}")
        if ch.get("classification") not in vocab.CLASSIFICATIONS:
            problems.append(f"P.CLASSIFICATION@{at}")
        if not 1 <= len(str(ch.get("body", ""))) <= MAX_CHANGE_BODY:
            problems.append(f"P.BODY@{at}")
        if len(ch.get("evidence_refs") or []) > vocab.MAX_EVIDENCE_REFS:
            problems.append(f"P.EVIDENCE_REFS@{at}")
        if len(str(ch.get("target_ref") or "")) > 256:
            problems.append(f"P.TARGET_REF@{at}")
        payload = ch.get("draft_payload")
        if payload is None:
            continue
        if ch.get("change_type") != "ANNOTATION" or ch.get("classification") == "UNKNOWN":
            problems.append(f"P.PAYLOAD_NOT_ALLOWED@{at}")
        if payload.get("operation") != "CREATE_ANNOTATION":
            problems.append(f"P.OPERATION@{at}")
        if payload.get("locator") not in (None, ""):
            problems.append(f"P.LOCATOR@{at}")
        if payload.get("certainty") not in vocab.CERTAINTIES_AGENT:
            problems.append(f"P.CERTAINTY@{at}")
        if payload.get("audience") not in vocab.AUDIENCES:
            problems.append(f"P.AUDIENCE@{at}")
        if payload.get("annotation_kind") not in vocab.ANNOTATION_KINDS:
            problems.append(f"P.ANNOTATION_KIND@{at}")
        for key in ("id", "version_id", "claim_id"):
            if not ID_RE.match(str(payload.get(key, ""))):
                problems.append(f"P.ID_{key.upper()}@{at}")
        if payload.get("source_id") is not None and not ID_RE.match(str(payload["source_id"])):
            problems.append(f"P.ID_SOURCE_ID@{at}")
        if not isinstance(payload.get("line_seq"), int) or isinstance(payload.get("line_seq"), bool) or payload["line_seq"] < 1:
            problems.append(f"P.LINE_SEQ@{at}")
        for key in ("content", "claim_value"):
            if not 1 <= len(str(payload.get(key, ""))) <= vocab.MAX_ANNOTATION_CONTENT:
                problems.append(f"P.{key.upper()}@{at}")
    return problems
