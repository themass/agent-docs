"""GAP_ANALYSIS (deterministic): a real analysis of the studio-view snapshot.

Findings are aggregated per code (one HIGH item for "N claims lack a checkable source", not N items),
each with a severity and evidence_refs that are real snapshot ids. For every claim without a checkable
source it adds a SOURCE_REQUEST. It never writes a volume/page and never invents a locator: finding a
source and filling a locator is a human reviewer's job.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from agent_worker.sanitize import is_placeholder
from agent_worker.snapshot import SnapshotView
from agent_worker.stub.common import (
    cn_join,
    ids_ref,
    item,
    line_ref,
    output,
    snippet,
    sort_by_severity,
)
from agent_worker.vocab import LAYERS, SOURCE_KINDS

MAX_SOURCE_REQUESTS = 30
SERVER_COVERED = {
    "TEXT_VERSION_MISSING", "TEXT_LINES_MISSING", "CLAIM_VERIFIED_CITATION_MISSING",
    "TEXT_SOURCE_NOT_VERIFIED", "BACKGROUND_LAYER_MISSING", "ANNOTATION_COVERAGE_LOW",
    "INTEGRITY_AUDIT_NONZERO",
}


def _gap(code: str, severity: str, text: str, refs: list[str], target: str | None = None) -> dict[str, Any]:
    return item("GAP", "DRAFT_TEXT", f"[{code}] {text}", target_ref=target, evidence_refs=refs, severity=severity)


def _findings(v: SnapshotView) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    work_ref = f"work:{v.work_id}" if v.work_id else None

    # ---- text versions and lines (R1 / R8 groundwork) ----
    if not v.versions:
        out.append(_gap("TEXT_VERSION_MISSING", "HIGH", "作品还没有任何文本版本,后续注释、背景关联与剧本都没有可引用的诗句。", [], work_ref))
    for ver in v.versions:
        vid = str(ver["id"])
        seqs = v.line_seqs.get(vid, [])
        vref = f"version:{vid}"
        if not seqs:
            out.append(_gap("TEXT_LINES_MISSING", "HIGH", f"文本版本 {vid} 没有逐句行。", [vref], vref))
        elif seqs != list(range(1, len(seqs) + 1)):
            out.append(_gap("TEXT_LINE_SEQ_GAP", "HIGH", f"文本版本 {vid} 的句序不连续:{seqs}。", [vref], vref))
        status = v.version_status_by_id.get(vid, ver.get("status"))
        if status != "PUBLISHED":
            out.append(_gap("TEXT_VERSION_NOT_PUBLISHED", "MEDIUM",
                            f"文本版本 {vid} 当前状态为 {status},尚未进入可编译状态;状态变更只能由人工评审后完成。", [vref], vref))
        sid = ver.get("source_id")
        if not sid:
            out.append(_gap("TEXT_SOURCE_MISSING", "HIGH", f"文本版本 {vid} 没有登记底本来源。", [vref], vref))
        else:
            sref = f"source:{sid}"
            state = v.source_verification(str(sid))
            if state != "VERIFIED":
                out.append(_gap("TEXT_SOURCE_NOT_CHECKED", "HIGH",
                                f"文本版本 {vid} 的底本来源 {sid} 核验状态为 {state},逐字核对未完成;核验只能由史料审核人完成。",
                                [vref, sref], vref))
        if is_placeholder(ver.get("source_locator")):
            out.append(_gap("TEXT_LOCATOR_PLACEHOLDER", "MEDIUM",
                            f"文本版本 {vid} 的底本定位仍是占位或空白({snippet(str(ver.get('source_locator') or '空'), 20)})。", [vref], vref))

    # ---- background layers, links, pile-up (R11 / R8) ----
    present = {str(b.get("layer")) for b in v.backgrounds}
    for layer in LAYERS:
        if layer not in present:
            out.append(_gap("BACKGROUND_LAYER_MISSING", "MEDIUM", f"缺少 {layer} 层背景草稿。", [], work_ref))
    if v.backgrounds and not v.has_background_lines:
        out.append(_gap("BACKGROUND_LINKS_UNKNOWN", "LOW",
                        "本次快照不含“背景—诗句”关联表,无法判断是否存在未关联诗句的背景(R11)。", ids_ref("background", sorted(v.background_by_id))))
    elif v.backgrounds:
        unlinked = sorted(b for b in v.background_by_id if not v.lines_of_background.get(b))
        if unlinked:
            out.append(_gap("BACKGROUND_NOT_LINKED", "HIGH",
                            f"背景 {cn_join(unlinked)} 没有关联任何诗句:不能解释诗句的背景是堆砌,不是教学(R11)。", ids_ref("background", unlinked)))
        dangling = sorted({str(b) for b, links in v.lines_of_background.items() for (vid, seq) in links if not v.has_line(vid, seq)})
        if dangling:
            out.append(_gap("BACKGROUND_LINE_MISSING", "HIGH", f"背景 {cn_join(dangling)} 关联到不存在的诗句(R8)。", ids_ref("background", dangling)))
        for ver in v.versions:
            vid = str(ver["id"])
            covered = {seq for links in v.lines_of_background.values() for (lv, seq) in links if lv == vid}
            bare = [s for s in v.line_seqs.get(vid, []) if s not in covered]
            if bare and covered:
                out.append(_gap("LINES_WITHOUT_BACKGROUND", "LOW",
                                f"文本版本 {vid} 中第 {cn_join([str(s) for s in bare], 8)} 句目前没有任何背景关联(是否需要背景由编辑判断)。",
                                [line_ref(vid, s) for s in bare[:10]]))

    # ---- claims and sources ----
    bare_ids = sorted(str(c["id"]) for c in v.claims)
    no_basis = [c for c in v.claims if not v.claim_checkable(str(c["id"]))]
    facts_missing = sorted(str(c["id"]) for c in no_basis if c.get("claim_kind") == "FACT")
    other_missing = sorted(str(c["id"]) for c in no_basis if c.get("claim_kind") != "FACT")
    if facts_missing:
        out.append(_gap("FACT_CLAIM_NO_CHECKABLE_SOURCE", "HIGH",
                        f"{len(facts_missing)} 条 FACT 类 claim 没有可核查出处(没有已核验来源加真实定位):{cn_join(facts_missing)}。", ids_ref("claim", facts_missing)))
    if other_missing:
        out.append(_gap("CLAIM_NO_CHECKABLE_SOURCE", "MEDIUM",
                        f"{len(other_missing)} 条解释或演绎类 claim 没有可核查依据:{cn_join(other_missing)}。", ids_ref("claim", other_missing)))
    uncited = sorted(c for c in bare_ids if not v.citations_by_claim.get(c))
    if uncited:
        out.append(_gap("CLAIM_NO_CITATION", "HIGH", f"{len(uncited)} 条 claim 连引用记录都没有:{cn_join(uncited)}。", ids_ref("claim", uncited)))
    placeholder_cites = sorted({str(c["claim_id"]) for c in v.citations if is_placeholder(c.get("locator"))})
    if placeholder_cites:
        out.append(_gap("CITATION_LOCATOR_PLACEHOLDER", "HIGH",
                        f"{len(placeholder_cites)} 条 claim 的引用定位仍是占位文字:{cn_join(placeholder_cites)}。", ids_ref("claim", placeholder_cites)))
    overclaimed = sorted(str(c["id"]) for c in no_basis if c.get("certainty") == "KNOWN")
    if overclaimed:
        out.append(_gap("KNOWN_WITHOUT_BASIS", "HIGH",
                        f"{len(overclaimed)} 条 claim 标为 KNOWN,却没有可核查出处:{cn_join(overclaimed)}。", ids_ref("claim", overclaimed)))
    pending = v.pending_sources()
    if pending:
        out.append(_gap("SOURCES_PENDING", "HIGH",
                        f"{len(pending)} 个来源仍是 PENDING:{cn_join(pending)}。来源的核验与定位填写只有史料审核人能做,agent 没有这项权限。", ids_ref("source", pending)))
    rejected_cited = sorted({str(c["source_id"]) for c in v.citations if v.source_verification(str(c.get("source_id"))) == "REJECTED"})
    if rejected_cited:
        out.append(_gap("CITED_SOURCE_REJECTED", "HIGH", f"引用中使用了已被驳回的来源:{cn_join(rejected_cited)}。", ids_ref("source", rejected_cited)))

    # ---- annotations ----
    for ver in v.versions:
        vid = str(ver["id"])
        seqs = v.line_seqs.get(vid, [])
        annotated = sorted(s for s in seqs if v.annotations_by_line.get((vid, s)))
        bare = [s for s in seqs if s not in annotated]
        if seqs:
            out.append(_gap("ANNOTATION_COVERAGE", "MEDIUM" if bare else "LOW",
                            f"文本版本 {vid} 共 {len(seqs)} 句,已有注释的是第 {cn_join([str(s) for s in annotated]) or '无'} 句,尚无注释的有 {len(bare)} 句。",
                            [line_ref(vid, s) for s in bare[:10]] or [f"version:{vid}"], f"version:{vid}"))
    dangling_ann = sorted(a["id"] for a in v.annotations if not v.has_line(str(a.get("version_id")), a["line_seq"] if isinstance(a.get("line_seq"), int) else -1))
    if dangling_ann:
        out.append(_gap("ANNOTATION_LINE_MISSING", "HIGH", f"注释 {cn_join(dangling_ann)} 指向不存在的诗句。", ids_ref("annotation", dangling_ann)))
    weak_ann = sorted(str(a["id"]) for a in v.annotations if not v.claim_checkable(str(a.get("claim_id"))))
    if weak_ann:
        out.append(_gap("ANNOTATION_NO_CHECKABLE_SOURCE", "MEDIUM",
                        f"{len(weak_ann)} 条已有注释所依据的 claim 没有可核查出处:{cn_join(weak_ann)}。", ids_ref("annotation", weak_ann)))

    # ---- coverage declaration and uncertain dates (R5 / R6 groundwork) ----
    if v.has_coverage_rows:
        if not v.coverage_rows:
            out.append(_gap("COVERAGE_NOT_DECLARED", "HIGH", "没有任何覆盖声明:空白会被误读成“历史上没有”,必须声明本轮不覆盖什么(R5)。", [], work_ref))
        else:
            drafts = sorted(str(r["id"]) for r in v.coverage_rows if str(r.get("status")) != "PUBLISHED")
            if drafts:
                out.append(_gap("COVERAGE_ROW_NOT_FINAL", "LOW", f"覆盖声明 {cn_join(drafts)} 尚未定稿。", ids_ref("coverage", drafts)))
            year = v.work.get("start_year")
            wrows = [r for r in v.coverage_rows if str(r.get("entity_type")) == "WORK"]
            if isinstance(year, int) and wrows and not any(
                isinstance(r.get("from_year"), int) and isinstance(r.get("to_year"), int) and r["from_year"] <= year <= r["to_year"] for r in wrows
            ):
                out.append(_gap("COVERAGE_RANGE_MISS", "MEDIUM", f"作品时间 {year} 年不在任何作品覆盖声明的年份范围内。", ids_ref("coverage", [str(r["id"]) for r in wrows])))
    else:
        out.append(_gap("COVERAGE_UNKNOWN", "LOW", "本次快照不含覆盖声明表,无法判断覆盖声明是否齐全(R5)。", [], work_ref))
    uncertain = sorted(str(c["id"]) for c in v.claims if str(c.get("property_key")) == "time.span" and c.get("certainty") in ("DISPUTED", "UNKNOWN"))
    if uncertain:
        out.append(_gap("UNKNOWN_DATES_UNDECLARED", "MEDIUM",
                        f"时间类 claim {cn_join(uncertain)} 的确定度为 DISPUTED 或 UNKNOWN:两说并存时都要保留,编译时必须带“未考日期”声明(R6)。", ids_ref("claim", uncertain)))

    # ---- audit and server-reported gaps not covered above ----
    for entry in v.gap_report.get("audit_non_zero") or []:
        code = re.match(r"[A-Za-z0-9_]+", str(entry))
        out.append(_gap("INTEGRITY_AUDIT_NONZERO", "HIGH", f"完整性审计有非零项:{code.group(0) if code else '未识别'}。", [], work_ref))
    for gap in v.gap_report.get("gaps") or []:
        code = str(gap.get("code") or "")
        if code and code not in SERVER_COVERED:
            sev = gap.get("severity") if gap.get("severity") in ("HIGH", "MEDIUM", "LOW") else "MEDIUM"
            out.append(_gap(f"SERVER_{code}", sev, f"服务端缺口报告列出了本分析未覆盖的缺口代码 {code}。", [], work_ref))
    return out


def _citation_state(v: SnapshotView, cites: list[dict[str, Any]], sid: str | None) -> str:
    """Why this claim has no checkable citation, from the citation rows themselves.

    Wording avoids stating a source's state as an assertion; only the PENDING case names it.
    """
    if not sid:
        return "尚无任何候选来源" if not cites else "引用记录指向的来源不在快照中"
    reasons: list[str] = []
    cite = next((c for c in cites if str(c.get("source_id")) == sid), {})
    state = v.source_verification(sid)
    if state == "PENDING":
        reasons.append("来源仍是 PENDING")
    elif state == "REJECTED":
        reasons.append("来源已被驳回")
    elif state != "VERIFIED":
        reasons.append("来源核验记录缺失")
    if is_placeholder(cite.get("locator")):
        reasons.append("定位仍是占位")
    return f"已登记候选来源 {sid},但" + "、".join(reasons or ["引用尚不满足可核查条件"])


def _source_requests(v: SnapshotView, budget: int) -> tuple[list[dict[str, Any]], int]:
    pool = [c for c in v.claims if not v.claim_checkable(str(c["id"]))]
    pool.sort(key=lambda c: (c.get("claim_kind") != "FACT", str(c["id"])))
    chosen = pool[: min(MAX_SOURCE_REQUESTS, max(0, budget))]
    out: list[dict[str, Any]] = []
    for c in chosen:
        cid = str(c["id"])
        cites = v.citations_by_claim.get(cid, [])
        sid = next((str(x["source_id"]) for x in cites if x.get("source_id") in v.source_by_id), None)
        src = v.source_by_id.get(sid or "", {})
        kind = src.get("source_kind") if src.get("source_kind") in SOURCE_KINDS else None
        title = snippet(str(src.get("title")), 120) if src.get("title") else None
        state = _citation_state(v, cites, sid)
        what = f"{c.get('subject_id')} 的 {c.get('property_key')}:{snippet(str(c.get('value_text')), 60)}"
        body = f"claim {cid}({c.get('claim_kind')}/{c.get('certainty')})没有可核查出处:{state}。需要史料审核人确认出处并填写定位。"
        refs = [f"claim:{cid}"] + ([f"source:{sid}"] if sid else [])
        out.append(item("SOURCE_REQUEST", "FACT_REQUEST", body, target_ref=f"claim:{cid}", evidence_refs=refs,
                        severity="HIGH" if c.get("claim_kind") == "FACT" else "MEDIUM",
                        source_request={"claim_ref": cid, "what_to_verify": what,
                                        "suggested_source_kind": kind, "suggested_source_title": title}))
    return out, len(pool) - len(chosen)


def generate(v: SnapshotView) -> dict[str, Any]:
    findings = sort_by_severity(_findings(v))[:20]
    requests, omitted = _source_requests(v, 50 - len(findings))
    items = findings + requests
    sev = Counter(i["severity"] for i in findings)
    no_basis = sum(1 for c in v.claims if not v.claim_checkable(str(c["id"])))
    pending = v.pending_sources()
    summary = (
        f"确定性分析(未调用模型):作品 {v.title or v.work_id},文本版本 {len(v.versions)} 个、诗句 {len(v.lines)} 句、claim {len(v.claims)} 条。"
        f"缺口 HIGH {sev['HIGH']} 项、MEDIUM {sev['MEDIUM']} 项、LOW {sev['LOW']} 项;"
        f"{no_basis} 条 claim 没有可核查出处,{len(pending)} 个来源仍是 PENDING。"
        "本分析只检查快照里的结构与出处状态,不判断史实真伪,也不提供卷页定位。"
    )
    unknowns = [
        "各 claim 所述内容本身是否属实,需要史料审核人对照原始文献判断,本分析不作判断。",
        "每个来源的具体版本、卷页或篇章定位,需要史料审核人核对原文后填写。",
    ]
    if not v.has_background_lines:
        unknowns.append("快照不含背景与诗句的关联表,背景是否堆砌无法判断。")
    if not v.has_coverage_rows:
        unknowns.append("快照不含覆盖声明,覆盖范围是否已声明无法判断。")
    if omitted:
        unknowns.append(f"另有 {omitted} 条缺可核查出处的 claim 因条目上限未单列来源请求,请参见缺口项中的 claim 清单。")
    if pending:
        top = Counter(str(c["source_id"]) for c in v.citations if str(c.get("source_id")) in pending).most_common(1)
        sid = top[0][0] if top else pending[0]
        title = snippet(str(v.source_by_id.get(sid, {}).get("title", sid)), 40)
        question = f"来源 {sid}({title})牵涉的 claim 最多,是否安排史料审核人优先核对它?"
    else:
        question = "当前没有 PENDING 来源,是否需要先补充候选来源再继续分析?"
    return output("GAP_ANALYSIS", summary, items, unknowns, question)
