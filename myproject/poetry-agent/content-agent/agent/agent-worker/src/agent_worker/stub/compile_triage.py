"""COMPILE_TRIAGE (deterministic): map the gap report onto rules R1-R12 and rank by how much each blocks.

Output is a remediation list, ordered so the order cannot be swapped: sources are checked first (no
checkable source means no citation, no citation means no factual line can compile), then publishing
gates, then structure. Every item says who can do it. Verifying a source and filling a locator are
human-only; an agent can only prepare the request.
"""
from __future__ import annotations

from typing import Any

from agent_worker.snapshot import SnapshotView
from agent_worker.stub.common import cn_join, item, output
from agent_worker.stub.rules import RULE_NAMES, RuleResult, evaluate

# rank = blocking order; owner text is part of the body.
PLAN: dict[str, tuple[int, str, str]] = {
    "R3": (1, "人(史料审核人)", "先核对来源并填写真实定位,再让 claim 获得可核查引用;agent 只能整理来源请求,不能代做。"),
    "R2": (2, "人(审核与发布权限的持有人)", "来源核验后经评审流程逐项推进状态;agent 没有改变状态的能力。"),
    "R7": (3, "人(内容编辑)", "注释所依托的 claim 与文本版本须先走完评审;agent 可起草注释脚手架供评审。"),
    "R1": (4, "人(内容编辑)/agent 协助", "修复指向不存在对象的引用;agent 可列出清单,改动由编辑确认。"),
    "R8": (5, "agent 可起草,人确认", "背景关联到不存在的诗句时,由编辑确认应关联哪一句。"),
    "R11": (6, "agent 可起草,人确认", "为未关联诗句的背景草拟关联建议;是否保留该背景由编辑决定。"),
    "R6": (7, "人(编剧/编辑)", "存在两说的时间,bundle 里并列呈现并写明“未考日期”声明。"),
    "R5": (8, "人(编剧/编辑)", "bundle 必须写明本轮不覆盖什么;agent 可起草措辞。"),
    "R12": (9, "人(编剧)", "每一步都允许跳过与返回,在 bundle 结构里设置。"),
    "R4": (10, "人(素材负责人)", "每个素材的降级链必须终止在文字,需要 bundle 才能评估。"),
    "R9": (11, "人(素材负责人)", "素材需要内容哈希,需要 bundle 才能评估。"),
    "R10": (12, "人(素材负责人)", "素材需要来源、许可,并能说清帮助理解哪一句,需要 bundle 才能评估。"),
}
SERVER_TO_RULE = {
    "CLAIM_VERIFIED_CITATION_MISSING": "R3", "TEXT_SOURCE_NOT_VERIFIED": "R3",
    "ANNOTATION_COVERAGE_LOW": "R7", "INTEGRITY_AUDIT_NONZERO": "R2",
    "TEXT_VERSION_MISSING": "R1", "TEXT_LINES_MISSING": "R8", "BACKGROUND_LAYER_MISSING": "R0",
}


def _state(r: RuleResult, v: SnapshotView) -> str:
    if r.status == "PASS":
        return "当前数据通过。"
    if r.status == "FAIL":
        return f"当前数据不通过,涉及 {r.count} 个对象:{cn_join(r.details, 5)}。"
    return "需要编译后的 bundle 才能评估;当前只能列出前置条件。" if r.evaluation == "BUNDLE" else "当前数据不足,无法评估。"


def generate(v: SnapshotView) -> dict[str, Any]:
    results = evaluate(v)
    ranked = sorted(results, key=lambda r: PLAN[r.id][0])
    items: list[dict[str, Any]] = []
    for r in ranked:
        if r.status == "PASS":
            continue
        rank, owner, fix = PLAN[r.id]
        sev = "HIGH" if r.status == "FAIL" and rank <= 4 else "MEDIUM" if r.status == "FAIL" else "LOW"
        server = sorted(code for code, rid in SERVER_TO_RULE.items() if rid == r.id and any(g.get("code") == code for g in v.gap_report.get("gaps") or []))
        mapped = f"对应服务端缺口:{cn_join(server)}。" if server else ""
        body = (f"[{r.id} {RULE_NAMES[r.id]}] 阻塞序 {rank}。{_state(r, v)}{mapped}"
                f"整改:{fix} 责任:{owner}。")
        items.append(item("TRIAGE_ITEM", "DRAFT_TEXT", body, evidence_refs=r.refs[:18], severity=sev))
    # server gaps that belong to no R1-R12 rule are still shown
    for g in v.gap_report.get("gaps") or []:
        if SERVER_TO_RULE.get(str(g.get("code"))) == "R0":
            items.append(item("TRIAGE_ITEM", "DRAFT_TEXT",
                              f"[R0 shape] 服务端缺口 {g.get('code')}:缺少完整的背景层,属于 bundle 结构前置条件,不对应 R1 至 R12。整改:由编辑补写背景草稿;责任:人。",
                              evidence_refs=[], severity="MEDIUM"))
    only_human = [
        "来源的核验:只有史料审核人可做。",
        "为引用填写真实的卷页或篇章定位:只有史料审核人可做,agent 不提供。",
        "状态的推进与发布:只有拥有相应权限的人可做,agent 没有这项能力。",
    ]
    items.append(item("TRIAGE_ITEM", "DRAFT_TEXT", "[人工专属事项] " + " ".join(only_human), severity="HIGH"))

    failed = [r.id for r in results if r.status == "FAIL"]
    undecided = [r.id for r in results if r.status == "NOT_EVALUATED"]
    passed = [r.id for r in results if r.status == "PASS"]
    summary = (f"确定性分诊(未调用模型):十二条编译规则中,当前数据不通过 {len(failed)} 条({cn_join(failed, 12) or '无'}),"
               f"通过 {len(passed)} 条({cn_join(passed, 12) or '无'}),需要 bundle 才能评估 {len(undecided)} 条。"
               "整改顺序按阻塞度排列,第一步总是来源核查;该步只有人工能做。")
    unknowns = ["R4、R9、R10、R12 以及 R5、R6 的 bundle 部分需要编译后的 bundle,本次无法评估。"]
    if not v.gap_report:
        unknowns.append("快照不含服务端缺口报告,无法把缺口代码对应到规则。")
    first = next((r for r in ranked if r.status == "FAIL"), None)
    question = (f"是否先安排史料审核人处理 {first.id} 涉及的对象({cn_join(first.details, 3)})?" if first
                else "当前数据层规则均通过,是否可以开始准备 bundle 并评估其余规则?")
    return output("COMPILE_TRIAGE", summary, items, unknowns, question)
