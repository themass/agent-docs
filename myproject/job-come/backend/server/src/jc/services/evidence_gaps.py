"""Find the bullets that are selling the user short, and ask for the missing evidence.

The product problem
-------------------
Users want their resume to look impressive enough to pass a screen. The tempting way to
deliver that is to let the model embellish. That trade is bad for the user: an invented
metric survives the screen and then collapses in the interview, where the cost lands
entirely on them — and a resume that cannot be defended is worse than one that is plain.

There is a better lever, and it is the one real resume coaches use. Most weak resumes are
not weak because the career was weak; they are weak because **the strongest evidence was
never written down**. The user knows the number. It was simply never asked for.

So instead of fabricating an outcome, this module locates every bullet that *should* carry
an outcome for this role family and does not, and turns each into a specific question the
user can answer from memory in seconds. Answers go back into the profile as real facts,
and the writer then has genuine material to work with.

This is deliberately deterministic: no model call, no latency, and the questions cannot
drift into asking for things the role does not care about.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from jc.domain.role_families import RolePlaybook, playbook_for_title
from jc.schemas.profile_payload import ProfilePayload

# A bullet already carrying a number or an explicit scale needs no prompting.
_METRIC_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|％|倍|万|千|亿|k|K|w|W|m|M|x|X)?"
    r"|\b(?:qps|tps|p99|p95|sla|dau|mau|arr|roi|nps|gmv)\b",
    re.IGNORECASE,
)

_OUTCOME_MARKERS = (
    "提升", "降低", "缩短", "下降", "增长", "节省", "减少", "支撑", "达成", "收敛",
    "解决", "覆盖", "实现", "改为", "优化到",
)

_WEAK_VERBS = ("参与", "协助", "配合", "了解", "熟悉", "接触", "跟进", "支持")

_VAGUE_QUANTIFIERS = ("多项", "若干", "多个", "一些", "大量", "众多", "部分")

#: Below this many characters a bullet is a bare label with no describable content at all
#: (`优化流程`). Kept deliberately low: a bullet that is merely missing an outcome gets the
#: more useful `missing_outcome` question instead of a generic "write more" nudge.
_THIN_BULLET_CHARS = 10


@dataclass(frozen=True, slots=True)
class EvidenceGap:
    """One concrete question whose answer would measurably strengthen the resume."""

    field_path: str
    kind: str
    source_text: str
    question: str
    #: Role-appropriate examples of what a valid answer looks like. Never pre-filled.
    examples: tuple[str, ...]
    #: Higher means a bigger expected gain. Drives ordering in the UI.
    weight: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_path": self.field_path,
            "kind": self.kind,
            "source_text": self.source_text,
            "question": self.question,
            "examples": list(self.examples),
            "weight": self.weight,
        }


def _has_metric(text: str) -> bool:
    return bool(_METRIC_RE.search(text))


def _has_outcome(text: str) -> bool:
    return any(m in text for m in _OUTCOME_MARKERS)


def _leads_with_weak_verb(text: str) -> bool:
    head = text.strip()[:6]
    return any(head.startswith(v) for v in _WEAK_VERBS)


def _vague_quantifier(text: str) -> str | None:
    for q in _VAGUE_QUANTIFIERS:
        if q in text:
            return q
    return None


def _bullet_gaps(
    *,
    field_path: str,
    text: str,
    where: str,
    playbook: RolePlaybook,
    recent: bool,
) -> list[EvidenceGap]:
    """Gaps for one bullet. At most one question per bullet, strongest reason first."""
    body = text.strip()
    if not body:
        return []
    examples = playbook.outcome_metrics[:4]
    # Recent roles are read most closely, so a gap there costs more.
    base = 3 if recent else 2

    vague = _vague_quantifier(body)
    if vague and not _has_metric(body):
        return [
            EvidenceGap(
                field_path=field_path,
                kind="vague_quantity",
                source_text=body,
                question=f"「{where}」这条写了「{vague}」——具体是多少？换成真实数字会明显更有说服力。",
                examples=examples,
                weight=base + 2,
            )
        ]

    if _leads_with_weak_verb(body):
        return [
            EvidenceGap(
                field_path=field_path,
                kind="weak_ownership",
                source_text=body,
                question=(
                    f"「{where}」这条以「{body[:2]}」开头。你在这件事里实际负责到哪一步"
                    "（独立负责 / 带人做 / 配合他人）？我们只会按你说的程度写。"
                ),
                examples=("独立负责整个方案", "带 3 人完成", "配合主负责人执行"),
                weight=base + 1,
            )
        ]

    if len(body) < _THIN_BULLET_CHARS:
        return [
            EvidenceGap(
                field_path=field_path,
                kind="thin_bullet",
                source_text=body,
                question=(
                    f"「{where}」这条只有几个字，读者看不出对象和结果。"
                    "具体是对什么做的，带来了什么变化？"
                ),
                examples=examples,
                weight=base + 1,
            )
        ]

    if not _has_metric(body) and not _has_outcome(body):
        # For roles whose results are often non-numeric, ask for the outcome in that
        # role's own terms instead of demanding a metric that may not exist.
        if playbook.quantification_optional:
            question = (
                f"「{where}」这条只写了做什么，没写带来什么。这件事最终解决了什么问题"
                "、避免了什么风险，或支撑了什么决策？没有数字也没关系。"
            )
        else:
            question = (
                f"「{where}」这条缺少结果。这件事带来的变化能用一个数字说明吗"
                f"（{'、'.join(examples[:3])} 之类）？"
            )
        return [
            EvidenceGap(
                field_path=field_path,
                kind="missing_outcome",
                source_text=body,
                question=question,
                examples=examples,
                weight=base,
            )
        ]

    if not _has_metric(body) and not playbook.quantification_optional:
        return [
            EvidenceGap(
                field_path=field_path,
                kind="unquantified_outcome",
                source_text=body,
                question=f"「{where}」写了结果但没有量级。大概是多少（{'、'.join(examples[:3])}）？",
                examples=examples,
                weight=base - 1,
            )
        ]

    return []


def find_evidence_gaps(
    profile: ProfilePayload,
    *,
    job_title: str | None = None,
    role_family: str | None = None,
    limit: int = 12,
) -> list[EvidenceGap]:
    """Rank the questions whose answers would most strengthen this specific resume."""
    from jc.domain.role_families import get_playbook

    playbook = (
        get_playbook(role_family)
        if role_family
        else playbook_for_title(
            job_title,
            profile.experiences[0].title if profile.experiences else None,
        )
    )

    gaps: list[EvidenceGap] = []

    for e_idx, exp in enumerate(profile.experiences):
        where = f"{exp.company} · {exp.title}".strip(" ·") or f"第 {e_idx + 1} 段经历"
        recent = e_idx == 0
        if not (exp.highlights or []):
            gaps.append(
                EvidenceGap(
                    field_path=f"experiences[{e_idx}]",
                    kind="empty_experience",
                    source_text=where,
                    question=f"「{where}」这段还没有任何要点。这段时间你主要负责什么、做出了什么？",
                    examples=playbook.outcome_metrics[:4],
                    weight=9 if recent else 7,
                )
            )
            continue
        for b_idx, raw in enumerate(exp.highlights):
            gaps.extend(
                _bullet_gaps(
                    field_path=f"experiences[{e_idx}].highlights[{b_idx}]",
                    text=raw,
                    where=where,
                    playbook=playbook,
                    recent=recent,
                )
            )

    for p_idx, proj in enumerate(profile.projects):
        where = proj.name or f"第 {p_idx + 1} 个项目"
        bullets = proj.highlights or ([proj.description] if proj.description else [])
        if not bullets:
            gaps.append(
                EvidenceGap(
                    field_path=f"projects[{p_idx}]",
                    kind="empty_project",
                    source_text=where,
                    question=f"项目「{where}」只有名字。你在其中承担什么角色，做出了什么结果？",
                    examples=playbook.outcome_metrics[:4],
                    weight=6,
                )
            )
            continue
        for b_idx, raw in enumerate(bullets):
            gaps.extend(
                _bullet_gaps(
                    field_path=f"projects[{p_idx}].highlights[{b_idx}]",
                    text=str(raw),
                    where=where,
                    playbook=playbook,
                    recent=False,
                )
            )

    for requirement in playbook.must_haves:
        links = " ".join(link.url or "" for link in profile.contact.links)
        if "作品集" in requirement and not links:
            gaps.append(
                EvidenceGap(
                    field_path="contact.links",
                    kind="missing_must_have",
                    source_text=requirement,
                    question="这个岗位的简历通常必须带作品集链接。你有可公开的作品集或代表作地址吗？",
                    examples=("个人网站", "Behance / Dribbble", "可访问的作品 PDF 链接"),
                    weight=10,
                )
            )

    gaps.sort(key=lambda g: -g.weight)
    return gaps[:limit]


def gaps_payload(gaps: list[EvidenceGap], *, playbook: RolePlaybook) -> dict[str, Any]:
    return {
        "role_family": playbook.id,
        "role_label": playbook.label,
        "quantification_optional": playbook.quantification_optional,
        "gaps": [g.to_dict() for g in gaps],
    }
