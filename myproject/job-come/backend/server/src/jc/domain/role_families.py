"""Role-family playbooks: what "a strong resume" means for a specific kind of job.

Why this exists
---------------
JC's writing methodology (Action + Object + Outcome, verb strength, the quantification
ladder) was written with engineering roles in mind and then applied to everyone. That is
wrong in two directions at once:

1. **It under-serves non-engineering roles.** A recruiter reading an operations or legal
   resume is looking for different evidence than one reading a backend resume. "What
   result did it produce" is answered in retention and GMV for growth, in cycle time and
   win rate for sales, and sometimes in "the risk never materialised" for legal and
   compliance — which has no number at all.
2. **It actively penalises them.** The reviewer flags "evidence exists but no outcome"
   and the technique classifier detects objects via named-system tokens. Both are tuned
   to engineering vocabulary, so a well-written marketing bullet gets told it is vague.

So a playbook does **not** replace the methodology. It supplies the role-specific
vocabulary the methodology needs in order to be applied honestly:

- `outcome_metrics` — what a result legitimately looks like here, used to prompt the user
  and the writer for evidence that exists but was left off the page.
- `object_nouns` — what the "Object" of a bullet is for this role, so a non-technical
  object is not mistaken for vagueness.
- `quantification_optional` — whether a missing number is a real gap or simply how this
  job works. Drives whether the reviewer may raise `no_outcome`.
- `must_haves` — role-specific document requirements a generic reviewer misses entirely
  (a design resume without a portfolio link is not a resume).
- `section_priority` — which section a recruiter in this family reads first.
- `framing_angles` — the honest reframing prompts for this role: the same work described
  in the terms this audience cares about.

Everything here is **presentation guidance, never fact generation.** A playbook can say
"growth roles are read for retention impact"; it can never supply a retention number.
The family ids are deliberately the same ids used by
`agent/prompts/coach/industry_followups.yaml`, so resume writing and mock interviews
speak about roles in one shared vocabulary instead of two.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

GENERAL = "general"


@dataclass(frozen=True, slots=True)
class RolePlaybook:
    id: str
    label: str
    #: What a legitimate "Outcome" looks like for this role.
    outcome_metrics: tuple[str, ...]
    #: What the "Object" of a bullet is here, so non-technical objects read as concrete.
    object_nouns: tuple[str, ...]
    #: Honest reframing angles — how to describe the same work for this audience.
    framing_angles: tuple[str, ...]
    #: Document requirements a generic reviewer would not know about.
    must_haves: tuple[str, ...] = ()
    #: True when results in this job are often qualitative rather than numeric.
    quantification_optional: bool = False
    #: Sections a recruiter in this family reads first, strongest first.
    section_priority: tuple[str, ...] = ("summary", "experience", "projects", "education", "skills")

    def as_prompt_block(self) -> str:
        """Render the playbook for injection into the writer/reviewer prompts."""
        lines = [
            f"Role family: {self.label} (`{self.id}`)",
            "Outcome vocabulary (use only values the source supports): "
            + "、".join(self.outcome_metrics),
            "What counts as a concrete object here: " + "、".join(self.object_nouns),
        ]
        if self.framing_angles:
            lines.append("Framing angles for this audience:")
            lines.extend(f"- {angle}" for angle in self.framing_angles)
        if self.must_haves:
            lines.append("This role's resume is incomplete without: " + "、".join(self.must_haves))
        if self.quantification_optional:
            lines.append(
                "Numeric outcomes are frequently unavailable in this role. A precise "
                "qualitative outcome (scope, risk avoided, decision enabled) is a complete "
                "bullet here — do not demand a metric and never invent one."
            )
        lines.append("Section priority: " + " > ".join(self.section_priority))
        return "\n".join(lines)


def _pb(**kwargs: Any) -> RolePlaybook:
    return RolePlaybook(**kwargs)


# --- playbooks ------------------------------------------------------------------------
# Ids mirror agent/prompts/coach/industry_followups.yaml.

PLAYBOOKS: dict[str, RolePlaybook] = {
    "backend": _pb(
        id="backend",
        label="后端 / 服务端研发",
        outcome_metrics=(
            "P99/P95 延迟", "QPS/TPS", "可用性 SLA", "成本节省", "故障率与恢复时长", "容量与规模",
        ),
        object_nouns=("服务", "接口", "链路", "存储", "集群", "中间件", "数据一致性方案"),
        framing_angles=(
            "把「做了什么功能」改写为「扛住了什么规模、解决了什么瓶颈」。",
            "架构决策要写清取舍：为什么选这个方案，放弃了什么。",
            "稳定性工作用「事故前后对比」表达，比「负责稳定性」有力得多。",
        ),
        section_priority=("summary", "experience", "projects", "skills", "education"),
    ),
    "frontend": _pb(
        id="frontend",
        label="前端 / 客户端研发",
        outcome_metrics=(
            "首屏与加载指标", "Core Web Vitals", "崩溃率", "包体积", "组件复用率",
            "覆盖的业务线数",
        ),
        object_nouns=("页面", "组件库", "构建链路", "埋点体系", "设计系统", "渲染性能"),
        framing_angles=(
            "体验优化必须落到可感知指标，而不是「优化了体验」。",
            "组件库/基建类工作用「被多少业务线复用」表达影响面。",
        ),
        section_priority=("summary", "experience", "projects", "skills", "education"),
    ),
    "ios": _pb(
        id="ios",
        label="移动端研发",
        outcome_metrics=("崩溃率", "启动耗时", "包体积", "内存占用", "日活覆盖量"),
        object_nouns=("App 模块", "启动链路", "离线能力", "推送通道", "热修复方案"),
        framing_angles=("端上工作强调弱网、机型碎片与版本兼容带来的真实约束。",),
        section_priority=("summary", "experience", "projects", "skills", "education"),
    ),
    "devops": _pb(
        id="devops",
        label="运维 / SRE / 效能",
        outcome_metrics=(
            "MTTR", "变更成功率", "发布频率", "告警噪音下降", "资源成本节省", "Lead Time",
        ),
        object_nouns=("发布流水线", "监控告警体系", "容量模型", "容器平台", "值班与 SOP"),
        framing_angles=(
            "SRE 的成果是「坏事变少」，用事故数、MTTR、告警量的前后对比表达。",
            "成本治理要给出节省绝对值或比例，这是最被管理者关注的一类成果。",
        ),
        section_priority=("summary", "experience", "projects", "skills", "education"),
    ),
    "data": _pb(
        id="data",
        label="数据 / 算法 / 分析",
        outcome_metrics=(
            "模型离线与线上指标", "实验提升幅度与显著性", "决策采纳情况", "数据覆盖与质量",
            "收益或成本影响",
        ),
        object_nouns=("模型", "特征体系", "指标体系", "实验平台", "数据链路", "看板"),
        framing_angles=(
            "必须区分「离线指标提升」和「业务指标提升」，混着写会被一问就穿。",
            "分析类工作的成果是「推动了什么决策」，不是「产出了多少报表」。",
            "实验结论要带样本量与置信度语境，这是专业度最直接的体现。",
        ),
        section_priority=("summary", "experience", "projects", "skills", "education"),
    ),
    "pm": _pb(
        id="pm",
        label="产品经理",
        outcome_metrics=(
            "留存与活跃", "转化率", "GMV/营收", "渗透率", "需求上线后的指标变化", "覆盖用户量",
        ),
        object_nouns=("产品线", "功能模块", "用户场景", "业务流程", "商业模式", "跨团队方案"),
        framing_angles=(
            "产品岗最忌写成需求清单。每段经历回答：你判断做什么、为什么值得做、上线后发生了什么。",
            "没涨的项目也可以写，但要写出复盘与决策收敛——这体现判断力，比假装成功可信。",
            "跨团队推动力是产品岗的核心证据，写清协同范围与阻力。",
        ),
        section_priority=("summary", "experience", "projects", "skills", "education"),
    ),
    "design": _pb(
        id="design",
        label="设计 / 用户体验",
        outcome_metrics=(
            "关键任务完成率", "可用性测试结论", "设计系统覆盖范围", "转化或留存变化",
            "交付效率提升",
        ),
        object_nouns=("用户旅程", "交互方案", "设计系统", "可用性问题", "品牌视觉体系"),
        framing_angles=(
            "设计岗的成果是「取舍」而非「稿子」：写清你在业务目标、体验质量、研发成本之间怎么权衡。",
            "用户研究要写到结论如何改变了方案，否则读起来像流程记录。",
        ),
        must_haves=("作品集链接（无作品集的设计简历基本无法进入评估）",),
        quantification_optional=True,
        section_priority=("summary", "projects", "experience", "skills", "education"),
    ),
    "operations": _pb(
        id="operations",
        label="运营",
        outcome_metrics=("活动 ROI", "拉新与留存", "内容消费指标", "社区活跃度", "履约或周转效率"),
        object_nouns=("用户分层", "活动机制", "内容矩阵", "渠道", "运营流程", "商家或作者生态"),
        framing_angles=(
            "运营岗要写清「机制设计」而不是「执行了活动」，机制才体现可复用的能力。",
            "效果必须说明归因方式，区分自然增长与运营贡献，这是运营专业度的分水岭。",
            "没预算条件下的低成本验证是运营岗很强的加分项。",
        ),
        section_priority=("summary", "experience", "projects", "skills", "education"),
    ),
    "marketing": _pb(
        id="marketing",
        label="市场 / 品牌 / 增长",
        outcome_metrics=("CAC/ROI", "曝光与转化漏斗", "品牌声量", "渠道贡献占比", "预算效率"),
        object_nouns=("目标人群", "渠道组合", "投放策略", "品牌叙事", "增长漏斗"),
        framing_angles=(
            "增长岗必须给出归因逻辑，否则所有数字都会被当成蹭自然增长。",
            "预算规模本身就是 scope 证据，写清你管了多少预算。",
        ),
        section_priority=("summary", "experience", "projects", "skills", "education"),
    ),
    "sales": _pb(
        id="sales",
        label="销售 / 商务 / BD",
        outcome_metrics=(
            "业绩完成率与排名", "回款与客单价", "赢率", "新签与续约", "销售周期缩短",
            "管辖区域或团队规模",
        ),
        object_nouns=("客户决策链", "商机管道", "行业解决方案", "渠道伙伴", "续约与增购"),
        framing_angles=(
            "销售岗的数字必须前置。「超额完成 135%，区域排名第 2」应该是每段经历的第一行。",
            "大单要写决策链复杂度与推进周期，这比总额更能体现能力。",
            "完成率、排名、绝对额三者至少给两个，单给一个容易被当成挑好的说。",
        ),
        section_priority=("summary", "experience", "skills", "projects", "education"),
    ),
    "customer_success": _pb(
        id="customer_success",
        label="客户成功 / 服务",
        outcome_metrics=(
            "续约率与流失率", "NPS/满意度", "客户健康分", "增购金额", "响应与解决时效",
        ),
        object_nouns=("客户生命周期", "健康分体系", "服务 SOP", "升级路径", "客户培训体系"),
        framing_angles=(
            "客户成功要写「预防」而非「救火」：主动识别风险并挽回的案例最有力。",
            "管辖客户数与 ARR 规模是 scope 证据，必须写。",
        ),
        section_priority=("summary", "experience", "skills", "projects", "education"),
    ),
    "hr": _pb(
        id="hr",
        label="人力资源 / 招聘",
        outcome_metrics=(
            "到岗周期", "招聘完成率", "关键岗位留存", "人均效能", "组织满意度", "覆盖人数规模",
        ),
        object_nouns=("招聘流程", "人才标准", "绩效体系", "组织结构", "员工关系", "培养体系"),
        framing_angles=(
            "HR 岗要写清「服务的组织规模」，这是最直接的 scope 证据。",
            "制度类工作的成果是落地率与行为改变，不是「制定了制度」。",
        ),
        quantification_optional=True,
        section_priority=("summary", "experience", "skills", "projects", "education"),
    ),
    "finance": _pb(
        id="finance",
        label="财务 / 经营分析",
        outcome_metrics=(
            "成本节省", "预算准确率", "结账周期", "资金效率", "审计结论", "管辖营收规模",
        ),
        object_nouns=("预算体系", "经营分析模型", "成本结构", "资金计划", "财务流程与系统"),
        framing_angles=(
            "财务岗要写清「你的分析改变了什么决策」，否则读起来像在描述岗位职责。",
            "合规与审计类成果用「零重大问题」「问题整改闭环」表达，这是该岗位的正当成果。",
        ),
        quantification_optional=True,
        section_priority=("summary", "experience", "skills", "projects", "education"),
    ),
    "legal": _pb(
        id="legal",
        label="法务 / 合规",
        outcome_metrics=(
            "风险敞口下降", "合同周转时效", "争议解决结果", "合规审查覆盖率", "处理案件或合同量",
        ),
        object_nouns=("合同体系", "合规框架", "争议案件", "监管沟通", "业务风险评估"),
        framing_angles=(
            "法务岗最重要的成果常常是「坏事没有发生」，这类成果没有数字也是完整的。",
            "要写清你如何在合规与业务时效之间给出替代路径，而不是只说「把关」。",
            "业务参与度是法务的核心区分点：是事后审还是事前介入方案设计。",
        ),
        quantification_optional=True,
        section_priority=("summary", "experience", "skills", "projects", "education"),
    ),
    "management": _pb(
        id="management",
        label="管理 / 负责人",
        outcome_metrics=(
            "团队规模与结构", "业务目标达成", "人才培养与晋升", "跨部门交付", "组织效率提升",
        ),
        object_nouns=("团队", "业务线", "组织目标", "跨部门依赖", "人才梯队", "技术或业务战略"),
        framing_angles=(
            "管理岗必须区分「我个人做的」和「我带的团队做的」。不区分会被读成冒领成果，这是资深候选人最常见的失分点。",
            "带人成果要具体：团队规模变化、晋升人数、关键岗位补齐。",
            "写清你被授权的决策范围——预算、人员、技术选型，这决定了职级判断。",
        ),
        section_priority=("summary", "experience", "projects", "skills", "education"),
    ),
    GENERAL: _pb(
        id=GENERAL,
        label="通用知识工作",
        outcome_metrics=(
            "效率提升", "成本或工时节省", "质量与差错率", "覆盖范围与规模", "推动的决策",
        ),
        object_nouns=("业务流程", "项目", "协作机制", "交付物", "对接方"),
        framing_angles=(
            "先写清你负责的范围和对象，再写结果。缺对象的要点无论多漂亮都是空句。",
            "跨团队协作要写清你的角色是执行、推动还是决策。",
        ),
        quantification_optional=True,
    ),
}


# --- inference ------------------------------------------------------------------------
# Ordered: the first matching family wins, so put specific aliases before generic ones.
# `管理` deliberately sits last — a title like "后端技术负责人" is primarily a backend role.

_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ios", ("ios", "android", "移动端", "客户端", "flutter", "鸿蒙")),
    ("frontend", ("前端", "frontend", "web 开发", "react", "vue", "h5")),
    ("devops", ("运维", "devops", "sre", "效能", "基础架构", "平台工程", "infra")),
    ("data", (
        "数据", "算法", "data", "analytics", "机器学习", "ai ", "推荐", "搜索", "风控建模", "bi",
    )),
    ("backend", (
        "后端", "服务端", "backend", "java", "golang", "go 开发", "python 开发", "c++", "架构师",
    )),
    ("pm", ("产品经理", "产品负责人", "product manager", "产品策划", " pm", "pm ", "产品运营专家")),
    ("design", ("设计", "designer", "ux", "ui ", "交互", "视觉", "用户研究")),
    ("operations", ("运营", "operation", "内容", "社区", "品类", "商家", "作者生态")),
    ("marketing", ("市场", "marketing", "品牌", "增长", "投放", "公关", "pr ")),
    ("sales", ("销售", "sales", "商务", "bd", "客户经理", "大客户", "渠道")),
    ("customer_success", ("客户成功", "customer success", "客服", "售后", "服务经理", "交付经理")),
    ("hr", ("人力", "招聘", "hr", "hrbp", "组织发展", "薪酬", "培训")),
    ("finance", ("财务", "finance", "会计", "审计", "经营分析", "税务", "资金")),
    ("legal", ("法务", "legal", "合规", "风控合规", "知识产权", "律师")),
    ("management", ("总监", "负责人", "director", "vp", "总经理", "cto", "coo", "管理")),
)


def infer_role_family(*candidates: str | None) -> str:
    """Best-effort family for a role title, trying each candidate in order.

    Returns `general` when nothing matches. The caller is expected to let the user
    override this: guessing wrong means rewriting a whole resume against the wrong
    audience, which is worse than applying the neutral playbook.
    """
    for candidate in candidates:
        title = (candidate or "").strip().lower()
        if not title:
            continue
        for family, aliases in _ALIASES:
            if any(alias in title for alias in aliases):
                return family
    return GENERAL


def get_playbook(family: str | None) -> RolePlaybook:
    """Resolve a family id to its playbook, falling back to the neutral one."""
    if not family:
        return PLAYBOOKS[GENERAL]
    return PLAYBOOKS.get(str(family).strip().lower(), PLAYBOOKS[GENERAL])


def playbook_for_title(*candidates: str | None) -> RolePlaybook:
    return get_playbook(infer_role_family(*candidates))


def resolve_role_family(
    *,
    override: str | None = None,
    job_category: str | None = None,
    job_title: str | None = None,
    profile_titles: tuple[str | None, ...] = (),
) -> str:
    """Single source of truth for "which playbook applies to this document".

    Precedence is deliberate: an explicit user choice beats everything, then the
    category we stored for the target job, then free-text titles. Inference is the
    last resort because picking the wrong family rewrites a whole resume for the
    wrong audience.
    """
    if override:
        candidate = str(override).strip().lower()
        if candidate in PLAYBOOKS:
            return candidate
    if job_category:
        candidate = str(job_category).strip().lower()
        if candidate in PLAYBOOKS:
            return candidate
    return infer_role_family(job_title, *profile_titles)


def all_families() -> list[dict[str, Any]]:
    """Catalogue for the UI's family picker."""
    return [
        {
            "id": pb.id,
            "label": pb.label,
            "outcome_metrics": list(pb.outcome_metrics),
            "must_haves": list(pb.must_haves),
            "quantification_optional": pb.quantification_optional,
        }
        for pb in PLAYBOOKS.values()
    ]
