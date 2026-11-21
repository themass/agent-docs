"""Lesson context: what each role is allowed to read, assembled BEFORE any model is called.

The bundle's spoken lines have no ids of their own, so this module gives each one a deterministic id,
``{step}/{layer}/{index}`` (index counts lines of that layer within that step, narrator and poet lines
together). Annotations are ``ann:{annotation_id}``. Nothing here modifies the bundle.

Permission by construction: the poet is handed only the roleplay lines of the meet step. A question about
the wider world has no material in the poet's context, so there is nothing to invent from.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("student_agent.lesson")

_SAFE_WORK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


@dataclass(frozen=True)
class Fact:
    id: str
    text: str
    kind: str  # FACT | INTERPRETATION | DRAMATIZATION | ANNOTATION
    owner: str  # poet | narrator
    step: str
    layer: str | None = None
    claim_id: str | None = None
    line_seqs: tuple[int, ...] = ()
    ann_kind: str | None = None


def badge_for(role: str, facts: list[Fact]) -> str:
    """The badge is computed from the facts actually used, never taken from a model."""
    kinds = {f.kind for f in facts}
    if role == "poet" or "DRAMATIZATION" in kinds:
        return "DRAMATIZATION"
    if "INTERPRETATION" in kinds:
        return "INTERPRETATION"
    if "FACT" in kinds:
        return "FACT"
    return "NONE"


@dataclass
class LessonContext:
    bundle_hash: str
    work_id: str
    facts: dict[str, Fact]
    lines: dict[int, str]
    sidecar: dict[str, Any]
    warnings: list[str] = field(default_factory=list)

    def role_facts(self, role: str) -> list[Fact]:
        """The only facts a role may be shown. The guide reads the sidecar, never facts."""
        if role == "poet":
            return [f for f in self.facts.values() if f.owner == "poet"]
        if role == "narrator":
            return [f for f in self.facts.values() if f.owner == "narrator"]
        return []

    def layer_facts(self, layer: str, step: str = "arrive") -> list[Fact]:
        return [f for f in self.facts.values() if f.owner == "narrator" and f.step == step and f.layer == layer
                and f.kind != "ANNOTATION"]

    def annotations_for(self, seq: int, kinds: set[str] | None = None) -> list[Fact]:
        out = []
        for f in self.facts.values():
            if f.kind != "ANNOTATION" or seq not in f.line_seqs:
                continue
            if kinds is not None and (f.ann_kind or "") not in kinds:
                continue
            out.append(f)
        return out

    def pick(self, step: str, ref: str | None, layer: str | None) -> Fact | None:
        """Choose one script fact for rephrase/basis. Role scope is enforced here."""
        want_owner = "poet" if step == "meet" else "narrator"
        if ref and ref in self.facts:
            f = self.facts[ref]
            return f if f.owner == want_owner and f.kind != "ANNOTATION" else None
        pool = [f for f in self.facts.values() if f.owner == want_owner and f.kind != "ANNOTATION"]
        if layer:
            pool = [f for f in pool if f.layer == layer]
        in_step = [f for f in pool if f.step == step]
        return (in_step or pool or [None])[0]

    @property
    def forbidden(self) -> list[str]:
        return [str(x) for x in self.sidecar.get("forbidden_entities", [])]

    @property
    def allowed_text(self) -> str:
        return "".join(f.text for f in self.facts.values()) + "".join(self.lines.values())


def build_context(bundle: dict[str, Any], pack: dict[str, Any], sidecar: dict[str, Any],
                  work_id: str, bundle_hash: str) -> LessonContext:
    facts: dict[str, Fact] = {}
    warnings: list[str] = []
    for step in bundle.get("steps", []):
        sid = str(step.get("step"))
        groups: list[tuple[dict[str, Any], str]] = [(layer, "narrator") for layer in step.get("layers") or []]
        roleplay = step.get("roleplay") or {}
        groups += [(layer, "poet") for layer in roleplay.get("layers") or []]
        counters: dict[str, int] = {}
        for layer, owner in groups:
            lname = str(layer.get("layer"))
            seqs = tuple(int(x) for x in layer.get("line_seqs") or [])
            for line in layer.get("lines") or []:
                idx = counters.get(lname, 0)
                counters[lname] = idx + 1
                kind = str(line.get("kind"))
                fid = f"{sid}/{lname}/{idx}"
                if kind == "DRAMATIZATION" and not line.get("badge"):
                    # An unlabelled dramatization is never spoken: same rule the page applies.
                    warnings.append(f"{fid}: dramatization without badge skipped")
                    continue
                claim = (line.get("basis") or {}).get("claim_id") if line.get("basis") else None
                facts[fid] = Fact(fid, str(line.get("text", "")), kind, owner, sid, lname, claim, seqs)
    for a in pack.get("annotations", []) or []:
        aid = f"ann:{a.get('id')}"
        facts[aid] = Fact(aid, str(a.get("text", "")), "ANNOTATION", "narrator", "*", None, None,
                          (int(a.get("lineSeq", 0)),), ann_kind=a.get("kind"))
    lines = {int(x["seq"]): str(x["text"]) for x in pack.get("lines", []) or [] if "seq" in x}
    clean = _validate_sidecar(sidecar, facts, warnings)
    return LessonContext(bundle_hash, work_id, facts, lines, clean, warnings)


def _validate_sidecar(sidecar: dict[str, Any], facts: dict[str, Fact], warnings: list[str]) -> dict[str, Any]:
    """Drop anything in the sidecar that points at a fact the bundle does not contain."""
    clean = dict(sidecar)
    points = []
    for p in sidecar.get("points", []) or []:
        ref = p.get("supplement_ref")
        if ref and ref not in facts:
            warnings.append(f"point {p.get('id')}: supplement_ref {ref} not in bundle; supplement dropped")
            p = {**p, "supplement_ref": None}
        points.append(p)
    clean["points"] = points
    faq = []
    for item in sidecar.get("faq", []) or []:
        if item.get("answer_ref") in facts:
            faq.append(item)
        else:
            warnings.append(f"faq {item.get('id')}: answer_ref not in bundle; entry dropped")
    clean["faq"] = faq
    return clean


_SIDECAR_CACHE: dict[tuple[str, str], dict[str, Any]] = {}


def load_sidecar(lessons_dir: Path, work_id: str) -> dict[str, Any]:
    """``lesson.<work-id without 'work-'>.json``. Missing file -> empty sidecar (generic guide wording only)."""
    if not _SAFE_WORK.match(work_id):
        return {}
    key = (str(lessons_dir), work_id)
    if key in _SIDECAR_CACHE:
        return _SIDECAR_CACHE[key]
    slug = work_id.removeprefix("work-")
    path = (lessons_dir / f"lesson.{slug}.json").resolve()
    data: dict[str, Any] = {}
    try:
        if lessons_dir.resolve() in path.parents:
            data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log.warning("lesson sidecar unreadable for work")
    _SIDECAR_CACHE[key] = data
    return data


def clear_sidecar_cache() -> None:
    _SIDECAR_CACHE.clear()
