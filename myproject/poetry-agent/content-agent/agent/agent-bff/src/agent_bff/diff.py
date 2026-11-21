"""Structured diff of a DRAFT proposal against the current Java studio-view.

The diff is advisory for the human reviewer. It never decides anything: Java revalidates every
executable operation when it is applied.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

LABEL_PREFIXES = {
    "【来源请求】": "来源请求",
    "【解释】": "解释",
    "【演绎】": "演绎",
    "【草稿】": "草稿",
    "【未考】": "未考",
    "【缺口】": "缺口",
}
_TARGET = re.compile(r"^(line|claim|background|annotation|version):(.+)$")
_LINE_REF = re.compile(r"^(?P<version>[^#]+)#(?P<seq>\d+)$")


def label_for(change: dict[str, Any]) -> str:
    body = str(change.get("body", ""))
    for prefix, label in LABEL_PREFIXES.items():
        if body.startswith(prefix):
            return label
    if change.get("change_type") == "GAP_REPORT":
        return "缺口"
    return {"INTERPRETATION": "解释", "UNKNOWN": "未考", "DRAFT": "草稿"}.get(str(change.get("classification")), "草稿")


def is_executable(change: dict[str, Any]) -> bool:
    payload = change.get("draft_payload")
    return isinstance(payload, dict) and payload.get("operation") == "CREATE_ANNOTATION"


def executable_indexes(payload: dict[str, Any]) -> list[int]:
    return [i for i, change in enumerate(payload.get("changes") or []) if is_executable(change)]


def _before(change: dict[str, Any], view: dict[str, Any]) -> dict[str, Any] | None:
    target = str(change.get("target_ref") or "")
    match = _TARGET.match(target)
    if not match:
        return None
    kind, ref = match.groups()
    if kind == "line":
        line = _LINE_REF.match(ref)
        if not line:
            return None
        version, seq = line.group("version"), int(line.group("seq"))
        found = next((x for x in view.get("lines") or [] if str(x.get("version_id")) == version and int(x.get("line_seq", 0)) == seq), None)
        if found is None:
            return None
        existing = [a for a in view.get("annotations") or [] if str(a.get("version_id")) == version and int(a.get("line_seq", 0)) == seq]
        return {"kind": "line", "line": found, "annotations": existing}
    if kind == "claim":
        claim = next((c for c in view.get("claims") or [] if c.get("id") == ref), None)
        if claim is None:
            return None
        return {"kind": "claim", "claim": claim,
                "citations": [c for c in view.get("citations") or [] if c.get("claim_id") == ref]}
    if kind == "background":
        background = next((b for b in view.get("backgrounds") or [] if b.get("id") == ref), None)
        return {"kind": "background", "background": background} if background else None
    if kind == "annotation":
        annotation = next((a for a in view.get("annotations") or [] if a.get("id") == ref), None)
        return {"kind": "annotation", "annotation": annotation} if annotation else None
    return None


def _risks(change: dict[str, Any], view: dict[str, Any] | None, label: str) -> list[str]:
    risks: list[str] = []
    payload = change.get("draft_payload")
    if label == "来源请求":
        risks.append("这是来源请求:没有任何出处被确认,需要人工查证并填写 locator。")
    if label == "演绎":
        risks.append("演绎内容,不是史实;学生端必须带“演绎”角标。")
    if label == "未考":
        risks.append("未考:不要把它当作“历史上不存在”。")
    if change.get("classification") == "UNKNOWN" and label not in {"来源请求", "未考"}:
        risks.append("分类为 UNKNOWN,不应当作事实采用。")
    if isinstance(payload, dict):
        if payload.get("certainty") in {"DISPUTED", "UNKNOWN"}:
            risks.append(f"确定度为 {payload['certainty']}:需要人工判断是否适合学生。")
        if not payload.get("source_id"):
            risks.append("注释没有出处,应用后仍无法核查。")
        if payload.get("locator"):
            risks.append("agent 不得提供 locator,请驳回此项。")
        if view is not None:
            versions = {str(v.get("id")) for v in view.get("versions") or []}
            lines = {(str(x.get("version_id")), int(x.get("line_seq", 0))) for x in view.get("lines") or []}
            if str(payload.get("version_id")) not in versions:
                risks.append(f"文本版本 {payload.get('version_id')} 在当前底座中不存在,Java 会拒绝。")
            elif (str(payload.get("version_id")), int(payload.get("line_seq", 0))) not in lines:
                risks.append(f"{payload.get('version_id')} 没有第 {payload.get('line_seq')} 句,Java 会拒绝。")
            if payload.get("claim_id") in {c.get("id") for c in view.get("claims") or []}:
                risks.append(f"claim id {payload.get('claim_id')} 已存在,Java 会拒绝。")
            sources = {s.get("id") for s in view.get("sources") or []}
            if payload.get("source_id") and payload["source_id"] not in sources:
                risks.append(f"来源 {payload['source_id']} 不在本作品的来源中。")
    if not (change.get("evidence_refs") or []) and change.get("change_type") != "GAP_REPORT":
        risks.append("没有证据引用。")
    return risks


def build_diff(proposal: dict[str, Any], view: dict[str, Any] | None, items: list[dict[str, Any]]) -> dict[str, Any]:
    payload = proposal.get("payload") or {}
    decisions = {int(i.get("item_index")): i for i in items}
    rows = []
    for index, change in enumerate(payload.get("changes") or []):
        label = label_for(change)
        decision = decisions.get(index)
        rows.append({
            "index": index,
            "change_type": change.get("change_type"),
            "classification": change.get("classification"),
            "label": label,
            "executable": is_executable(change),
            "target_ref": change.get("target_ref"),
            "before": _before(change, view) if view is not None else None,
            "after": change.get("body"),
            "annotation": change.get("draft_payload"),
            "evidence_refs": change.get("evidence_refs") or [],
            "risks": _risks(change, view, label),
            "item_decision": ({"decision": decision.get("decision"), "comment": decision.get("comment"),
                               "reviewer": decision.get("reviewer")} if decision else None),
        })
    result: dict[str, Any] = {
        "proposal_id": proposal.get("proposal_id"),
        "work_id": proposal.get("work_id"),
        "snapshot_taken_at": datetime.now(UTC).isoformat(),
        "summary": payload.get("summary"),
        "unknowns": payload.get("unknowns") or [],
        "human_review_question": payload.get("human_review_question"),
        "changes": rows,
    }
    if view is None:
        result["warnings"] = ["当前底座视图不可用:无法对照 before,也无法预检 Java 校验;请稍后重试。"]
    return result
