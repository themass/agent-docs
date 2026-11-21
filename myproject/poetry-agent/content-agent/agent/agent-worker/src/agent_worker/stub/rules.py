"""The twelve compile rules (``pipeline/tools/scene-validator/rules.mjs``), evaluated at DATA level.

Names and DATA/BUNDLE split match ``agent_bff.precheck`` so triage and the pre-publication checklist
agree. BUNDLE rules are never PASS here: they need a compiled bundle and are reported NOT_EVALUATED.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from agent_worker.snapshot import SnapshotView

RULES: tuple[tuple[str, str, str], ...] = (
    ("R1", "reference exists", "DATA"),
    ("R2", "published only", "DATA"),
    ("R3", "basis", "DATA"),
    ("R4", "fallback", "BUNDLE"),
    ("R5", "coverage declared", "BUNDLE"),
    ("R6", "unknown dates", "BUNDLE"),
    ("R7", "annotations from base", "DATA"),
    ("R8", "line link", "DATA"),
    ("R9", "hash", "BUNDLE"),
    ("R10", "rights and meaning", "BUNDLE"),
    ("R11", "no pile-up", "DATA"),
    ("R12", "free movement", "BUNDLE"),
)
RULE_NAMES = {rid: name for rid, name, _ in RULES}


@dataclass
class RuleResult:
    id: str
    name: str
    evaluation: str
    status: str  # PASS | FAIL | NOT_EVALUATED
    count: int = 0
    details: list[str] = field(default_factory=list)
    refs: list[str] = field(default_factory=list)


def evaluate(view: SnapshotView) -> list[RuleResult]:
    out: list[RuleResult] = []
    for rid, name, evaluation in RULES:
        res = RuleResult(rid, name, evaluation, "NOT_EVALUATED")
        if evaluation == "DATA":
            _data(rid, view, res)
        out.append(res)
    return out


def _data(rid: str, v: SnapshotView, res: RuleResult) -> None:
    bad: list[str] = []
    refs: list[str] = []
    if rid == "R1":
        for b in v.backgrounds:
            if str(b.get("claim_id")) not in v.claim_by_id:
                bad.append(b["id"])
                refs.append(f"background:{b['id']}")
        for a in v.annotations:
            seq = a.get("line_seq")
            if not isinstance(seq, int) or not v.has_line(str(a.get("version_id")), seq):
                bad.append(a["id"])
                refs.append(f"annotation:{a['id']}")
        _settle(res, bad, refs)
    elif rid == "R2":
        if v.work and str(v.work.get("status")) != "PUBLISHED":
            bad.append(v.work_id)
            refs.append(f"work:{v.work_id}")
        for ver in v.versions:
            if v.version_status_by_id.get(ver["id"], ver.get("status")) != "PUBLISHED":
                bad.append(ver["id"])
                refs.append(f"version:{ver['id']}")
        for b in v.backgrounds:
            if v.content_status_by_id.get(b["id"]) != "PUBLISHED":
                bad.append(b["id"])
                refs.append(f"background:{b['id']}")
        for c in v.claims:
            if v.claim_status(str(c["id"])) != "PUBLISHED":
                bad.append(c["id"])
                refs.append(f"claim:{c['id']}")
        if not v.versions:
            bad.append("no-text-version")
        _settle(res, bad, refs)
    elif rid == "R3":
        if not v.claims:
            return
        for c in v.claims:
            if c.get("claim_kind") != "DRAMATIZATION" and not v.claim_checkable(str(c["id"])):
                bad.append(c["id"])
                refs.append(f"claim:{c['id']}")
        _settle(res, bad, refs)
    elif rid == "R7":
        for a in v.annotations:
            if v.claim_status(str(a.get("claim_id"))) != "PUBLISHED":
                bad.append(a["id"])
                refs.append(f"annotation:{a['id']}")
        _settle(res, bad, refs)
    elif rid == "R8":
        if not v.background_lines:
            return
        for link in v.background_lines:
            ok_line = v.has_line(str(link.get("version_id")), int(link.get("line_seq", 0)))
            if not ok_line or str(link.get("background_id")) not in v.background_by_id:
                bad.append(str(link.get("background_id")))
        _settle(res, bad, [f"background:{b}" for b in dict.fromkeys(bad)])
    elif rid == "R11":
        if not v.backgrounds or not v.has_background_lines:
            return
        for b in v.backgrounds:
            if not v.lines_of_background.get(str(b["id"])):
                bad.append(b["id"])
                refs.append(f"background:{b['id']}")
        _settle(res, bad, refs)


def _settle(res: RuleResult, bad: list[str], refs: list[str]) -> None:
    res.count = len(bad)
    res.details = list(dict.fromkeys(bad))
    res.refs = list(dict.fromkeys(refs))
    res.status = "FAIL" if bad else "PASS"
