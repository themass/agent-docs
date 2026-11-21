"""CONTENT_REVIEW (deterministic): the checks the twelve compile rules cannot make.

The validator's R1-R12 answer "is this structurally publishable". They cannot answer "is this true",
"is a two-reading claim presented as settled", "does a dramatized beat carry its label". Those need a
reader. The STUB is not a reader either: it never judges wording. What it can do is point at the exact
objects where the four facts below are mechanically visible, so the human reviewer starts from a list
instead of from a blank page.

Everything here is derived from the snapshot. No model is called, no fact is added, no source is
proposed, and no item can become an applicable change (``REVIEW_FINDING`` maps to a GAP_REPORT record).
"""
from __future__ import annotations

import re
from typing import Any

from agent_worker.sanitize import is_placeholder
from agent_worker.snapshot import SnapshotView
from agent_worker.stub.common import cn_join, ids_ref, item, output, snippet, sort_by_severity

MAX_FINDINGS = 30
# 一条注释或背景的长度上限（SKILL.md 第 4 维）。不分年级：产品只有一个版本（2026-11-12）。
TEXT_LIMIT = 100
# 给编辑看的内部标记。它们一旦进入已发布内容，读者会直接看到。
INTERNAL_MARKER = re.compile(r"草稿|待复核|待核对|措辞待|TBD|TODO")
# 「未收录」被写成「不存在」的措辞。只做提示，不做改写。
COVERAGE_OVERCLAIM = re.compile(r"(历史上(并)?(不|没)存在|从未(出现|发生)|根本没有)")


def _finding(body: str, severity: str, refs: list[str], target: str | None = None) -> dict[str, Any]:
    return item("REVIEW_FINDING", "INTERPRETATION", body, target_ref=target,
                evidence_refs=refs, severity=severity)


def _disputed(v: SnapshotView) -> list[dict[str, Any]]:
    """同一条陈述的两说：同一 subject+property 下有多条 certainty=DISPUTED 的 claim。"""
    out: list[dict[str, Any]] = []
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for c in v.claims:
        key = (str(c.get("subject_id") or ""), str(c.get("property_key") or ""))
        buckets.setdefault(key, []).append(c)
    for (subject, prop), rows in sorted(buckets.items()):
        if len(rows) < 2:
            continue
        disputed = [r for r in rows if str(r.get("certainty")) == "DISPUTED"]
        if not disputed:
            continue
        ids = [str(r["id"]) for r in rows if r.get("id")]
        values = cn_join([snippet(str(r.get("value_text") or ""), 24) for r in rows], 4)
        out.append(_finding(
            f"{subject} 的 {prop} 有 {len(rows)} 条并存陈述（{values}），其中 {len(disputed)} 条标为 DISPUTED。"
            "审核要确认：这些是否在 bundle 里并列出现并标明争议，而不是只取一说写成定论。"
            "本条只指出并存关系，不裁决哪一说成立。",
            "HIGH", ids_ref("claim", ids), f"claim:{ids[0]}"))
    return out


def _placeholders(v: SnapshotView) -> list[dict[str, Any]]:
    """有 citation 但定位仍是占位：陈述「有出处」，实际上没人能核。"""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for c in v.citations:
        if not is_placeholder(c.get("locator")):
            continue
        claim_id = str(c.get("claim_id") or "")
        if not claim_id or claim_id in seen or claim_id not in v.claim_by_id:
            continue
        seen.add(claim_id)
        out.append(_finding(
            f"claim {claim_id}（{snippet(str(v.claim_by_id[claim_id].get('value_text') or ''), 30)}）"
            f"挂着引用，但定位是占位文字「{snippet(str(c.get('locator') or ''), 24)}」。"
            "页面读起来像有出处，实际上无法核查。审核要确认这段内容是否被当成事实展示；"
            "核验完成之前，这段只能标为待核，不能当成有出处的事实展示。",
            "HIGH", [f"claim:{claim_id}", f"source:{c.get('source_id')}"], f"claim:{claim_id}"))
    return out


def _dramatization(v: SnapshotView) -> list[dict[str, Any]]:
    """演绎类内容：陈述本身标了 DRAMATIZATION，就要确认呈现层带了标识。"""
    out: list[dict[str, Any]] = []
    drama = [c for c in v.claims if str(c.get("claim_kind")) == "DRAMATIZATION"]
    if drama:
        ids = [str(c["id"]) for c in drama if c.get("id")]
        out.append(_finding(
            f"{len(drama)} 条 claim 标为 DRAMATIZATION：{cn_join(ids)}。"
            "审核要逐条确认它们的台词/画面带「演绎 · 不是史料」标识，且三处（文字卡、bundle、界面）措辞逐字一致。"
            "bundle 不在快照里，这一步必须在编译产物上做。",
            "HIGH", ids_ref("claim", ids), None))
    return out


