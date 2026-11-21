"""Deterministic validation of ``agent-output/1`` (contract section 6, rules 1-8).

Every failure carries a rule id (``V1``..``V8``), a short code and a JSON-ish path. A violation never
quotes model text, so the ``OUTPUT_REJECTED`` event stays metadata-only.

    V1 structure     JSON shape, enums, lengths, schema/task_type, kind/epistemic pairing, one question
    V2 evidence      every evidence_ref / target_ref / claim_ref exists in the snapshot
    V3 fact boundary FACT_REQUEST only with source_request, never annotation; no fabricated locator
    V4 annotation    version/line exist, Java vocabulary, no KNOWN, no locator, no duplicates
    V5 capability    forbidden capability used as an instruction (guard.py)
    V6 limits        items/unknowns caps; no "already verified/published" assertion
    V7 hygiene       no active markup or invisible characters in model output
    V8 budget        output size within max_output_chars; composed body within the v1 limit
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from agent_worker import vocab
from agent_worker.guard import (
    find_active_markup,
    find_assertions,
    find_forbidden_imperatives,
    has_invisible,
)
from agent_worker.mapping import compose_body, map_item
from agent_worker.output_schema import AgentOutput
from agent_worker.snapshot import SnapshotView

# Contract section 6, rule 3. Matches that already occur verbatim in the snapshot are not fabrications.
LOCATOR_PATTERNS = (
    re.compile(r"卷[一二三四五六七八九十百零\d]+"),
    re.compile(r"第?\s*\d+\s*[页頁]"),
    # `\b` would not fire between a CJK character and "p"/"vol" (both are \w), so a page number glued to
    # Chinese text ("详见pp.12") would slip through; anchor on "not preceded by an ASCII letter" instead.
    re.compile(r"(?<![A-Za-z])p{1,2}\.?\s*\d+", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z])vol\.?\s*\d+", re.IGNORECASE),
    re.compile(r"《[^》]{2,40}》\s*卷?\s*[\d一二三四五六七八九十]+"),
)
MAX_CHANGE_BODY = 8000


@dataclass(frozen=True)
class Violation:
    rule: str
    code: str
    path: str = ""

    def __str__(self) -> str:
        return f"{self.rule}.{self.code}@{self.path}" if self.path else f"{self.rule}.{self.code}"


@dataclass
class ValidationResult:
    output: AgentOutput | None = None
    violations: list[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations and self.output is not None

    def rule_ids(self) -> list[str]:
        seen: list[str] = []
        for v in self.violations:
            if v.rule not in seen:
                seen.append(v.rule)
        return seen

    def codes(self) -> list[str]:
        out: list[str] = []
        for v in self.violations:
            code = f"{v.rule}.{v.code}"
            if code not in out:
                out.append(code)
        return out


def _path(loc: tuple[Any, ...]) -> str:
    return ".".join(str(part) for part in loc)


def _structure_violations(error: ValidationError) -> list[Violation]:
    out: list[Violation] = []
    for err in error.errors():
        loc = tuple(err["loc"])
        kind = err["type"]
        if loc in (("items",), ("unknowns",)) and kind == "too_long":
            out.append(Violation("V6", "TOO_MANY_ITEMS" if loc[0] == "items" else "TOO_MANY_UNKNOWNS", loc[0]))
            continue
        if loc and loc[-1] == "evidence_refs" and kind == "too_long":
            out.append(Violation("V2", "TOO_MANY_REFS", _path(loc)))
            continue
        code = {
            "missing": "MISSING", "extra_forbidden": "EXTRA_FIELD", "literal_error": "ENUM",
            "string_too_long": "TOO_LONG", "string_too_short": "TOO_SHORT", "too_long": "TOO_LONG",
        }.get(kind, "TYPE")
        out.append(Violation("V1", code, _path(loc)))
    return out


def _strings(output: AgentOutput) -> list[tuple[str, str]]:
    """Every free-text field with its path. Ids and refs are excluded."""
    out: list[tuple[str, str]] = [("summary", output.summary), ("human_review_question", output.human_review_question)]
    out += [(f"unknowns.{i}", u) for i, u in enumerate(output.unknowns)]
    for i, item in enumerate(output.items):
        out.append((f"items.{i}.body", item.body))
        if item.annotation:
            out.append((f"items.{i}.annotation.content", item.annotation.content))
            if item.annotation.claim_value:
                out.append((f"items.{i}.annotation.claim_value", item.annotation.claim_value))
        if item.source_request:
            out.append((f"items.{i}.source_request.what_to_verify", item.source_request.what_to_verify))
            if item.source_request.suggested_source_title:
                out.append((f"items.{i}.source_request.suggested_source_title", item.source_request.suggested_source_title))
    return out


def _fabricated_locator(text: str, view: SnapshotView) -> bool:
    for pattern in LOCATOR_PATTERNS:
        for match in pattern.finditer(text):
            if re.sub(r"\s+", "", match.group(0)) not in view.corpus():
                return True
    return False


def validate_output(
    raw: Any,
    view: SnapshotView,
    *,
    expected_task_type: str,
    max_output_chars: int = 60000,
) -> ValidationResult:
    result = ValidationResult()
    if not isinstance(raw, dict):
        result.violations.append(Violation("V1", "NOT_OBJECT"))
        return result
    try:
        output = AgentOutput.model_validate(raw)
    except ValidationError as exc:
        result.violations.extend(_structure_violations(exc))
        return result
    result.output = output
    add = result.violations.append

    # ---- V1 ----
    if output.task_type != expected_task_type:
        add(Violation("V1", "TASK_TYPE_MISMATCH", "task_type"))
    if len(re.findall(r"[?？]", output.human_review_question)) != 1:
        add(Violation("V1", "REVIEW_QUESTION_COUNT", "human_review_question"))

    seen_annotations: set[tuple[str, int, str, str]] = set()
    for i, item in enumerate(output.items):
        at = f"items.{i}"
        mapped = map_item(item.kind, item.epistemic, item.target_ref)

        # V3: fact boundary comes before the generic pairing check so the specific rule is reported.
        if item.epistemic == "FACT_REQUEST" and item.kind != "SOURCE_REQUEST":
            add(Violation("V3", "FACT_REQUEST_KIND", f"{at}.kind"))
        elif mapped is None:
            add(Violation("V1", "KIND_EPISTEMIC_MISMATCH", at))
        if item.epistemic == "FACT_REQUEST":
            if item.source_request is None:
                add(Violation("V3", "SOURCE_REQUEST_MISSING", f"{at}.source_request"))
            if item.annotation is not None:
                add(Violation("V3", "ANNOTATION_ON_FACT", f"{at}.annotation"))
        elif item.source_request is not None:
            add(Violation("V3", "SOURCE_REQUEST_ON_WRONG_ITEM", f"{at}.source_request"))
        if item.kind == "SOURCE_REQUEST" and item.source_request is None:
            add(Violation("V3", "SOURCE_REQUEST_MISSING", f"{at}.source_request"))

        # V2 evidence
        for j, ref in enumerate(item.evidence_refs):
            if not view.resolves(ref):
                add(Violation("V2", "EVIDENCE_REF_UNKNOWN", f"{at}.evidence_refs.{j}"))
        if item.target_ref is not None and not view.resolves(item.target_ref):
            add(Violation("V2", "TARGET_REF_UNKNOWN", f"{at}.target_ref"))
        sr = item.source_request
        if sr is not None:
            if sr.claim_ref is not None and not view.has_claim(sr.claim_ref):
                add(Violation("V2", "CLAIM_REF_UNKNOWN", f"{at}.source_request.claim_ref"))
            if sr.locator not in (None, ""):
                add(Violation("V3", "LOCATOR_NOT_NULL", f"{at}.source_request.locator"))
            if sr.suggested_source_kind is not None and sr.suggested_source_kind not in vocab.SOURCE_KINDS:
                add(Violation("V3", "SOURCE_KIND_INVALID", f"{at}.source_request.suggested_source_kind"))

        # V4 annotation
        ann = item.annotation
        if ann is not None and item.epistemic != "FACT_REQUEST":
            if item.kind != "ANNOTATION" or item.epistemic not in ("INTERPRETATION", "DRAFT_TEXT"):
                add(Violation("V4", "ANNOTATION_PAYLOAD_NOT_ALLOWED", f"{at}.annotation"))
            a = f"{at}.annotation"
            if ann.version_id not in view.version_by_id:
                add(Violation("V4", "VERSION_UNKNOWN", f"{a}.version_id"))
            elif ann.line_seq < 1 or not view.has_line(ann.version_id, ann.line_seq):
                add(Violation("V4", "LINE_UNKNOWN", f"{a}.line_seq"))
            if ann.annotation_kind not in vocab.ANNOTATION_KINDS:
                add(Violation("V4", "KIND_INVALID", f"{a}.annotation_kind"))
            if ann.audience not in vocab.AUDIENCES:
                add(Violation("V4", "AUDIENCE_INVALID", f"{a}.audience"))
            if ann.certainty == "KNOWN":
                add(Violation("V4", "CERTAINTY_KNOWN_FORBIDDEN", f"{a}.certainty"))
            elif ann.certainty not in vocab.CERTAINTIES_AGENT:
                add(Violation("V4", "CERTAINTY_INVALID", f"{a}.certainty"))
            if ann.source_id is not None and ann.source_id not in view.source_by_id:
                add(Violation("V4", "SOURCE_UNKNOWN", f"{a}.source_id"))
            if len(ann.content) > vocab.MAX_ANNOTATION_CONTENT:
                add(Violation("V4", "CONTENT_TOO_LONG", f"{a}.content"))
            if ann.claim_value is not None and len(ann.claim_value) > vocab.MAX_ANNOTATION_CONTENT:
                add(Violation("V4", "CLAIM_VALUE_TOO_LONG", f"{a}.claim_value"))
            if ann.locator not in (None, ""):
                add(Violation("V4", "LOCATOR_NOT_NULL", f"{a}.locator"))
            key = (ann.version_id, ann.line_seq, ann.annotation_kind, ann.content)
            if key in seen_annotations:
                add(Violation("V4", "DUPLICATE_ANNOTATION", a))
            seen_annotations.add(key)

        # V8: the composed v1 body must fit
        if mapped is not None and len(
            compose_body(item.kind, mapped, item.body, sr.model_dump() if sr else None)
        ) > MAX_CHANGE_BODY:
            add(Violation("V8", "COMPOSED_BODY_TOO_LONG", f"{at}.body"))

    # ---- text rules over every free-text field ----
    total = 0
    for path, text in _strings(output):
        total += len(text)
        in_free_text = path.startswith("items.") and (
            path.endswith(".body") or ".source_request." in path or ".annotation." in path)
        if in_free_text and _fabricated_locator(text, view):
            add(Violation("V3", "FABRICATED_LOCATOR", path))
        if find_forbidden_imperatives(text):
            add(Violation("V5", "FORBIDDEN_CAPABILITY_REQUEST", path))
        if find_assertions(text):
            add(Violation("V6", "VERIFIED_ASSERTION", path))
        if find_active_markup(text):
            add(Violation("V7", "ACTIVE_MARKUP", path))
        elif has_invisible(text):
            add(Violation("V7", "INVISIBLE_CHARACTERS", path))
    if total > max_output_chars:
        add(Violation("V8", "OUTPUT_TOO_LONG"))
    return result
