"""SCRIPT_DRAFT (deterministic): an outline over the five steps 读 / 到 / 见 / 回 / 诵.

It only refers to ids that exist in the snapshot, says which beats have a basis and which do not, tags
every performed beat as dramatization, and writes no dialogue. "Basis" means a claim with a checkable
source; until sources are checked, background-driven beats are marked as lacking one.
"""
from __future__ import annotations

from typing import Any

from agent_worker.snapshot import SnapshotView
from agent_worker.stub.common import cn_join, ids_ref, item, line_ref, output, snippet
from agent_worker.vocab import LAYERS

LAYER_CN = {"SCENE": "眼前", "CITY": "这座城", "WORLD": "这个天下", "PERSON": "这个人"}


def generate(v: SnapshotView) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    ver = v.versions[0] if v.versions else None
    vid = str(ver["id"]) if ver else ""
    seqs = v.line_seqs.get(vid, [])
    grounded = lacking = drama = 0

    # 读: show the poem
    if seqs:
        first = snippet(v.line_content.get((vid, seqs[0]), ""), 14)
        items.append(item(
            "SCRIPT_BEAT", "DRAFT_TEXT",
            f"【读】按原序呈现 {vid} 的第 1 至第 {seqs[-1]} 句(首句「{first}」),不加背景讲解。该文本版本的底本尚未经人核对,此步只是草稿。",
            target_ref=f"version:{vid}", evidence_refs=[f"version:{vid}"] + [line_ref(vid, s) for s in seqs[:3]], severity="LOW"))
        grounded += 1
    else:
        items.append(item("SCRIPT_BEAT", "UNKNOWN", "【读】没有可呈现的诗句,此步无法起草。", severity="HIGH"))
        lacking += 1

    # 到: one beat per background layer
    by_layer = {str(b.get("layer")): b for b in v.backgrounds}
    for layer in LAYERS:
        bg = by_layer.get(layer)
        name = LAYER_CN[layer]
        if bg is None:
            items.append(item("SCRIPT_BEAT", "UNKNOWN", f"【到·{name}】没有 {layer} 层背景草稿,此拍没有依据;需先补背景,或删去这一拍。", severity="HIGH"))
            lacking += 1
            continue
        bid, cid = str(bg["id"]), str(bg.get("claim_id") or "")
        links = sorted({seq for (lv, seq) in v.lines_of_background.get(bid, []) if lv == vid})
        refs = [f"background:{bid}"] + ([f"claim:{cid}"] if cid in v.claim_by_id else []) + [line_ref(vid, s) for s in links[:4]]
        where = f"对应第 {cn_join([str(s) for s in links])} 句" if links else "尚未关联任何诗句"
        if cid and v.claim_checkable(cid):
            items.append(item("SCRIPT_BEAT", "DRAFT_TEXT", f"【到·{name}】依据背景 {bid}({where})安排一拍;台词由编剧撰写,事实性陈述须引用该 claim。",
                              target_ref=f"background:{bid}", evidence_refs=refs, severity="LOW"))
            grounded += 1
        else:
            items.append(item("SCRIPT_BEAT", "UNKNOWN",
                              f"【到·{name}】背景 {bid}({where})所依据的 claim 没有可核查出处,此拍暂无依据,只能占位;若演出,必须标为演绎。",
                              target_ref=f"background:{bid}", evidence_refs=refs, severity="MEDIUM"))
            lacking += 1

    # 见: a staged meeting is dramatization by definition
    author = next((c for c in v.claims if str(c.get("property_key")) == "authorship"), None)
    refs = ([f"claim:{author['id']}"] if author else []) + ([f"work:{v.work_id}"] if v.work_id else [])
    basis = "作者归属 claim 目前没有可核查出处" if author and not v.claim_checkable(str(author["id"])) else "作者归属需另行核对"
    items.append(item(
        "SCRIPT_BEAT", "DRAMATIZATION",
        f"【见】安排与诗人相见的一拍,整拍属于演绎,必须带“演绎”标签。本稿不写台词;若台词要引用史实,需引用有可核查出处的 claim({basis})。",
        target_ref=f"work:{v.work_id}" if v.work_id else None, evidence_refs=refs, severity="MEDIUM"))
    drama += 1

    # 回: return to the lines through annotations
    anns = sorted(v.annotations, key=lambda a: (str(a.get("version_id")), a.get("line_seq") if isinstance(a.get("line_seq"), int) else 0))[:6]
    if anns:
        for a in anns:
            seq, aid = a.get("line_seq"), str(a["id"])
            ok = v.claim_checkable(str(a.get("claim_id")))
            items.append(item(
                "SCRIPT_BEAT", "DRAFT_TEXT" if ok else "UNKNOWN",
                f"【回】回到第 {seq} 句,借注释 {aid} 的字词释义复读;" + ("该注释的依据可核查。" if ok else "该注释依据的 claim 没有可核查出处,此拍暂无依据。"),
                target_ref=line_ref(str(a.get("version_id")), seq) if isinstance(seq, int) else None,
                evidence_refs=[f"annotation:{aid}"] + ([line_ref(str(a.get("version_id")), seq)] if isinstance(seq, int) else []),
                severity="LOW" if ok else "MEDIUM"))
            grounded, lacking = (grounded + 1, lacking) if ok else (grounded, lacking + 1)
    else:
        items.append(item("SCRIPT_BEAT", "UNKNOWN", "【回】没有任何注释可供回扣,此步没有依据。", severity="HIGH"))
        lacking += 1
    if len(v.annotations) < 4:
        items.append(item("GAP", "DRAFT_TEXT", f"[ANNOTATION_COVERAGE_LOW] 现有注释 {len(v.annotations)} 条,「回」步可回扣的字词偏少。",
                          evidence_refs=ids_ref("annotation", [str(a["id"]) for a in v.annotations]), severity="MEDIUM"))

    # 诵: recite
    if seqs:
        items.append(item("SCRIPT_BEAT", "DRAFT_TEXT", f"【诵】按原序整首诵读第 1 至第 {seqs[-1]} 句,节奏与分句由编剧标注。",
                          target_ref=f"version:{vid}", evidence_refs=[f"version:{vid}"] + [line_ref(vid, s) for s in seqs[-2:]], severity="LOW"))
        grounded += 1
    else:
        items.append(item("SCRIPT_BEAT", "UNKNOWN", "【诵】没有可诵读的诗句。", severity="HIGH"))
        lacking += 1

    uncertain = [str(c["id"]) for c in v.claims if str(c.get("property_key")) == "time.span" and c.get("certainty") in ("DISPUTED", "UNKNOWN")]
    if uncertain:
        items.append(item("GAP", "DRAFT_TEXT",
                          f"[UNKNOWN_DATES_UNDECLARED] 时间类 claim {cn_join(uncertain)} 存在两说或未考,脚本若涉及年份,必须并列呈现并带“未考日期”声明。",
                          evidence_refs=ids_ref("claim", uncertain), severity="MEDIUM"))
    items.append(item("GAP", "DRAFT_TEXT", "[SCRIPT_FREE_MOVEMENT] 每一步都必须允许跳过与返回,覆盖声明须写明本轮不覆盖什么;这两项在 bundle 里设置,本稿不涉及。", severity="LOW"))

    summary = (f"确定性大纲(未调用模型,不含对白):读、到、见、回、诵五步共 {len([i for i in items if i['kind'] == 'SCRIPT_BEAT'])} 拍;"
               f"有依据 {grounded} 拍,暂无依据 {lacking} 拍,演绎 {drama} 拍。引用的 id 均来自快照。")
    unknowns = ["哪些背景拍能写成有出处的陈述,取决于对应 claim 的来源核查结果。",
                "「见」一步是否需要台词,以及台词能引用哪些史实,需要编剧与史料审核人商定。"]
    return output("SCRIPT_DRAFT", summary, items, unknowns, "「见」这一步是否需要台词;如果需要,是否先等对应 claim 的出处核查完成?")
