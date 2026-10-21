"""Per-role-family document blueprints: what a strong resume of *this kind* looks like.

The gap this closes
-------------------
`role_families.py` already knew that a backend resume and a legal resume are judged
differently — it carried outcome vocabulary, object nouns and a section priority. But all
of that was consumed inside prompts, so two things were true at once:

1. The user was told "不同岗位有不同的方法论" and could never see what the difference was.
   The only visible trace was one line of hint text and a dropdown label.
2. Nothing checked whether the generated document actually met the family's bar. The
   playbook advised the writer and then nobody verified the advice had been followed.

A blueprint is the same knowledge expressed as a **contract that can be measured**: a
fixed set of requirements, each with a deterministic checker, family-specific thresholds
and copy the user can read. It answers "what does a strong 后端 resume have that mine
does not" with a list, not a paragraph.

Derive, then override
---------------------
Sixteen hand-written blueprints would drift from the sixteen playbooks within a month, so
the blueprint is **derived** from the playbook and only the fields where derivation is
genuinely wrong are overridden in `_SPECS`. A new family therefore works immediately with
sane defaults, and the per-family opinions stay reviewable in one table.

What a blueprint may not do
---------------------------
It is a bar, not a generator. A requirement may say "this family is read for team size
and mandate"; it can never supply a team size. Every check is run against text that is
already in the document, and every failure is phrased as a question for the user or an
instruction for the writer — never as a licence to invent. All findings are advisory:
`resume_service` maps them to `warning`, because a document-shape preference must not be
able to lock someone out of their own resume.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jc.domain.role_families import GENERAL, PLAYBOOKS, RolePlaybook, get_playbook
from jc.services.resume_structure import analyze_summary, score_bullet

#: Bullets the most recent role needs before it reads as a full account of the job.
#: Four is the floor, not the target: below it a recruiter sees a title and a gesture.
_DEFAULT_LEAD_BULLETS = 4
#: Older roles are skimmed, so they need enough to prove the trajectory and no more.
_DEFAULT_TAIL_BULLETS = 2
#: Share of bullets that must carry a result. Roles whose outcomes are qualitative get a
#: lower bar from `quantification_optional`, not an exemption: a bullet with no outcome
#: of any kind is a duty, and a list of duties is a job description, not a resume.
_DEFAULT_OUTCOME_RATIO = 0.6
_SOFT_OUTCOME_RATIO = 0.4


@dataclass(frozen=True, slots=True)
class BlueprintSpec:
    """The parts of a blueprint that derivation from the playbook gets wrong."""

    scope_dimensions: tuple[str, ...] = ()
    summary_evidence: str = ""
    anti_patterns: tuple[str, ...] = ()
    lead_bullets: int = 0
    outcome_ratio: float = 0.0


# Only genuine per-family opinions live here. Anything omitted is derived below.
_SPECS: dict[str, BlueprintSpec] = {
    "backend": BlueprintSpec(
        scope_dimensions=("负责的服务与链路", "流量或数据量级", "团队与协作方规模"),
        summary_evidence="一个最硬的规模或稳定性数字",
        anti_patterns=(
            "只写用到的技术栈，不写扛住了多大的量",
            "把架构决策写成功能清单，看不到取舍",
        ),
    ),
    "frontend": BlueprintSpec(
        scope_dimensions=("负责的产品与页面范围", "用户量级或业务线数", "协作的设计与后端团队"),
        summary_evidence="一个可感知的体验或性能指标",
        anti_patterns=(
            "写「优化了体验」却没有任何可感知指标",
            "基建类工作不写被多少业务复用，影响面消失",
        ),
    ),
    "ios": BlueprintSpec(
        scope_dimensions=("负责的客户端模块", "装机或日活量级", "发版节奏与团队规模"),
        summary_evidence="一个崩溃率、启动耗时或包体积指标",
        anti_patterns=("只写实现了哪些页面，不写质量与性能结果",),
    ),
    "data": BlueprintSpec(
        scope_dimensions=("负责的数据域或模型", "数据与调用量级", "下游使用方"),
        summary_evidence="一个业务指标的提升幅度",
        anti_patterns=(
            "只写模型和指标，不写业务上因此改变了什么",
            "写离线效果不写线上效果，无法判断是否落地",
        ),
    ),
    "devops": BlueprintSpec(
        scope_dimensions=("负责的平台与集群", "承载的服务数与规模", "服务的研发团队数"),
        summary_evidence="一个稳定性、效率或成本数字",
        anti_patterns=("写工具搭建不写接入率，看不出是否真的被用起来",),
    ),
    "pm": BlueprintSpec(
        scope_dimensions=("负责的产品线与阶段", "用户或客户量级", "对接的研发与业务团队"),
        summary_evidence="一个由你推动达成的业务结果",
        anti_patterns=(
            "写需求数量不写业务结果，读起来像需求管理员",
            "不区分你定的方向和团队执行的部分",
        ),
    ),
    "design": BlueprintSpec(
        scope_dimensions=("负责的产品与设计范围", "覆盖的用户与场景", "协作的产品与研发团队"),
        summary_evidence="一个由设计带来的可衡量变化",
        anti_patterns=("只有作品描述没有问题与结果，读者无法判断你的判断力",),
        outcome_ratio=_SOFT_OUTCOME_RATIO,
    ),
    "operations": BlueprintSpec(
        scope_dimensions=("负责的品类或业务板块", "管理的规模与预算", "协作与管理的团队"),
        summary_evidence="一个增长、效率或留存数字",
        anti_patterns=("把日常执行写成列表，看不到你改变了哪个指标",),
    ),
    "marketing": BlueprintSpec(
        scope_dimensions=("负责的品牌或渠道", "预算与投放量级", "覆盖的市场与人群"),
        summary_evidence="一个获客成本或增长数字",
        anti_patterns=("只写做过哪些活动，不写花了多少钱带来了什么",),
    ),
    "sales": BlueprintSpec(
        scope_dimensions=("负责的区域或客户群", "配额与业绩量级", "带领或协作的团队"),
        summary_evidence="一个业绩完成率或签约金额",
        anti_patterns=("不写配额完成率，读者无法判断业绩的分量",),
    ),
    "customer_success": BlueprintSpec(
        scope_dimensions=("负责的客户群与规模", "续约或服务量级", "协作的交付与产品团队"),
        summary_evidence="一个续约率、满意度或交付结果",
        anti_patterns=("写服务流程不写客户结果，看不出你的价值",),
    ),
    "hr": BlueprintSpec(
        scope_dimensions=("支持的业务线与人数", "招聘或组织项目规模", "汇报与协作关系"),
        summary_evidence="一个招聘效率或组织结果",
        anti_patterns=("写事务性工作不写组织结果，读起来像流程执行者",),
        outcome_ratio=_SOFT_OUTCOME_RATIO,
    ),
    "finance": BlueprintSpec(
        scope_dimensions=("负责的业务与科目范围", "管理的资金或预算量级", "协作的业务方"),
        summary_evidence="一个成本、合规或经营分析结果",
        anti_patterns=("只写核算与报表，不写因此支撑了什么决策",),
        outcome_ratio=_SOFT_OUTCOME_RATIO,
    ),
    "legal": BlueprintSpec(
        scope_dimensions=("负责的业务与法域范围", "处理的案件或合同量级", "协作的业务与外部机构"),
        summary_evidence="一个避免的风险或支撑成的交易",
        anti_patterns=("只写合同类型，不写风险与结果，看不出判断力",),
        outcome_ratio=_SOFT_OUTCOME_RATIO,
    ),
    "management": BlueprintSpec(
        scope_dimensions=("带的团队规模与结构", "负责的业务量级与预算", "被授权的决策范围"),
        summary_evidence="一个组织或业务层面的结果",
        anti_patterns=(
            "不区分「我做的」和「团队做的」，会被读成冒领成果",
            "只写管理动作不写组织结果，看不出你带来的差别",
        ),
        lead_bullets=5,
    ),
    GENERAL: BlueprintSpec(
        scope_dimensions=("负责的范围与对象", "涉及的规模", "协作与汇报关系"),
        summary_evidence="一个可以说清的结果",
        anti_patterns=("先写职责再写结果，读者读不到第二行就离开了",),
        outcome_ratio=_SOFT_OUTCOME_RATIO,
    ),
}


@dataclass(frozen=True, slots=True)
class BlueprintRequirement:
    """One measurable property of a strong resume in this family."""

    id: str
    label: str
    #: Why a recruiter in this family cares, in the user's terms.
    why: str
    #: What to do when it is not met. Always an action the user or writer can take.
    fix: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "why": self.why, "fix": self.fix}


@dataclass(frozen=True, slots=True)
class BlueprintFinding:
    """Whether one requirement is met by the document on screen."""

    requirement: BlueprintRequirement
    met: bool
    #: Measured value, rendered for the user ("3/5 条要点带结果").
    detail: str
    field_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.requirement.to_dict(),
            "met": self.met,
            "detail": self.detail,
            "field_path": self.field_path,
        }


@dataclass(frozen=True, slots=True)
class ResumeBlueprint:
    """The bar for one role family, in a form both the writer and the user can read."""

    family: str
    label: str
    section_order: tuple[str, ...]
    #: The three parts of a conclusion-first 摘要, worded for this family.
    summary_formula: tuple[str, ...]
    #: What the 先总后分 scope line must state here.
    scope_dimensions: tuple[str, ...]
    #: Strongest evidence first — what to lead a bullet with in this family.
    evidence_ladder: tuple[str, ...]
    #: How this family's resumes typically fail.
    anti_patterns: tuple[str, ...]
    #: Document requirements a generic reviewer would not know about.
    must_haves: tuple[str, ...]
    lead_bullets: int
    tail_bullets: int
    outcome_ratio: float
    quantification_optional: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "label": self.label,
            "section_order": list(self.section_order),
            "summary_formula": list(self.summary_formula),
            "scope_dimensions": list(self.scope_dimensions),
            "evidence_ladder": list(self.evidence_ladder),
            "anti_patterns": list(self.anti_patterns),
            "must_haves": list(self.must_haves),
            "lead_bullets": self.lead_bullets,
            "tail_bullets": self.tail_bullets,
            "outcome_ratio": self.outcome_ratio,
            "quantification_optional": self.quantification_optional,
        }

    def as_prompt_block(self) -> str:
        """Render the bar for the writer prompt.

        Written as a document contract rather than as advice, because the previous
        playbook block was advice and the model routinely satisfied the sentence-level
        rules while producing a document that met none of these.
        """
        lines = [
            f"Document blueprint for {self.label} (`{self.family}`).",
            "Section order: " + " > ".join(self.section_order),
            "Summary must contain, in this order: " + " → ".join(self.summary_formula),
            "Every experience block opens with a scope line stating: "
            + "、".join(self.scope_dimensions)
            + ". Write it only from what the source supports; omit it if the source "
            "carries none of these.",
            f"Completeness reference: {self.lead_bullets} bullets for the most recent role; "
            f"{self.tail_bullets} for earlier roles. These are advisory, not quotas. "
            "Preserve source paragraph count and project grouping; never split a project "
            "narrative; never invent work to reach a number.",
            f"At least {int(self.outcome_ratio * 100)}% of bullets must end in a result.",
            "Lead bullets with evidence in this order: " + " > ".join(self.evidence_ladder),
        ]
        if self.must_haves:
            lines.append("Incomplete without: " + "、".join(self.must_haves))
        if self.anti_patterns:
            lines.append("How resumes in this family fail:")
            lines.extend(f"- {a}" for a in self.anti_patterns)
        return "\n".join(lines)


def _spec(family: str) -> BlueprintSpec:
    return _SPECS.get(family, _SPECS[GENERAL])


def blueprint_for(family: str | None) -> ResumeBlueprint:
    """The blueprint in force for a family, derived from its playbook."""
    playbook: RolePlaybook = get_playbook(family)
    spec = _spec(playbook.id)
    ratio = spec.outcome_ratio or (
        _SOFT_OUTCOME_RATIO if playbook.quantification_optional else _DEFAULT_OUTCOME_RATIO
    )
    return ResumeBlueprint(
        family=playbook.id,
        label=playbook.label,
        section_order=playbook.section_priority,
        summary_formula=(
            f"你是谁（年限 + {playbook.label}定位）",
            spec.summary_evidence or "一个最硬的结果",
            "下一步要做什么",
        ),
        scope_dimensions=spec.scope_dimensions or _SPECS[GENERAL].scope_dimensions,
        # The playbook's outcome vocabulary *is* the evidence ladder for this family:
        # what counts as a result is what is worth leading with.
        evidence_ladder=playbook.outcome_metrics,
        anti_patterns=spec.anti_patterns or _SPECS[GENERAL].anti_patterns,
        must_haves=playbook.must_haves,
        lead_bullets=spec.lead_bullets or _DEFAULT_LEAD_BULLETS,
        tail_bullets=_DEFAULT_TAIL_BULLETS,
        outcome_ratio=ratio,
        quantification_optional=playbook.quantification_optional,
    )


def all_blueprints() -> list[dict[str, Any]]:
    """Catalogue for the UI, so the user can compare families before choosing one."""
    return [blueprint_for(fid).to_dict() for fid in PLAYBOOKS]


# --- measurement ----------------------------------------------------------------------

#: A bullet counts as carrying a result when the structural scorer saw a metric or an
#: outcome marker in it. Reusing that scorer keeps "有结果" meaning one thing across the
#: blueprint checklist, the bullet ordering and the reviewer notes.
_OUTCOME_REASONS = ("带量化", "有结果")


def _blocks(sections: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [b for b in (sections.get(key) or []) if isinstance(b, dict)]


def _bullets(block: dict[str, Any]) -> list[str]:
    return [b for b in (block.get("bullets") or []) if isinstance(b, str) and b.strip()]


def _requirement_checks(
    blueprint: ResumeBlueprint,
    sections: dict[str, Any],
) -> list[BlueprintFinding]:
    playbook = get_playbook(blueprint.family)
    experience = _blocks(sections, "experience_blocks")
    projects = _blocks(sections, "project_blocks")
    all_blocks = experience + projects
    findings: list[BlueprintFinding] = []

    # 1. 结论先行
    shape = analyze_summary(
        sections.get("summary"), headline=(sections.get("header") or {}).get("headline")
    )
    missing_parts = []
    if not shape.present:
        missing_parts.append("整段缺失")
    else:
        if not shape.positioning:
            missing_parts.append("缺定位")
        if not shape.evidence:
            missing_parts.append("缺硬证据")
    findings.append(
        BlueprintFinding(
            requirement=BlueprintRequirement(
                id="summary_conclusion_first",
                label="摘要结论先行",
                why="招聘方读前三行决定要不要继续，这三行要先给结论再给证据。",
                fix="按「" + " → ".join(blueprint.summary_formula) + "」重写摘要。",
            ),
            met=shape.conclusion_first,
            detail="已结论先行" if shape.conclusion_first else "、".join(missing_parts),
            field_path=None if shape.conclusion_first else "summary",
        )
    )

    # 2. 先总后分
    with_scope = sum(1 for b in all_blocks if str(b.get("scope_line") or "").strip())
    findings.append(
        BlueprintFinding(
            requirement=BlueprintRequirement(
                id="scope_lines",
                label="每段先说范围",
                why=(
                    f"{blueprint.label}的读者先判断量级："
                    + "、".join(blueprint.scope_dimensions)
                    + "。"
                ),
                fix="在「补充信息」里写清这段经历你负责的范围与量级。",
            ),
            met=bool(all_blocks) and with_scope == len(all_blocks),
            detail=f"{with_scope}/{len(all_blocks)} 段有范围句" if all_blocks else "还没有经历",
            field_path=None if with_scope == len(all_blocks) else "experience_blocks",
        )
    )

    # 3. 段内最强在前
    weak_leads = [
        idx
        for idx, block in enumerate(all_blocks)
        if _bullets(block)
        and not score_bullet(_bullets(block)[0], playbook=playbook).is_lead_worthy
    ]
    findings.append(
        BlueprintFinding(
            requirement=BlueprintRequirement(
                id="strong_lead_bullets",
                label="项目成果是否清晰",
                why="每段只有第一条一定会被读到，它应该是这段里最有分量的成果。",
                fix="在原项目陈述内写清已有的成果，不要拆散上下文或机械重排。",
            ),
            met=not weak_leads,
            detail="全部段落以强证据开头"
            if not weak_leads
            else f"{len(weak_leads)}/{len(all_blocks)} 段开头偏弱",
            field_path=None if not weak_leads else f"experience_blocks[{weak_leads[0]}].bullets[0]",
        )
    )

    # 4. 篇幅与深度
    lead_count = len(_bullets(experience[0])) if experience else 0
    thin_tail = [
        idx
        for idx, block in enumerate(experience[1:], start=1)
        if len(_bullets(block)) < blueprint.tail_bullets
    ]
    depth_met = bool(experience) and lead_count >= blueprint.lead_bullets and not thin_tail
    findings.append(
        BlueprintFinding(
            requirement=BlueprintRequirement(
                id="document_depth",
                label="分量与经历相称",
                why=(
                    f"完整性参考：最近经历约 {blueprint.lead_bullets} 段、"
                    f"更早经历约 {blueprint.tail_bullets} 段。不是条数配额；"
                    "原文项目与段落完整性优先，少于参考值不等于经历不足。"
                ),
                fix="保留项目与段落完整性；如有遗漏，补回独立的原始经历，不要为凑条数拆散同一项目。",
            ),
            met=depth_met,
            detail=(
                f"最近一段 {lead_count} 条"
                + (f"，{len(thin_tail)} 段更早经历过薄" if thin_tail else "")
            )
            if experience
            else "还没有工作经历",
            field_path=None if depth_met else "experience_blocks[0]",
        )
    )

    # 5. 结果密度
    total = sum(len(_bullets(b)) for b in all_blocks)
    with_outcome = 0
    for block in all_blocks:
        for bullet in _bullets(block):
            reasons = score_bullet(bullet, playbook=playbook).reasons
            if any(r in reasons for r in _OUTCOME_REASONS):
                with_outcome += 1
    ratio = round(with_outcome / total, 2) if total else 0.0
    findings.append(
        BlueprintFinding(
            requirement=BlueprintRequirement(
                id="outcome_density",
                label="多数要点要有结果",
                why=(
                    f"{blueprint.label}的成果看："
                    + "、".join(blueprint.evidence_ladder[:3])
                    + "。没有结果的要点读起来是职责描述。"
                )
                if not blueprint.quantification_optional
                else (
                    f"{blueprint.label}的结果常常没有数字，但「解决了什么、避免了什么」"
                    "必须写出来，否则只是职责。"
                ),
                fix="去「补充证据」回答缺结果的那几条，我们不会替你编数字。",
            ),
            met=total > 0 and ratio >= blueprint.outcome_ratio,
            detail=f"{with_outcome}/{total} 条带结果（目标 {int(blueprint.outcome_ratio * 100)}%）"
            if total
            else "还没有要点",
            field_path=None if ratio >= blueprint.outcome_ratio else "experience_blocks",
        )
    )

    # 6. 岗位专属必备项
    if blueprint.must_haves:
        haystack = " ".join(
            [
                str(sections.get("summary") or ""),
                str((sections.get("header") or {}).get("contact_line") or ""),
                str((sections.get("skills_block") or {}).get("content") or ""),
            ]
            + [b for block in all_blocks for b in _bullets(block)]
        ).lower()
        # Matched on the leading token of each requirement: `must_haves` entries are
        # phrases like "作品集链接", and a phrase match would miss "作品集：…".
        missing = [m for m in blueprint.must_haves if m[:2].lower() not in haystack]
        findings.append(
            BlueprintFinding(
                requirement=BlueprintRequirement(
                    id="family_must_haves",
                    label=f"{blueprint.label}的必备项",
                    why="这类岗位缺了这些，简历在第一轮就会被判为不完整。",
                    fix="补齐：" + "、".join(blueprint.must_haves),
                ),
                met=not missing,
                detail="已齐备" if not missing else "缺少：" + "、".join(missing),
                field_path=None if not missing else "summary",
            )
        )

    return findings


@dataclass(frozen=True, slots=True)
class BlueprintReport:
    """How the document on screen measures against its family's bar."""

    blueprint: ResumeBlueprint
    findings: list[BlueprintFinding] = field(default_factory=list)

    @property
    def met(self) -> int:
        return sum(1 for f in self.findings if f.met)

    @property
    def total(self) -> int:
        return len(self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "blueprint": self.blueprint.to_dict(),
            "findings": [f.to_dict() for f in self.findings],
            "met": self.met,
            "total": self.total,
        }

    def unmet_issues(self) -> list[dict[str, Any]]:
        """Unmet requirements as reviewer-shaped issues. Advisory, never blocking."""
        out: list[dict[str, Any]] = []
        for finding in self.findings:
            if finding.met:
                continue
            out.append(
                {
                    "severity": "warning",
                    "code": f"blueprint_{finding.requirement.id}",
                    "field": finding.field_path or "summary",
                    "message": (
                        f"{finding.requirement.label}：{finding.detail}。"
                        f"{finding.requirement.fix}"
                    ),
                }
            )
        return out


def evaluate_blueprint(
    sections: dict[str, Any],
    *,
    role_family: str | None = None,
) -> BlueprintReport:
    """Measure a generated draft against its family's blueprint. Pure, no model."""
    if sections.get("track") == "bilingual":
        sections = sections.get("zh_sections") or {}
    blueprint = blueprint_for(role_family or sections.get("role_family"))
    return BlueprintReport(
        blueprint=blueprint,
        findings=_requirement_checks(blueprint, sections),
    )


#: Exported for callers that want the checker set without running it, e.g. docs.
REQUIREMENT_IDS: tuple[str, ...] = (
    "summary_conclusion_first",
    "scope_lines",
    "strong_lead_bullets",
    "document_depth",
    "outcome_density",
    "family_must_haves",
)

__all__ = [
    "REQUIREMENT_IDS",
    "BlueprintFinding",
    "BlueprintReport",
    "BlueprintRequirement",
    "ResumeBlueprint",
    "all_blueprints",
    "blueprint_for",
    "evaluate_blueprint",
]
