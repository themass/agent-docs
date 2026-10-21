"""Deterministic screening diagnostics for a finished draft.

What this answers for the user
------------------------------
"Will this get past the screen?" The reviewer already answers "is this honest". Nothing
answered the two mechanical questions that actually decide whether a resume is read:

1. **Keyword coverage.** Which of the target job's own terms never appear in the
   document. A human recruiter and a keyword filter both scan for these, and a resume can
   describe exactly the right work in words the JD does not use.
2. **Reading budget.** How long the document is, and how much of the strongest experience
   falls inside the first page. A recruiter's first pass is short; an achievement on page
   three may as well not exist.

Both are computed from the draft, with no model call, so they cannot invent a problem or
flatter the user. Everything here is advisory: it never blocks export, because a long
resume is a judgement call and a missing keyword may simply be a skill the user lacks —
in which case adding it would be a lie, not a fix.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Characters per A4 page, measured by rendering our own templates at increasing length
# and recording where Chromium actually broke the page (multi-role layout, whitespace
# stripped before counting). The first page holds less than later ones because of the
# header and summary block, so first-page and steady-state are tracked separately —
# a single average mislabels a genuine two-pager as 1.6 pages.
#
#   zh-one-page:  page 2 starts at ~1226 chars, page 3 at ~2778  → 1st ~1200, then ~1550
#   en-two-page:  page 2 starts at ~1997 chars, page 3 at ~4117  → 1st ~1950, then ~2120
#
# Re-measure with scripts/calibrate_resume_pages.py after changing template typography.
_PAGE_BUDGET = {
    "cjk": (1200, 1550),
    "latin": (1950, 2120),
}

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _is_cjk_heavy(text: str) -> bool:
    cjk = len(_CJK_RE.findall(text))
    return cjk * 2 > max(len(text), 1)


def _normalize(text: str) -> str:
    return re.sub(r"[\s\u3000]+", "", text).lower()


def _estimate_pages(total_chars: int, first_page: int, later_page: int) -> float:
    """Pages this much text occupies, charging the header-bearing first page separately.

    Floored at 0.1 so a near-empty draft reads as "约 0.1 页" rather than "约 0 页",
    which looks like a failed measurement instead of a very short document.
    """
    if total_chars <= first_page:
        return max(round(max(total_chars, 1) / first_page, 1), 0.1)
    overflow = total_chars - first_page
    return round(1 + overflow / later_page, 1)


@dataclass(frozen=True, slots=True)
class KeywordHit:
    keyword: str
    present: bool
    #: Where it was found, so the UI can say "only in 技能, not in any bullet".
    locations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResumeDiagnostics:
    estimated_pages: float
    total_chars: int
    bullet_count: int
    longest_bullet_chars: int
    keyword_hits: list[KeywordHit] = field(default_factory=list)
    #: Keywords absent from the whole document.
    missing_keywords: list[str] = field(default_factory=list)
    #: Present, but only in the skills line — a claim with no story behind it.
    skills_only_keywords: list[str] = field(default_factory=list)
    #: Advisory messages, already phrased for the user.
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimated_pages": self.estimated_pages,
            "total_chars": self.total_chars,
            "bullet_count": self.bullet_count,
            "longest_bullet_chars": self.longest_bullet_chars,
            "keyword_coverage": {
                "total": len(self.keyword_hits),
                "present": sum(1 for h in self.keyword_hits if h.present),
                "missing": list(self.missing_keywords),
                "skills_only": list(self.skills_only_keywords),
            },
            "notes": list(self.notes),
        }


def _collect(sections: dict[str, Any]) -> tuple[str, list[str], str]:
    """Return (all text, bullets, skills text) for one monolingual draft."""
    parts: list[str] = []
    bullets: list[str] = []

    header = sections.get("header") or {}
    if isinstance(header, dict):
        parts.extend(str(v) for v in header.values() if v)
    if sections.get("summary"):
        parts.append(str(sections["summary"]))

    for key in ("experience_blocks", "project_blocks", "education_blocks"):
        for block in sections.get(key) or []:
            if not isinstance(block, dict):
                continue
            for field_name, value in block.items():
                if field_name == "bullets" and isinstance(value, list):
                    block_bullets = [str(b) for b in value if b]
                    bullets.extend(block_bullets)
                    parts.extend(block_bullets)
                elif value and not isinstance(value, (list, dict)):
                    parts.append(str(value))

    skills = str((sections.get("skills_block") or {}).get("content") or "")
    if skills:
        parts.append(skills)

    return "\n".join(parts), bullets, skills


def diagnose(
    sections: dict[str, Any],
    *,
    job_keywords: list[str] | None = None,
) -> ResumeDiagnostics:
    """Measure screening readiness for a draft. Bilingual drafts use their 中文 track."""
    if sections.get("track") == "bilingual":
        sections = sections.get("zh_sections") or {}

    text, bullets, skills = _collect(sections)
    normalized = _normalize(text)
    normalized_skills = _normalize(skills)
    normalized_bullets = _normalize("\n".join(bullets))

    first_page, later_page = _PAGE_BUDGET["cjk" if _is_cjk_heavy(text) else "latin"]
    total_chars = len(_normalize(text))
    estimated_pages = _estimate_pages(total_chars, first_page, later_page)

    hits: list[KeywordHit] = []
    missing: list[str] = []
    skills_only: list[str] = []
    seen: set[str] = set()
    for raw in job_keywords or []:
        keyword = str(raw).strip()
        key = _normalize(keyword)
        if len(key) < 2 or key in seen:
            continue
        seen.add(key)
        locations: list[str] = []
        if key in normalized_bullets:
            locations.append("bullets")
        if key in normalized_skills:
            locations.append("skills")
        present = key in normalized
        hits.append(KeywordHit(keyword=keyword, present=present, locations=tuple(locations)))
        if not present:
            missing.append(keyword)
        elif locations == ["skills"]:
            skills_only.append(keyword)

    longest = max((len(b) for b in bullets), default=0)

    notes: list[str] = []
    if estimated_pages > 2.2:
        notes.append(
            f"篇幅约 {estimated_pages} 页。招聘方首轮通常只扫第一页，"
            "把最强的一段经历和最有力的要点放到最前面。"
        )
    elif estimated_pages < 0.6 and bullets:
        notes.append(
            f"篇幅约 {estimated_pages} 页，偏薄。对照左侧待补充项把成果写进要点，"
            "比留白更能说明你做过什么。"
        )
    if longest > 160:
        notes.append(
            f"最长的一条要点有 {longest} 字，一眼读不完。拆成两条，每条只讲一件事。"
        )
    if missing:
        notes.append(
            "这些岗位用词在简历里没出现："
            + "、".join(missing[:8])
            + "。如果你确实做过，换成岗位的说法；没做过就不要加。"
        )
    if skills_only:
        notes.append(
            "这些词只出现在技能里，没有任何经历佐证："
            + "、".join(skills_only[:8])
            + "。只写在技能栏的技能在面试中最容易被追问。"
        )

    return ResumeDiagnostics(
        estimated_pages=estimated_pages,
        total_chars=total_chars,
        bullet_count=len(bullets),
        longest_bullet_chars=longest,
        keyword_hits=hits,
        missing_keywords=missing,
        skills_only_keywords=skills_only,
        notes=notes,
    )
