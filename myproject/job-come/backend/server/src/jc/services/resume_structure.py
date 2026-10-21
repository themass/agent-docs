"""Document-level composition: the layer above the bullet.

The gap this closes
-------------------
Every writing mechanism JC had before this module operated on **one bullet at a time**:
`elevation_techniques` classifies a sentence rewrite, `evidence_gaps` asks about a
sentence, `writing_invariants` attributes a sentence. The user's complaint was exact and
correct — "只是简单地把每条描述优化了一下，没有根本性提升，比如布局、整体结构、先总后分、
结论先行". All true: the pipeline had no representation of the document as a document.

A resume is read in a fixed way, and the decisions that matter most are above the
sentence:

1. **结论先行 (conclusion first).** The摘要 states the positioning, then the single
   strongest piece of evidence, then the direction. A recruiter who reads only three
   lines must already know what this person is.
2. **先总后分 (whole before parts).** Each role opens with one line of 角色与范围 — what
   the person owned and how big it was — and only then lists accomplishments. Without it
   the reader has to infer scope from the bullets, which is work they will not do.
3. **项目叙事完整.** Preserve source paragraph order. A project's background,
   implementation and outcome are not independent items to rank by metric strength.
4. **节序由内容决定.** The playbook's `section_priority` is a per-audience default, not
   a fact about this document. A candidate whose projects carry the evidence and whose
   employment history is thin should not be rendered experience-first.

Why deterministic
-----------------
Structure checks measure evidence without inferring semantic paragraph boundaries from
punctuation or scores. This module may change section order, never paragraph order or
resume wording. Fact generation stays exactly where it was.

Strength scoring, and what it is not
------------------------------------
`score_bullet` is a *proxy for how much evidence a sentence carries*, not a quality
judgement. It rewards the things the methodology defines as evidence (a metric, a stated
outcome, an ownership verb the source supports, a concrete object, JD vocabulary) and
penalises the things it defines as noise (a bare label, a weak lead verb). Ties keep
source order, so a block whose bullets are equally strong is left exactly as written —
reordering without a reason is churn the user cannot explain to themselves.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from jc.domain.role_families import RolePlaybook, get_playbook

#: Sections the renderer knows how to draw. Anything else in a model-supplied
#: `section_order` is ignored rather than trusted.
KNOWN_SECTIONS: tuple[str, ...] = ("summary", "experience", "projects", "education", "skills")

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

_METRIC_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|％|倍|万|千|亿|k|K|w|W|m|M|x|X"
    r"|个|条|名|人|家|次|套|款|端|轮|业务线|业务方|团队)?"
    r"|\b(?:qps|tps|p99|p95|sla|dau|mau|arr|roi|nps|gmv)\b",
    re.IGNORECASE,
)

_CALENDAR_RE = re.compile(r"(?:19|20)\d{2}\s*[-–年]")

_OUTCOME_MARKERS = (
    "提升", "降低", "缩短", "下降", "增长", "节省", "减少", "支撑", "达成", "收敛",
    "解决", "覆盖", "实现", "压缩", "改为", "优化到", "避免", "拿到", "中标", "续约",
    "resulting in", "reduced", "increased", "improved", "achieved", "enabled",
    "saving", "grew", "cut ",
)

_OWNERSHIP_VERBS = (
    "主导", "牵头", "负责", "搭建", "设计并实现", "从 0 到 1", "从0到1", "独立负责",
    "owned", "led", "architected", "built", "launched", "drove", "spearheaded",
)

_WEAK_VERBS = (
    "参与", "协助", "配合", "参加", "跟进", "了解", "熟悉", "接触",
    "involved in", "helped with", "assisted", "supported", "contributed to",
)

_OBJECT_HINT_RE = re.compile(
    r"[A-Za-z][A-Za-z0-9+.#/-]{1,}"
    r"|[\u4e00-\u9fff]{2}(?:系统|平台|服务|链路|模块|流程|集群|网关|中心|引擎|体系|方案)"
)

#: Below this a bullet is a bare label (`优化流程`) carrying no describable content.
_THIN_CHARS = 12
#: Above this a bullet stops being scannable and starts being a paragraph.
_LONG_CHARS = 150

#: A section only overtakes the playbook default when it is clearly stronger. Content-aware
#: ordering that fires on noise would make the same profile render differently run to run,
#: which reads as instability rather than as a decision.
_PROMOTION_MARGIN = 1.5


def _is_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(n.lower() in low for n in needles)


def _metric_count(text: str) -> int:
    """Numbers that are claims, not calendar years."""
    stripped = _CALENDAR_RE.sub(" ", text)
    return sum(1 for m in _METRIC_RE.findall(stripped) if m.strip())


def _has_object(text: str, playbook: RolePlaybook) -> bool:
    if _OBJECT_HINT_RE.search(text):
        return True
    low = text.lower()
    return any(noun.lower() in low for noun in playbook.object_nouns if noun)


@dataclass(frozen=True, slots=True)
class BulletStrength:
    """How much evidence one sentence carries, and why."""

    score: float
    reasons: tuple[str, ...]

    @property
    def is_lead_worthy(self) -> bool:
        """Strong enough to be the first thing a reader sees for this role."""
        return self.score >= 4.0


def score_bullet(
    text: str,
    *,
    playbook: RolePlaybook,
    job_keywords: tuple[str, ...] = (),
) -> BulletStrength:
    """Evidence weight of one bullet. Higher sorts earlier within its block."""
    body = (text or "").strip()
    if not body:
        return BulletStrength(score=0.0, reasons=())

    score = 0.0
    reasons: list[str] = []

    metrics = _metric_count(body)
    if metrics:
        score += 3.0 if metrics == 1 else 3.5
        reasons.append("带量化")

    if _has_any(body, _OUTCOME_MARKERS):
        score += 2.0
        reasons.append("有结果")
    elif playbook.quantification_optional:
        # Roles whose results are qualitative must not be sorted below roles' noise just
        # because no outcome verb fired. A precise bullet is a complete bullet here.
        score += 0.5

    if _has_any(body, _OWNERSHIP_VERBS):
        score += 2.0
        reasons.append("主导性强")
    if _has_any(body, _WEAK_VERBS):
        score -= 1.5
        reasons.append("动词偏弱")

    if _has_object(body, playbook):
        score += 1.0
        reasons.append("对象具体")

    hits = 0
    for kw in job_keywords:
        token = kw.strip().lower()
        if len(token) >= 2 and token in body.lower():
            hits += 1
        if hits >= 2:
            break
    if hits:
        score += hits * 0.75
        reasons.append("命中岗位关键词")

    length = len(body)
    if length < _THIN_CHARS:
        score -= 2.0
        reasons.append("内容过短")
    elif length > _LONG_CHARS:
        score -= 1.0
        reasons.append("过长")
    elif _is_cjk(body) and 40 <= length <= 120:
        score += 0.5

    return BulletStrength(score=round(score, 2), reasons=tuple(reasons))


@dataclass(frozen=True, slots=True)
class BulletMove:
    """One bullet that the structure pass promoted or demoted inside its block."""

    field_path: str
    where: str
    text: str
    from_index: int
    to_index: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_path": self.field_path,
            "where": self.where,
            "text": self.text,
            "from_index": self.from_index,
            "to_index": self.to_index,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class StructureIssue:
    """A document-level defect. Advisory: never blocks export."""

    code: str
    field_path: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "field_path": self.field_path, "message": self.message}


@dataclass(frozen=True, slots=True)
class SummaryShape:
    """Whether the摘要 actually reads conclusion-first."""

    present: bool
    positioning: bool
    evidence: bool
    direction: bool

    @property
    def conclusion_first(self) -> bool:
        return self.present and self.positioning and self.evidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "present": self.present,
            "positioning": self.positioning,
            "evidence": self.evidence,
            "direction": self.direction,
            "conclusion_first": self.conclusion_first,
        }


@dataclass(frozen=True, slots=True)
class StructureReport:
    """What the composition pass did to this document, and what it could not fix."""

    section_order: list[str]
    section_order_changed: bool
    section_order_reason: str | None
    moves: list[BulletMove] = field(default_factory=list)
    scope_lines: int = 0
    blocks_total: int = 0
    summary_shape: SummaryShape | None = None
    issues: list[StructureIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_order": list(self.section_order),
            "section_order_changed": self.section_order_changed,
            "section_order_reason": self.section_order_reason,
            "moves": [m.to_dict() for m in self.moves],
            "scope_lines": self.scope_lines,
            "blocks_total": self.blocks_total,
            "summary_shape": self.summary_shape.to_dict() if self.summary_shape else None,
            "issues": [i.to_dict() for i in self.issues],
        }


_DIRECTION_MARKERS = (
    "希望", "目标", "寻求", "期望", "方向", "专注", "面向", "seeking", "targeting",
    "focused on",
)


def analyze_summary(summary: str | None, *, headline: str | None = None) -> SummaryShape:
    """Does the摘要 state a position, prove it, and say where the person is going.

    This is the one place "结论先行" is checkable without a model: a summary that opens
    with a role statement and carries a number or a named outcome has front-loaded the
    conclusion; one that opens with 本人 or lists duties has not.
    """
    text = (summary or "").strip()
    if not text:
        return SummaryShape(present=False, positioning=False, evidence=False, direction=False)

    head = text[:60]
    positioning = bool(
        re.search(r"(年|years?)", head)
        or (headline and headline.strip() and headline.strip()[:6] in head)
        or re.search(r"(工程师|专家|经理|负责人|总监|设计师|运营|分析师|顾问|架构师|主管)", head)
    )
    evidence = bool(_metric_count(text)) or _has_any(text, _OUTCOME_MARKERS)
    direction = _has_any(text, _DIRECTION_MARKERS)
    return SummaryShape(
        present=True, positioning=positioning, evidence=evidence, direction=direction
    )


def _block_label(key: str, idx: int, block: dict[str, Any]) -> str:
    if key == "project_blocks":
        return str(block.get("name") or f"第 {idx + 1} 个项目")
    company = str(block.get("company") or "").strip()
    title = str(block.get("title") or "").strip()
    return f"{company} · {title}".strip(" ·") or f"第 {idx + 1} 段经历"


def _section_weight(
    sections: dict[str, Any],
    key: str,
    *,
    playbook: RolePlaybook,
    job_keywords: tuple[str, ...],
) -> float:
    """Average evidence weight of a section's strongest bullets.

    Averaged over the top three rather than all: a section is read from the top, and a
    long tail of weak bullets should not disqualify a section that opens strongly.
    """
    scores: list[float] = []
    for block in sections.get(key) or []:
        if not isinstance(block, dict):
            continue
        for bullet in block.get("bullets") or []:
            if isinstance(bullet, str) and bullet.strip():
                scores.append(
                    score_bullet(bullet, playbook=playbook, job_keywords=job_keywords).score
                )
    if not scores:
        return 0.0
    top = sorted(scores, reverse=True)[:3]
    return round(sum(top) / len(top), 2)


def resolve_section_order(
    sections: dict[str, Any],
    *,
    playbook: RolePlaybook,
    job_keywords: tuple[str, ...] = (),
) -> tuple[list[str], str | None]:
    """Reading order for this document, starting from the role default.

    The playbook says what this audience reads first; content decides whether that
    default misreads *this* candidate. The only swap allowed is 项目经历 ahead of
    工作经历, because that is the one case where the default is routinely wrong — a
    candidate whose evidence lives in projects (early career, contractor, platform work
    under one employer) gets read experience-first and looks thin.
    """
    base = [k for k in playbook.section_priority if k in KNOWN_SECTIONS]
    for key in KNOWN_SECTIONS:
        if key not in base:
            base.append(key)

    exp_w = _section_weight(
        sections, "experience_blocks", playbook=playbook, job_keywords=job_keywords
    )
    proj_w = _section_weight(
        sections, "project_blocks", playbook=playbook, job_keywords=job_keywords
    )
    if not (sections.get("project_blocks") or []):
        return base, None

    try:
        exp_at, proj_at = base.index("experience"), base.index("projects")
    except ValueError:
        return base, None

    if proj_at > exp_at and proj_w >= exp_w + _PROMOTION_MARGIN:
        reordered = [k for k in base if k != "projects"]
        reordered.insert(reordered.index("experience"), "projects")
        return (
            reordered,
            f"项目经历的证据强度（{proj_w}）明显高于工作经历（{exp_w}），把项目提到前面读。",
        )
    return base, None


def compose_document(
    sections: dict[str, Any],
    *,
    role_family: str | None = None,
    job_keywords: list[str] | None = None,
    apply_changes: bool = True,
) -> StructureReport:
    """Impose document-level structure on a generated draft, and report what changed.

    Mutates only `section_order` when `apply_changes` is true. Source paragraph
    order is preserved, including a project's background/action/outcome. No sentence is
    edited, no block is dropped, no fact is added. With `apply_changes=False` this is a
    pure audit, which is how the export-time check uses it.
    """
    playbook = get_playbook(role_family or sections.get("role_family"))
    keywords = tuple(job_keywords or ())

    moves: list[BulletMove] = []
    issues: list[StructureIssue] = []
    scope_lines = 0
    blocks_total = 0

    for key in ("experience_blocks", "project_blocks"):
        for idx, block in enumerate(sections.get(key) or []):
            if not isinstance(block, dict):
                continue
            blocks_total += 1
            scope = block.get("scope_line")
            if isinstance(scope, str) and scope.strip():
                scope_lines += 1
            elif key == "experience_blocks":
                issues.append(
                    StructureIssue(
                        code="missing_scope_line",
                        field_path=f"{key}[{idx}].scope_line",
                        message=(
                            f"「{_block_label(key, idx, block)}」没有一句话说明角色与范围。"
                            "读者要从要点里自己拼出你管了多大的事，这一步大多数人不会做。"
                        ),
                    )
                )
            # No automatic bullet-level sorting: a block can be one project's
            # background -> implementation -> result narrative. Evidence scores
            # cannot determine whether those sentences are independent.
            bullets = [b for b in (block.get("bullets") or []) if isinstance(b, str)]
            if bullets:
                lead = score_bullet(bullets[0], playbook=playbook, job_keywords=keywords)
                if not lead.is_lead_worthy:
                    issues.append(
                        StructureIssue(
                            code="weak_lead_bullet",
                            field_path=f"{key}[{idx}].bullets[0]",
                            message=(
                                f"「{_block_label(key, idx, block)}」的第一条还不够有力。"
                                "可在保留项目背景、行动与成果关系的前提下突出成果，不要拆散或机械重排。"
                            ),
                        )
                    )

    order, reason = resolve_section_order(sections, playbook=playbook, job_keywords=keywords)
    if apply_changes:
        sections["section_order"] = order

    shape = analyze_summary(
        sections.get("summary"), headline=(sections.get("header") or {}).get("headline")
    )
    if not shape.present:
        issues.append(
            StructureIssue(
                code="missing_summary",
                field_path="summary",
                message="没有个人摘要。招聘方读的前三行决定要不要继续，这三行不该留空。",
            )
        )
    elif not shape.conclusion_first:
        missing = []
        if not shape.positioning:
            missing.append("你是谁（年限 + 定位）")
        if not shape.evidence:
            missing.append("一条最硬的证据")
        issues.append(
            StructureIssue(
                code="summary_not_conclusion_first",
                field_path="summary",
                message="摘要没有结论先行，缺少：" + "、".join(missing) + "。",
            )
        )

    return StructureReport(
        section_order=order,
        # Only a *content-driven* deviation is a change worth telling the user about.
        # Normalising a model's arbitrary order back to the role default is housekeeping;
        # reporting it would train the user to ignore this field.
        section_order_changed=bool(reason),
        section_order_reason=reason,
        moves=moves,
        scope_lines=scope_lines,
        blocks_total=blocks_total,
        summary_shape=shape,
        issues=issues,
    )


def audit_structure(
    sections: dict[str, Any],
    *,
    role_family: str | None = None,
    job_keywords: list[str] | None = None,
) -> StructureReport:
    """Read-only structural audit, for drafts that are already composed."""
    if sections.get("track") == "bilingual":
        sections = sections.get("zh_sections") or {}
    return compose_document(
        dict(sections),
        role_family=role_family,
        job_keywords=job_keywords,
        apply_changes=False,
    )
