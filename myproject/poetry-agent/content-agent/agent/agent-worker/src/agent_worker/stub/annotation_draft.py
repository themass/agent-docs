"""ANNOTATION_DRAFT (deterministic): a scaffold, never annotation text.

Writing a real annotation needs interpretation, which the STUB must not fake. For every line it emits
an UNKNOWN item saying whether the line has an annotation yet and what a human editor must decide, and
it lists the open questions. There is no ``annotation`` payload, so nothing here is executable.
"""
from __future__ import annotations

from typing import Any

from agent_worker.snapshot import SnapshotView
from agent_worker.stub.common import cn_join, ids_ref, item, line_ref, output, snippet

MAX_LINES = 40


def generate(v: SnapshotView) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    unannotated: list[str] = []
    for ver in v.versions:
        vid = str(ver["id"])
        for seq in v.line_seqs.get(vid, []):
            if len(items) >= MAX_LINES:
                break
            text = v.line_content.get((vid, seq), "")
            existing = v.annotations_by_line.get((vid, seq), [])
            linked = sorted(b for b, links in v.lines_of_background.items() if (vid, seq) in links)
            refs = [line_ref(vid, seq)] + ids_ref("annotation", [str(a["id"]) for a in existing], 4) + ids_ref("background", linked, 4)
            if existing:
                ids = cn_join([str(a["id"]) for a in existing], 4)
                body = (f"第 {seq} 句「{snippet(text, 24)}」已有 {len(existing)} 条注释({ids})。"
                        "STUB 不改写现有注释;如需补充其他字词,请编辑指出词语与受众。")
                items.append(item("ANNOTATION", "UNKNOWN", body, target_ref=line_ref(vid, seq), evidence_refs=refs, severity="LOW"))
                continue
            unannotated.append(str(seq))
            bg = (f"本句关联的背景草稿有 {cn_join(linked, 3)},它们自身的出处也未经核查,只能作为编辑参考。" if linked else "本句没有关联的背景草稿。")
            body = (f"第 {seq} 句「{snippet(text, 24)}」尚无注释。{bg}"
                    "需要编辑决定:哪些字词需要注释、面向 PRIMARY、JUNIOR 还是 SENIOR 读者、依据哪个来源。STUB 不编写注释文字。")
            items.append(item("ANNOTATION", "UNKNOWN", body, target_ref=line_ref(vid, seq), evidence_refs=refs, severity="MEDIUM"))

    unverified = [str(ver.get("source_id")) for ver in v.versions if ver.get("source_id") and v.source_verification(str(ver["source_id"])) != "VERIFIED"]
    if unverified:
        items.append(item(
            "GAP", "DRAFT_TEXT",
            f"[TEXT_SOURCE_NOT_CHECKED] 文本版本的底本来源 {cn_join(unverified)} 尚未经史料审核人核对,字句本身可能还会改动,逐句注释应在底本确认后再定稿。",
            target_ref=f"work:{v.work_id}" if v.work_id else None,
            evidence_refs=ids_ref("source", unverified) + ids_ref("version", [str(x["id"]) for x in v.versions], 2), severity="HIGH"))
    weak = [str(a["id"]) for a in v.annotations if not v.claim_checkable(str(a.get("claim_id")))]
    if weak:
        items.append(item(
            "GAP", "DRAFT_TEXT",
            f"[ANNOTATION_NO_CHECKABLE_SOURCE] 已有注释 {cn_join(weak)} 所依据的 claim 没有可核查出处,新增注释同样需要先有来源,否则只能保持 UNKNOWN。",
            evidence_refs=ids_ref("annotation", weak), severity="MEDIUM"))

    total = sum(len(v.line_seqs.get(str(x["id"]), [])) for x in v.versions)
    summary = (f"确定性脚手架(未调用模型):共 {total} 句,尚无注释 {len(unannotated)} 句,已有注释 {total - len(unannotated)} 句。"
               "STUB 不编写注释文字,每句只列出需要编辑决定的事项;注释正文需要由 DeerFlow 模式的模型起草后人工评审,或由编辑撰写。")
    unknowns = [
        "哪些字词需要注释,取决于目标读者与教学要求,STUB 无法判断。",
        "注释所依据的出处与定位需要史料审核人核对,不能由 agent 补写。",
        "字词释义本身的准确性没有被检查。",
    ]
    if unannotated:
        question = f"本轮优先为第 {cn_join(unannotated, 8)} 句中的哪几句起草注释?"
    else:
        question = "所有诗句都已有注释,是否需要为其中某句补充另一类注释?"
    return output("ANNOTATION_DRAFT", summary, items, unknowns, question)