def _readability(v: SnapshotView) -> list[dict[str, Any]]:
    """读得懂：内部标记漏给读者、单条过长。不分年级——只有一个版本，要让任何想弄懂这首诗的人读得懂。"""
    out: list[dict[str, Any]] = []
    texts = [("background", b, str(b.get("body_text") or "")) for b in v.backgrounds]
    texts += [("annotation", a, str(a.get("content") or "")) for a in v.annotations]
    for kind, row, text in texts:
        ref = f"{kind}:{row['id']}"
        marker = INTERNAL_MARKER.search(text)
        if marker:
            out.append(_finding(
                f"{ref} 的正文里带着给编辑看的内部标记「{marker.group(0)}」（「{snippet(text, 40)}」）。"
                "一旦进入已发布内容，读者会直接看到；「待复核」是给编辑的信号，不是给读者的话。"
                "审核要确认发布前改写成面向读者的表述，或整段不上。",
                "MEDIUM", [ref], ref))
        if len(text) > TEXT_LIMIT:
            out.append(_finding(
                f"{ref} 正文 {len(text)} 字，超过 {TEXT_LIMIT} 字。读者一次读不完一整段，理解会断。"
                "审核要判断是否拆开或改短；本条不代改。",
                "LOW", [ref], ref))
    return out


def _coverage(v: SnapshotView) -> list[dict[str, Any]]:
    """覆盖声明：把「未收录」说成「不存在」是最容易进的错。"""
    out: list[dict[str, Any]] = []
    for row in v.coverage_rows:
        note = str(row.get("note") or "")
        if COVERAGE_OVERCLAIM.search(note):
            out.append(_finding(
                f"覆盖记录 {row.get('id')} 的说明把「未收录」写成了「不存在」："
                f"「{snippet(note, 60)}」。空白只代表尚未覆盖，不代表历史上没有。审核要求改写。",
                "HIGH", [], None))
    if not v.coverage_rows:
        out.append(_finding(
            "快照里没有覆盖记录，无法判断本轮声明覆盖了什么、没覆盖什么。"
            "bundle 的覆盖声明必须与实际范围一致，这一点要在编译产物上补查。",
            "MEDIUM", [], None))
    return out


def _precise_numbers(v: SnapshotView) -> list[dict[str, Any]]:
    """无依据的精确数字：年龄、人数、年份精确到个位而来源不可核查。"""
    out: list[dict[str, Any]] = []
    for c in v.claims:
        value = str(c.get("value_text") or "")
        if not re.search(r"\d", value):
            continue
        if v.claim_checkable(str(c.get("id") or "")):
            continue
        out.append(_finding(
            f"claim {c.get('id')} 写有精确数字「{snippet(value, 40)}」，但没有任何可核查引用支撑它。"
            "审核要确认这句是否出现在正文；有依据就补出处，没有依据就改为「约」或标为待核，不能保留精确值。",
            "HIGH", [f"claim:{c['id']}"], f"claim:{c['id']}"))
    return out


def generate(v: SnapshotView) -> dict[str, Any]:
    published_claims = [c for c in v.claims if v.claim_status(str(c.get("id") or "")) == "PUBLISHED"]
    findings = _disputed(v) + _placeholders(v) + _dramatization(v) + _readability(v) + _coverage(v) + _precise_numbers(v)
    findings = sort_by_severity(findings)

    unknowns: list[str] = [
        "本任务是确定性审核（未调用模型）：只按可机械判定的六类给出线索，不判断措辞是否得体、比喻是否恰当。",
        "「依据是否真的支持陈述」需要读原文，STUB 做不到；它只能指出定位是占位或来源未核验的地方。",
    ]
    if not v.versions or not v.lines:
        unknowns.append("快照里没有已发布的诗句，本轮没有可审的正文。")

    blocking = sum(1 for f in findings if f.get("severity") == "HIGH")
    if not findings:
        summary = ("确定性审核（未调用模型）：已发布内容中没有发现可机械判定的问题。"
                   "这不等于内容正确——依据是否支持陈述、措辞是否合适仍需人读一遍。")
    else:
        summary = (f"确定性审核（未调用模型）：发现 {len(findings)} 处需要复核，其中 {blocking} 处高危。"
                   f"覆盖 {len(published_claims)} 条 PUBLISHED claim 与 {len(v.backgrounds)} 条背景草稿。"
                   "高危项优先：占位定位、两说被当定论、演绎缺标识。")

    question = ("这 "
                f"{blocking} 处高危项里，是否先处理占位定位的那几条？" if blocking
                else "没有高危项，是否可以进入人工终审？")
    return output("CONTENT_REVIEW", summary, findings[:MAX_FINDINGS], unknowns, question)
