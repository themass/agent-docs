"""epistemic/kind -> v1 change mapping (contract section 5). One table, used by validate and compile."""
from __future__ import annotations

from dataclasses import dataclass

PREFIX = {
    "来源请求": "【来源请求】", "解释": "【解释】", "演绎": "【演绎】",
    "草稿": "【草稿】", "未考": "【未考】", "缺口": "【缺口】", "审核": "【审核】",
}


@dataclass(frozen=True)
class Mapped:
    change_type: str
    classification: str
    label: str  # key of PREFIX

    @property
    def prefix(self) -> str:
        return PREFIX[self.label]


def map_item(kind: str, epistemic: str, target_ref: str | None = None) -> Mapped | None:
    """The change an item becomes, or ``None`` if the kind/epistemic pair is not allowed."""
    if kind == "SOURCE_REQUEST":
        return Mapped("CLAIM", "UNKNOWN", "来源请求") if epistemic == "FACT_REQUEST" else None
    if kind in ("GAP", "TRIAGE_ITEM"):
        return Mapped("GAP_REPORT", "DRAFT", "缺口") if epistemic in ("DRAFT_TEXT", "UNKNOWN") else None
    # 审核意见不是内容，永远不能变成可应用的改动：只落成一条 GAP_REPORT 记录。
    # epistemic 只允许 INTERPRETATION（判断）；写成 DRAFT_TEXT 会把审核结论当成待发草稿。
    if kind == "REVIEW_FINDING":
        return Mapped("GAP_REPORT", "DRAFT", "审核") if epistemic == "INTERPRETATION" else None
    if kind == "ANNOTATION":
        return {
            "INTERPRETATION": Mapped("ANNOTATION", "INTERPRETATION", "解释"),
            "DRAFT_TEXT": Mapped("ANNOTATION", "DRAFT", "草稿"),
            "UNKNOWN": Mapped("ANNOTATION", "UNKNOWN", "未考"),
        }.get(epistemic)
    if kind == "BACKGROUND_NOTE":
        change = "CLAIM" if (target_ref or "").startswith("claim:") else "BACKGROUND"
        return {
            "INTERPRETATION": Mapped(change, "INTERPRETATION", "解释"),
            "DRAMATIZATION": Mapped("BACKGROUND", "INTERPRETATION", "演绎"),
            "DRAFT_TEXT": Mapped("BACKGROUND", "DRAFT", "草稿"),
            "UNKNOWN": Mapped("BACKGROUND", "UNKNOWN", "未考"),
        }.get(epistemic)
    if kind == "SCRIPT_BEAT":
        return {
            "DRAMATIZATION": Mapped("SCRIPT", "INTERPRETATION", "演绎"),
            "DRAFT_TEXT": Mapped("SCRIPT", "DRAFT", "草稿"),
            "UNKNOWN": Mapped("SCRIPT", "UNKNOWN", "未考"),
        }.get(epistemic)
    return None


def with_prefix(prefix: str, body: str) -> str:
    return body if body.startswith(prefix) else f"{prefix}{body}"


def compose_body(kind: str, mapped: Mapped, body: str, source_request: dict | None) -> str:
    """Final change body: label prefix, then text; a source request gets its verification block appended."""
    text = with_prefix(mapped.prefix, body)
    if kind == "SOURCE_REQUEST" and source_request:
        extra = [f"待核查内容:{source_request.get('what_to_verify', '')}"]
        if source_request.get("claim_ref"):
            extra.append(f"关联 claim:{source_request['claim_ref']}")
        if source_request.get("suggested_source_kind"):
            extra.append(f"建议来源类型:{source_request['suggested_source_kind']}")
        if source_request.get("suggested_source_title"):
            extra.append(f"建议来源:{source_request['suggested_source_title']}")
        extra.append("卷页、篇章定位须由史料审核人核对后填写,此处不提供。")
        text = text + "\n" + "\n".join(extra)
    return text
