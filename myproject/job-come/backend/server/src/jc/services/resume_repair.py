"""Decide whether a generated draft is worth one targeted rewrite, and whether to keep it.

Five evaluators already measure a draft -- blueprint, structure, coverage, writing
invariants, and the model reviewer. Every one of them ran *after* generation and reported
to the user, and none of them reached the writer. The system could state precisely that a
block opened with its weakest line, or that three source highlights never made it into
the document, and then printed that sentence for the user to act on.

This module closes that loop, and deliberately contains no model call. Every decision
here -- what to repair, whether the result is better, whether it is still honest -- is a
pure function over the same evaluators the UI already shows. `resume_elevator` owns the
single impure step.

Two standing positions in this codebase argue against asking a model twice:
`profile_ingest_service` ("never retry the same model pipeline merely because its
previous request timed out") and `writing_invariants` ("prompts are not enforcement -- a
retry re-introduces the behaviour"). Both are respected rather than overridden:

* A repair never follows a *failure*. When the writer chain fell over, the draft carries
  `generation.mode == "source_layout"` and `plan_repair` returns None. Retrying a failed
  pipeline is exactly what the first position forbids.
* Honesty is enforced by measurement, not by instruction. `accept_repair` discards a
  candidate whose fabrication set grew, whatever the prompt asked for. The second
  position is the reason that gate exists.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any

from jc.domain.role_families import RolePlaybook, get_playbook
from jc.schemas.profile_payload import ProfilePayload
from jc.services.resume_blueprint import evaluate_blueprint
from jc.services.resume_coverage import audit_coverage
from jc.services.resume_structure import audit_structure, score_bullet
from jc.services.writing_invariants import audit_additions

#: Placeholder bullets the deterministic builder writes for a role with no highlights.
#: They are scored like prose by `score_bullet` (measured: -2.00), so they would drag a
#: quality score down and make any rewrite look like an improvement. Kept in sync with
#: `ResumeService._PENDING_PLACEHOLDERS` by a test rather than by import, because this
#: module must not depend on the service layer.
PLACEHOLDERS = ("（待补充经历要点）", "(Add experience highlights)")

#: Structure findings a rewrite can legitimately act on, mapped to the instruction given
#: to the writer. `missing_scope_line` is deliberately absent -- see `plan_repair`.
_ACTIONABLE = {
    "weak_lead_bullet": (
        "这段的第一条要点不是最有分量的那条。在本段已有事实内重写，"
        "把最强的成果放到首条，不要新增事实，不要拆散项目叙事。"
    ),
    "missing_summary": "缺少摘要。按岗位族的摘要公式写一段，只用档案已有的事实。",
    "summary_not_conclusion_first": "摘要没有结论先行。先给定位与最强证据，再补方向。",
}

_INDEX = re.compile(r"^(experience_blocks|project_blocks)\[(\d+)\]")


@dataclass(frozen=True, slots=True)
class RepairTarget:
    """One block to rewrite, with the measured reasons it needs rewriting."""

    collection: str
    index: int
    block_id: str | None
    reasons: tuple[str, ...]
    #: Source highlights the draft dropped that belong to this block, verbatim. The
    #: writer is asked to put them back rather than to invent a replacement.
    dropped: tuple[str, ...] = ()

    @property
    def path(self) -> str:
        return f"{self.collection}[{self.index}]"


@dataclass(frozen=True, slots=True)
class RepairPlan:
    blocks: tuple[RepairTarget, ...] = ()
    #: Document-level instructions (summary shape, outcome density) that are not scoped
    #: to one block.
    document: tuple[str, ...] = ()

    @property
    def empty(self) -> bool:
        return not self.blocks and not self.document

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocks": [
                {"path": t.path, "id": t.block_id, "reasons": list(t.reasons),
                 "dropped": list(t.dropped)}
                for t in self.blocks
            ],
            "document": list(self.document),
        }


@dataclass(frozen=True, slots=True)
class QualityScore:
    """Comparable quality of one draft. Higher is better on every component.

    Ordered as a tuple so comparison is lexicographic: a requirement met or a structure
    defect removed outweighs any amount of bullet-score drift, and bullet score only
    breaks ties. `blueprint_met` is a count out of a family-dependent total (5, or 6 for
    `design`), so these are only ever compared between two drafts of the *same* profile.
    """

    blueprint_met: int = 0
    structure_clean: int = 0
    covered: int = 0
    bullet_score: float = 0.0

    def as_tuple(self) -> tuple[int, int, int, float]:
        return (self.blueprint_met, self.structure_clean, self.covered,
                round(self.bullet_score, 3))

    def to_dict(self) -> dict[str, Any]:
        return {
            "blueprint_met": self.blueprint_met,
            "structure_clean": self.structure_clean,
            "covered": self.covered,
            "bullet_score": round(self.bullet_score, 3),
        }


@dataclass(frozen=True, slots=True)
class RepairVerdict:
    accepted: bool
    reason: str
    before: QualityScore | None = None
    after: QualityScore | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"accepted": self.accepted, "reason": self.reason}
        if self.before is not None:
            out["before"] = self.before.to_dict()
        if self.after is not None:
            out["after"] = self.after.to_dict()
        return out


@dataclass(slots=True)
class _Targets:
    reasons: dict[tuple[str, int], list[str]] = field(default_factory=dict)
    dropped: dict[tuple[str, int], list[str]] = field(default_factory=dict)


def _real_bullets(block: Any) -> list[str]:
    if not isinstance(block, dict):
        return []
    return [
        b for b in (block.get("bullets") or [])
        if isinstance(b, str) and b.strip() and b.strip() not in PLACEHOLDERS
    ]


def measured_track(sections: dict[str, Any]) -> dict[str, Any]:
    """The document to measure. A bilingual wrapper carries no bullets of its own.

    Public because the elevator reads the same track when it assembles the repair
    request: two answers to "which document is this" would let the plan describe one
    draft while the payload quotes another.
    """
    if sections.get("track") == "bilingual":
        return sections.get("zh_sections") or {}
    return sections



def plan_repair(
    sections: dict[str, Any],
    profile: ProfilePayload | None,
    *,
    role_family: str | None = None,
) -> RepairPlan | None:
    """What a second pass should fix, or None when a second pass is not warranted.

    Returns None -- costing nothing -- in three cases that matter more than the
    thresholds:

    * **The writer never ran.** `generation.mode == "source_layout"` means the chain
      failed and this is the profile's own wording laid out. Rewriting it is retrying a
      failed pipeline, and the user already gets an explicit "AI 写作未完成" notice.
    * **No profile.** Every honesty and coverage gate in `accept_repair` needs the source
      to compare against; `audit_additions` reports `holds` vacuously without one. A
      rewrite we cannot verify is a rewrite we do not make.
    * **Nothing measurably wrong.** The common case, and the reason this is affordable.

    `missing_scope_line` is never a repair reason even though `audit_structure` reports
    it. The only source of a scope line is the `scope` the user typed; with none in the
    profile, asking a model to supply one is asking it to invent a team size -- into the
    single highest-leverage line in the document. The right fix is to ask the user, which
    `evidence_gaps` already does. It would also fire on every English draft, where
    `scope_line` is structurally always None.
    """
    if profile is None:
        return None
    generation = sections.get("generation")
    if isinstance(generation, dict) and generation.get("mode") == "source_layout":
        return None

    doc = measured_track(sections)
    family = role_family or doc.get("role_family")
    found = _Targets()
    document: list[str] = []

    for issue in audit_structure(doc, role_family=family).issues:
        instruction = _ACTIONABLE.get(issue.code)
        if instruction is None:
            continue
        match = _INDEX.match(issue.field_path or "")
        if match is None:
            if instruction not in document:
                document.append(instruction)
            continue
        key = (match.group(1), int(match.group(2)))
        found.reasons.setdefault(key, [])
        if instruction not in found.reasons[key]:
            found.reasons[key].append(instruction)

    report = evaluate_blueprint(doc, role_family=family)
    for finding in report.findings:
        if finding.met or finding.requirement.id != "outcome_density":
            continue
        document.append(
            "多数要点应当带结果。把源文里已有但被压掉的结果显化出来"
            f"（当前 {finding.detail}）；档案里没有数字就说清做到了什么，不要编造数字。"
        )

    # A dropped highlight is the one defect where the writer needs the source text, not a
    # description of the problem. `DroppedHighlight` carries no field path, so it is
    # attached by matching the source entity's identity to the rendered block.
    coverage = audit_coverage(doc, profile)
    if coverage.dropped:
        for item in coverage.dropped:
            key = _locate_origin(doc, profile, item)
            if key is None:
                continue
            found.dropped.setdefault(key, [])
            if item.text not in found.dropped[key]:
                found.dropped[key].append(item.text)

    targets: list[RepairTarget] = []
    for key in sorted(set(found.reasons) | set(found.dropped)):
        collection, index = key
        rendered = doc.get(collection) or []
        block = rendered[index] if index < len(rendered) else None
        if not isinstance(block, dict):
            continue
        reasons = list(found.reasons.get(key, []))
        dropped = tuple(found.dropped.get(key, []))
        if dropped:
            reasons.append(
                "下列源要点在优化稿里丢失了，请放回本段，保持原有事实不变："
                + " / ".join(dropped)
            )
        targets.append(
            RepairTarget(
                collection=collection,
                index=index,
                block_id=block.get("id") if isinstance(block.get("id"), str) else None,
                reasons=tuple(reasons),
                dropped=dropped,
            )
        )

    plan = RepairPlan(blocks=tuple(targets), document=tuple(document))
    return None if plan.empty else plan


def _locate_origin(
    doc: dict[str, Any], profile: ProfilePayload, item: Any
) -> tuple[str, int] | None:
    """Map a dropped source highlight back to the block that should carry it.

    `DroppedHighlight.where` is a display label (`"公司 · 职位"` or a project name) and
    `origin` is `"experience"`/`"project"`. The stable join is the source entity's id,
    matched against the rendered block's `id`; an entity whose block the writer dropped
    entirely has nowhere to go and is skipped rather than guessed at.
    """
    origin = getattr(item, "origin", None)
    text = getattr(item, "text", "")
    if origin == "experience":
        entities, collection = profile.experiences, "experience_blocks"
    elif origin == "project":
        entities, collection = profile.projects, "project_blocks"
    else:
        return None
    owner = next(
        (e for e in entities if any(text == (h or "").strip() for h in (e.highlights or []))),
        None,
    )
    if owner is None:
        owner = next(
            (e for e in entities if getattr(e, "description", None)
             and (e.description or "").strip() == text),
            None,
        )
    if owner is None:
        return None
    for index, block in enumerate(doc.get(collection) or []):
        if isinstance(block, dict) and block.get("id") == owner.id:
            return (collection, index)
    return None


def quality_score(
    sections: dict[str, Any],
    profile: ProfilePayload | None,
    *,
    role_family: str | None = None,
) -> QualityScore:
    """Measure a draft on the four signals that already exist.

    `score_bullet` is the only continuous signal in the whole evaluation surface; the
    rest are booleans. It is used as the last tiebreaker so a draft cannot be accepted
    for wordsmithing alone -- a requirement met or a defect removed has to come first.
    """
    doc = measured_track(sections)
    family = role_family or doc.get("role_family")
    playbook: RolePlaybook = get_playbook(family)
    report = evaluate_blueprint(doc, role_family=family)
    structure = audit_structure(doc, role_family=family)
    coverage = audit_coverage(doc, profile)
    bullets = [
        b
        for key in ("experience_blocks", "project_blocks")
        for block in (doc.get(key) or [])
        for b in _real_bullets(block)
    ]
    mean = (
        sum(score_bullet(b, playbook=playbook).score for b in bullets) / len(bullets)
        if bullets
        else 0.0
    )
    return QualityScore(
        blueprint_met=report.met,
        # Negated into a "higher is better" axis so every component sorts the same way.
        structure_clean=-len(structure.issues),
        covered=coverage.covered,
        bullet_score=mean,
    )


def _fabrication_keys(sections: dict[str, Any], profile: ProfilePayload) -> set[tuple]:
    return {
        (f.kind, f.field_path, f.detail)
        for f in audit_additions(measured_track(sections), profile).fabrications
    }


def accept_repair(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    profile: ProfilePayload | None,
    *,
    role_family: str | None = None,
) -> RepairVerdict:
    """Keep the rewrite only if it is more honest-or-equal, loses nothing, and is better.

    Three gates, in this order because the first two are about damage and the third is
    about benefit:

    1. **Honesty.** The fabrication set -- keyed on `(kind, field_path, detail)` rather
       than counted, so "fixed one, invented another" is caught -- must not grow. This is
       the gate that makes a second model call defensible at all.
    2. **Coverage.** `covered` must not fall. A rewrite that reads better by dropping a
       fact is not an improvement.
    3. **Improvement.** The score must strictly increase. Without this, a second call is
       just trading one sample for another.
    """
    if profile is None:
        return RepairVerdict(False, "no_profile_to_verify_against")
    before = quality_score(baseline, profile, role_family=role_family)
    after = quality_score(candidate, profile, role_family=role_family)
    if _fabrication_keys(candidate, profile) - _fabrication_keys(baseline, profile):
        return RepairVerdict(False, "introduced_unsupported_claim", before, after)
    if after.covered < before.covered:
        return RepairVerdict(False, "dropped_source_facts", before, after)
    if after.as_tuple() <= before.as_tuple():
        return RepairVerdict(False, "not_an_improvement", before, after)
    return RepairVerdict(True, "improved", before, after)


def merge_repaired_blocks(
    sections: dict[str, Any],
    repaired: Any,
    plan: RepairPlan,
) -> dict[str, Any]:
    """Overlay rewritten blocks onto a copy of the draft, by id and only where asked.

    Validation mirrors `ResumeElevator._preserve_source_units`: identity is the stable
    `id`, never an array position, and one source paragraph stays one paragraph. A model
    that returns an id nobody asked about, or a different number of bullets, is ignored
    for that block -- there is no safe way to guess how fragments merge, and the first
    draft is already a valid document.

    Only `bullets`, `scope_line` and `description` can be overlaid. Identity fields
    (`company`, `title`, `name`, `role`, dates, `id`) are never taken from a repair: a
    rewrite was asked for the wording of accomplishments, and letting it restate the
    employer is how a confirmed title silently reverts.
    """
    if not isinstance(repaired, dict):
        return sections
    allowed = {t.block_id: t for t in plan.blocks if t.block_id}
    out = copy.deepcopy(sections)
    doc = measured_track(out)
    for collection in ("experience_blocks", "project_blocks"):
        incoming = repaired.get(collection)
        if not isinstance(incoming, list):
            continue
        existing = doc.get(collection) or []
        by_id = {
            b["id"]: b for b in existing
            if isinstance(b, dict) and isinstance(b.get("id"), str)
        }
        for item in incoming:
            if not isinstance(item, dict):
                continue
            block_id = item.get("id")
            target = allowed.get(block_id) if isinstance(block_id, str) else None
            if target is None or target.collection != collection:
                continue
            block = by_id.get(block_id)
            if block is None:
                continue
            bullets = [b for b in (item.get("bullets") or []) if isinstance(b, str) and b.strip()]
            source_count = len(_real_bullets(block))
            # A dropped highlight is the one case where growing the block is the point.
            expected = source_count + len(target.dropped)
            if bullets and len(bullets) == expected:
                block["bullets"] = bullets
            for key in ("scope_line", "description"):
                value = item.get(key)
                # Never let a repair blank an existing line; absent means "unchanged".
                if isinstance(value, str) and value.strip() and block.get(key):
                    block[key] = value.strip()
    summary = repaired.get("summary")
    if isinstance(summary, str) and summary.strip() and plan.document:
        doc["summary"] = summary.strip()
    return out
