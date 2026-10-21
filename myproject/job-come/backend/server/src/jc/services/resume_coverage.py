"""Did the written resume keep everything the career actually contains?

The failure this catches
------------------------
Users report the same complaint in two different ways: "内容太少了" and "跟工作经历极度
不匹配". Both are the same defect — the draft is thinner than the source profile. It has
three causes, and a prompt rule fixes none of them reliably:

1. The model merges two unrelated highlights into one bullet to "tighten" the document.
2. The model drops a highlight it judges weak — usually the ones with no number, which
   are exactly the ones the user could have supplied a number for.
3. The model omits `project_blocks` entirely, silently deleting 项目经历.

The writer prompt forbids all three. Prompts are not enforcement: a long profile, a
retry, or a model swap re-introduces the behaviour, and nobody notices because a thin
resume and a thin career look identical on the page.

So this module measures it. For every source highlight, it asks whether *some* bullet in
the draft still carries that content, matched by character overlap rather than equality
(the whole point of the writer is that the wording changes). What it produces is a
coverage ratio and the specific list of dropped items — which the UI can show as
"你有 23 条经历要点，简历里只出现了 14 条" with the missing ones named.

Deliberately not a gate
-----------------------
Dropping content is sometimes right: two highlights describing the same work *should*
merge, and the user may have asked for a one-pager. So this never blocks export. It is
reported, with the dropped text shown, so the decision stays with the person whose
career it is.

Matching is character-bigram overlap, not embeddings: no model call, no latency, stable
across runs, and transparent enough that a surprising result can be explained by reading
the two strings. The metric itself lives in `text_overlap`, shared with the addition-side
checks in `writing_invariants`; the threshold below stays here because it was calibrated
for *this* question and does not transfer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jc.schemas.profile_payload import ProfilePayload
from jc.services.text_overlap import containment as _containment
from jc.services.text_overlap import excerpt as _excerpt
from jc.services.text_overlap import normalize as _normalize

#: Bigram containment above this counts as "this highlight is still represented".
#: Tuned against real drafts: a rewritten bullet typically retains 0.55–0.9 of the
#: source's bigrams, while two genuinely different bullets from the same role land
#: around 0.2. 0.42 sits in the empty band between those two clusters, so neither
#: ordinary rewriting nor shared company vocabulary moves an item across it.
_MATCH_THRESHOLD = 0.42

#: Below this length a highlight is a label, not content, and bigram overlap is noise.
#: These are reported as covered rather than dropped: flagging `优化流程` as missing
#: sends the user looking for content that was never there.
_MIN_COMPARABLE_CHARS = 6


@dataclass(frozen=True, slots=True)
class DroppedHighlight:
    """A source accomplishment with no recognisable counterpart in the draft."""

    #: Human-readable origin, e.g. `字节跳动 · 后端工程师`.
    where: str
    text: str
    #: `experience` | `project`
    origin: str
    #: Best overlap found, so a near-miss can be told apart from an outright drop.
    best_match: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "where": self.where,
            "text": self.text,
            "origin": self.origin,
            "best_match": round(self.best_match, 2),
        }


@dataclass(frozen=True, slots=True)
class CoverageReport:
    source_highlights: int
    covered: int
    draft_bullets: int
    #: True when the profile has projects but the draft rendered none. This one is
    #: always a defect, never a judgement call.
    projects_missing: bool = False
    dropped: list[DroppedHighlight] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        if self.source_highlights <= 0:
            return 1.0
        return round(self.covered / self.source_highlights, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_highlights": self.source_highlights,
            "covered": self.covered,
            "draft_bullets": self.draft_bullets,
            "ratio": self.ratio,
            "projects_missing": self.projects_missing,
            "dropped": [d.to_dict() for d in self.dropped],
            "notes": list(self.notes),
        }


def _draft_bullets(sections: dict[str, Any]) -> list[str]:
    """Every place in the document a source highlight could legitimately have landed.

    Not just `bullets`. The writer is allowed to fold a fact upward -- a team size or a
    system scope belongs in the role's `scope_line` (先总后分) rather than spent as one
    of the lead bullets, and the summary may carry the headline number. Counting only
    bullets reported those as dropped, so the panel told users content was missing while
    it was sitting one line above the bullets they were reading.
    """
    out: list[str] = []
    summary = sections.get("summary")
    if isinstance(summary, str) and summary.strip():
        out.append(summary)
    for key in ("experience_blocks", "project_blocks"):
        for block in sections.get(key) or []:
            if not isinstance(block, dict):
                continue
            # The project one-liner carries content too, so a project summarised into
            # `description` must not be reported as a dropped highlight.
            for field_name in ("description", "scope_line"):
                value = block.get(field_name)
                if isinstance(value, str) and value.strip():
                    out.append(value)
            for bullet in block.get("bullets") or []:
                if isinstance(bullet, str) and bullet.strip():
                    out.append(bullet)
    return out


def _source_items(profile: ProfilePayload) -> list[tuple[str, str, str]]:
    """(where, text, origin) for every accomplishment the user confirmed."""
    items: list[tuple[str, str, str]] = []
    for exp in profile.experiences:
        where = f"{exp.company} · {exp.title}".strip(" ·") or "工作经历"
        for raw in exp.highlights or []:
            if str(raw).strip():
                items.append((where, str(raw).strip(), "experience"))
    for proj in profile.projects:
        where = proj.name or "项目经历"
        for raw in proj.highlights or []:
            if str(raw).strip():
                items.append((where, str(raw).strip(), "project"))
        if not (proj.highlights or []) and proj.description:
            items.append((where, str(proj.description).strip(), "project"))
    return items


def audit_coverage(
    sections: dict[str, Any],
    profile: ProfilePayload | None,
) -> CoverageReport:
    """Compare a written draft against the confirmed profile it came from.

    Bilingual drafts are audited on their 中文 track: the English track is a translation
    of the same facts, so auditing both would double-count every drop, and the Chinese
    source text is what the overlap metric is calibrated against.
    """
    if sections.get("track") == "bilingual":
        sections = sections.get("zh_sections") or {}

    bullets = _draft_bullets(sections)
    if profile is None:
        return CoverageReport(source_highlights=0, covered=0, draft_bullets=len(bullets))

    items = _source_items(profile)
    dropped: list[DroppedHighlight] = []
    covered = 0
    for where, text, origin in items:
        if len(_normalize(text)) < _MIN_COMPARABLE_CHARS:
            covered += 1
            continue
        best = max((_containment(text, b) for b in bullets), default=0.0)
        if best >= _MATCH_THRESHOLD:
            covered += 1
        else:
            dropped.append(
                DroppedHighlight(where=where, text=text, origin=origin, best_match=best)
            )

    projects_missing = bool(profile.projects) and not (sections.get("project_blocks") or [])

    notes: list[str] = []
    if projects_missing:
        notes.append(
            f"档案里有 {len(profile.projects)} 个项目，但简历里没有项目经历这一节。"
            "这通常是生成异常，建议重新生成优化稿。"
        )
    if dropped:
        shown = "；".join(f"「{_excerpt(d.text)}」" for d in dropped[:3])
        more = f"，另有 {len(dropped) - 3} 条" if len(dropped) > 3 else ""
        notes.append(
            f"你档案里这 {len(dropped)} 条经历没有写进这份简历：{shown}{more}。"
            "如果其中有你想让面试官看到的内容，重新生成一次，或在档案里把它排到更前面；"
            "如果只是和别的要点说的是同一件事，可以不管。"
        )
    return CoverageReport(
        source_highlights=len(items),
        covered=covered,
        draft_bullets=len(bullets),
        projects_missing=projects_missing,
        dropped=dropped,
        notes=notes,
    )
