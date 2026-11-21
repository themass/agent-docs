"""Read-only, normalised view over a Java studio-view / snapshot response.

Accepts either key style (``workInfo`` or ``work_info``), with or without the ``{status,data,...}``
envelope, and with or without the studio-view extras (``background_lines`` ...). Everything the stubs
and the validator need to know about "what really exists" goes through here, so there is exactly one
definition of an id that resolves.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any

from agent_worker.naming import normalize_keys
from agent_worker.sanitize import is_placeholder

_LINE_REF = re.compile(r"^(?P<vid>[A-Za-z][A-Za-z0-9_-]*)#(?P<seq>\d+)$")
REF_PREFIXES = ("line", "claim", "background", "annotation", "source", "version", "work", "coverage")


def _rows(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data.get(key)
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def unwrap(raw: Any) -> dict[str, Any]:
    """Strip the Java ``AgentResponse`` envelope if present."""
    if not isinstance(raw, dict):
        return {}
    if "data" in raw and isinstance(raw["data"], dict) and (
        "status" in raw or "audit_refs" in raw or "auditRefs" in raw
    ):
        return raw["data"]
    return raw


class SnapshotView:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.work = _as_dict(data.get("work"))
        self.work_info = _as_dict(data.get("work_info"))
        self.versions = _rows(data, "versions")
        self.lines = _rows(data, "lines")
        self.claims = _rows(data, "claims")
        self.citations = _rows(data, "citations")
        self.backgrounds = _rows(data, "backgrounds")
        self.annotations = _rows(data, "annotations")
        self.sources = _rows(data, "sources")
        self.background_lines = _rows(data, "background_lines")
        self.coverage_rows = _rows(data, "coverage_rows")
        self.gap_report = _as_dict(data.get("gap_report"))
        self.has_background_lines = isinstance(data.get("background_lines"), list)
        self.has_coverage_rows = isinstance(data.get("coverage_rows"), list)
        self.claim_status_by_id = _as_dict(data.get("claim_status_by_id"))
        self.content_status_by_id = _as_dict(data.get("content_status_by_id"))
        self.version_status_by_id = _as_dict(data.get("version_status_by_id"))
        self.source_verification_by_id = _as_dict(data.get("source_verification_by_id"))

        self.work_id: str = str(self.work.get("id") or self.work_info.get("id") or data.get("work_id") or "")
        self.title: str = str(self.work.get("title") or "")
        self.version_ids: list[str] = [str(v["id"]) for v in self.versions if v.get("id")]
        self.claim_by_id = {str(c["id"]): c for c in self.claims if c.get("id")}
        self.source_by_id = {str(s["id"]): s for s in self.sources if s.get("id")}
        self.background_by_id = {str(b["id"]): b for b in self.backgrounds if b.get("id")}
        self.annotation_by_id = {str(a["id"]): a for a in self.annotations if a.get("id")}
        self.version_by_id = {str(v["id"]): v for v in self.versions if v.get("id")}

        self.line_seqs: dict[str, list[int]] = defaultdict(list)
        self.line_content: dict[tuple[str, int], str] = {}
        for row in self.lines:
            try:
                key = (str(row["version_id"]), int(row["line_seq"]))
            except (KeyError, TypeError, ValueError):
                continue
            self.line_seqs[key[0]].append(key[1])
            self.line_content[key] = str(row.get("content") or "")
        for seqs in self.line_seqs.values():
            seqs.sort()

        self.citations_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in self.citations:
            if row.get("claim_id"):
                self.citations_by_claim[str(row["claim_id"])].append(row)

        self.lines_of_background: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for row in self.background_lines:
            try:
                self.lines_of_background[str(row["background_id"])].append(
                    (str(row["version_id"]), int(row["line_seq"]))
                )
            except (KeyError, TypeError, ValueError):
                continue

        self.annotations_by_line: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
        for row in self.annotations:
            try:
                self.annotations_by_line[(str(row["version_id"]), int(row["line_seq"]))].append(row)
            except (KeyError, TypeError, ValueError):
                continue

        self._ids: dict[str, set[str]] = self._collect_ids()
        self._corpus: str | None = None

    # ---- construction -------------------------------------------------------------------------
    @classmethod
    def from_raw(cls, raw: Any) -> SnapshotView:
        return cls(normalize_keys(unwrap(raw)))

    # ---- ids ----------------------------------------------------------------------------------
    def _collect_ids(self) -> dict[str, set[str]]:
        ids: dict[str, set[str]] = {k: set() for k in REF_PREFIXES}
        if self.work_id:
            ids["work"].add(self.work_id)
        for key in self.content_status_by_id:
            ids["work"].add(str(key))
        ids["version"] |= set(self.version_by_id) | {str(k) for k in self.version_status_by_id}
        ids["claim"] |= set(self.claim_by_id) | {str(k) for k in self.claim_status_by_id}
        for b in self.backgrounds:
            if b.get("claim_id"):
                ids["claim"].add(str(b["claim_id"]))
        for a in self.annotations:
            if a.get("claim_id"):
                ids["claim"].add(str(a["claim_id"]))
        for c in self.citations:
            if c.get("claim_id"):
                ids["claim"].add(str(c["claim_id"]))
        ids["background"] |= set(self.background_by_id)
        ids["annotation"] |= set(self.annotation_by_id)
        ids["source"] |= set(self.source_by_id) | {str(k) for k in self.source_verification_by_id}
        for row in self.coverage_rows:
            if row.get("id"):
                ids["coverage"].add(str(row["id"]))
        for vid, seqs in self.line_seqs.items():
            for seq in seqs:
                ids["line"].add(f"{vid}#{seq}")
        return ids

    def all_ids(self) -> set[str]:
        """Every bare id that exists in the snapshot (content, version, claim, background, annotation, source)."""
        out: set[str] = set()
        for kind, values in self._ids.items():
            if kind != "line":
                out |= values
        return out

    def resolves(self, ref: str) -> bool:
        """True if ``ref`` is a real id or a ``prefix:id`` / ``line:<version>#<seq>`` reference."""
        if not isinstance(ref, str) or not ref:
            return False
        if ":" in ref:
            prefix, _, rest = ref.partition(":")
            if prefix in self._ids:
                if prefix == "line":
                    return bool(_LINE_REF.match(rest)) and rest in self._ids["line"]
                return rest in self._ids[prefix]
            return False
        return ref in self.all_ids()

    def has_claim(self, ref: str) -> bool:
        """``claim-x`` or ``claim:claim-x``."""
        bare = ref.removeprefix("claim:")
        return bare in self._ids["claim"]

    def has_line(self, version_id: str, line_seq: int) -> bool:
        return line_seq in self.line_seqs.get(version_id, [])

    # ---- source / claim state -----------------------------------------------------------------
    def source_verification(self, source_id: str) -> str:
        if source_id in self.source_verification_by_id:
            return str(self.source_verification_by_id[source_id])
        return str(self.source_by_id.get(source_id, {}).get("verification_status") or "UNKNOWN")

    def claim_status(self, claim_id: str) -> str:
        if claim_id in self.claim_status_by_id:
            return str(self.claim_status_by_id[claim_id])
        return str(self.claim_by_id.get(claim_id, {}).get("status") or "UNKNOWN")

    def citation_checkable(self, citation: dict[str, Any]) -> bool:
        source_id = str(citation.get("source_id") or "")
        status = str(citation.get("verification_status") or self.source_verification(source_id))
        if source_id in self.source_verification_by_id:
            status = self.source_verification(source_id)
        return status == "VERIFIED" and not is_placeholder(citation.get("locator"))

    def claim_checkable(self, claim_id: str) -> bool:
        return any(self.citation_checkable(c) for c in self.citations_by_claim.get(claim_id, []))

    def pending_sources(self) -> list[str]:
        return sorted(sid for sid in self.source_by_id if self.source_verification(sid) == "PENDING")

    # ---- misc ---------------------------------------------------------------------------------
    def corpus(self) -> str:
        """All snapshot strings, whitespace-stripped: locator-looking text that already exists is not fabricated."""
        if self._corpus is None:
            parts: list[str] = []

            def walk(value: Any) -> None:
                if isinstance(value, str):
                    parts.append(value)
                elif isinstance(value, dict):
                    for k, v in value.items():
                        parts.append(str(k))
                        walk(v)
                elif isinstance(value, list):
                    for v in value:
                        walk(v)

            walk(self.data)
            self._corpus = re.sub(r"\s+", "", "".join(parts))
        return self._corpus

    def counts(self) -> dict[str, int]:
        return {
            "versions": len(self.versions), "lines": len(self.lines), "claims": len(self.claims),
            "citations": len(self.citations), "backgrounds": len(self.backgrounds),
            "annotations": len(self.annotations), "sources": len(self.sources),
            "background_lines": len(self.background_lines), "coverage_rows": len(self.coverage_rows),
        }

    def digest(self) -> str:
        blob = json.dumps(self.data, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()
