"""Label each elevation diff with the writing technique that produced it.

Problem this solves: the writer prompt encodes a real methodology (Action + Object +
Outcome, verb strength, the quantification ladder, target-role alignment), but none of
it was visible to the user, so the product felt like an opaque "make it better" button.

This module classifies each `elevation_map` entry deterministically by comparing the
conservative baseline text with the written text. No extra model call, no extra latency,
and the labels cannot drift from what actually changed in the text.

Labels are advisory UI metadata. They never gate export and never modify resume content.
"""

from __future__ import annotations

import re
from typing import Any

# --- technique catalogue -------------------------------------------------------------
# `id` is stable and used by the frontend; `label`/`hint` are user-facing Chinese copy.

TECHNIQUES: list[dict[str, str]] = [
    {
        "id": "quantified",
        "label": "补量化",
        "hint": "把规模、指标或前后对比写进要点，让成果可衡量。",
    },
    {
        "id": "outcome",
        "label": "加结果",
        "hint": "补上这件事带来的变化，而不是只说做了什么。",
    },
    {
        "id": "ownership",
        "label": "强化主导性",
        "hint": "在原文支持的范围内，换用更能体现负责程度的动词。",
    },
    {
        "id": "object",
        "label": "明确对象",
        "hint": "写清动作作用在哪个系统、产品或流程上，避免空泛。",
    },
    {
        "id": "jd_aligned",
        "label": "对齐岗位",
        "hint": "换用目标岗位描述里的说法，指同一件事，不新增技能。",
    },
    {
        "id": "tightened",
        "label": "精简表达",
        "hint": "删掉冗余铺垫，让招聘方更快读到重点。",
    },
    {
        "id": "expanded",
        "label": "补充细节",
        "hint": "把原文压缩掉的背景和职责还原出来。",
    },
]

_TECHNIQUE_BY_ID = {item["id"]: item for item in TECHNIQUES}

# Numbers, percentages, multipliers, orders of magnitude.
_METRIC_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|％|倍|万|千|亿|k|K|w|W|m|M|x|X)?"
    r"|\b(?:qps|tps|p99|p95|sla|dau|mau|arr|roi)\b",
    re.IGNORECASE,
)

# Words that introduce a consequence rather than an activity.
_OUTCOME_MARKERS = (
    "实现",
    "提升",
    "降低",
    "缩短",
    "下降",
    "增长",
    "节省",
    "减少",
    "支撑",
    "带来",
    "使得",
    "达成",
    "收敛",
    "解决",
    "覆盖",
    "resulting in",
    "reduced",
    "increased",
    "improved",
    "cut ",
    "achieved",
    "enabling",
    "enabled",
    "saving",
    "grew",
)

# Mirrors the verb-strength ladder in prompts/elevate/resume_writer.md.
_OWNERSHIP_VERBS = (
    "主导",
    "负责",
    "搭建",
    "设计并实现",
    "从 0 到 1",
    "从0到1",
    "牵头",
    "owned",
    "led",
    "architected",
    "built",
    "launched",
    "drove",
    "spearheaded",
)

_WEAK_VERBS = (
    "参与",
    "协助",
    "了解",
    "熟悉",
    "接触",
    "配合",
    "involved in",
    "helped with",
    "assisted",
    "familiar with",
    "worked on",
)

# Concrete-object signals: a named system/tech token rather than a vague noun.
# The CJK branch takes a fixed 2-char prefix on purpose. A greedy `{2,}` prefix would
# swallow unrelated leading words (`主导参与推送链路` vs `参与推送链路`), making a verb
# change look like an object change and mislabelling the diff.
_OBJECT_HINT_RE = re.compile(
    r"[A-Za-z][A-Za-z0-9+.#/-]{1,}"
    r"|[\u4e00-\u9fff]{2}(?:系统|平台|服务|链路|模块|流程|集群|网关|中心|引擎)"
)


def _has(text: str, needles: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(n.lower() in low for n in needles)


def _metrics(text: str) -> set[str]:
    return {m.strip().lower() for m in _METRIC_RE.findall(text) if m.strip()}


def _object_tokens(text: str, *, extra_nouns: tuple[str, ...] = ()) -> set[str]:
    """Concrete-object tokens in `text`.

    `_OBJECT_HINT_RE` only recognises engineering nouns, so a well-written operations or
    sales bullet ("把招商流程的审核环节前置", "重构大客户续约话术") would read as having no
    object at all. `extra_nouns` comes from the role playbook and supplies the nouns that
    count as concrete for this audience.
    """
    tokens = {t.lower() for t in _OBJECT_HINT_RE.findall(text) if len(t) > 1}
    low = text.lower()
    tokens |= {noun.lower() for noun in extra_nouns if noun and noun.lower() in low}
    return tokens


def classify_change(
    source_text: str,
    written_text: str,
    *,
    job_keywords: list[str] | None = None,
    role_family: str | None = None,
) -> list[str]:
    """Return the technique ids that explain `source_text` -> `written_text`.

    Returns an empty list when the change is cosmetic. Order follows `TECHNIQUES`
    so the UI renders labels consistently.
    """
    source = (source_text or "").strip()
    written = (written_text or "").strip()
    if not written or written == source:
        return []

    found: set[str] = set()
    object_nouns: tuple[str, ...] = ()
    if role_family:
        from jc.domain.role_families import get_playbook

        object_nouns = get_playbook(role_family).object_nouns

    if _metrics(written) - _metrics(source):
        found.add("quantified")

    if _has(written, _OUTCOME_MARKERS) and not _has(source, _OUTCOME_MARKERS):
        found.add("outcome")

    source_weak_or_absent = not _has(source, _OWNERSHIP_VERBS)
    if _has(written, _OWNERSHIP_VERBS) and source_weak_or_absent:
        found.add("ownership")
    elif _has(source, _WEAK_VERBS) and not _has(written, _WEAK_VERBS):
        found.add("ownership")

    written_objects = _object_tokens(written, extra_nouns=object_nouns)
    source_objects = _object_tokens(source, extra_nouns=object_nouns)
    if written_objects - source_objects:
        found.add("object")

    for keyword in job_keywords or []:
        kw = keyword.strip()
        if len(kw) < 2:
            continue
        if kw.lower() in written.lower() and kw.lower() not in source.lower():
            found.add("jd_aligned")
            break

    # Length signals are weak on their own; only report them when nothing else fired,
    # otherwise every rewrite would carry a redundant "精简/补充" label.
    if not found and source:
        ratio = len(written) / max(len(source), 1)
        if ratio <= 0.8:
            found.add("tightened")
        elif ratio >= 1.25:
            found.add("expanded")

    return [item["id"] for item in TECHNIQUES if item["id"] in found]


def annotate_elevation_map(
    elevation_map: list[dict[str, Any]],
    *,
    job_keywords: list[str] | None = None,
    role_family: str | None = None,
) -> list[dict[str, Any]]:
    """Attach a `techniques` list to every diff entry, in place-safe fashion."""
    annotated: list[dict[str, Any]] = []
    for entry in elevation_map:
        item = dict(entry)
        item["techniques"] = classify_change(
            str(item.get("source_text") or ""),
            str(item.get("written_text") or ""),
            job_keywords=job_keywords,
            role_family=role_family,
        )
        annotated.append(item)
    return annotated


def summarize_techniques(elevation_map: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate technique usage across a draft for the step-3 summary strip."""
    counts: dict[str, int] = {}
    for entry in elevation_map:
        for tid in entry.get("techniques") or []:
            counts[tid] = counts.get(tid, 0) + 1
    out: list[dict[str, Any]] = []
    for item in TECHNIQUES:
        count = counts.get(item["id"], 0)
        if count:
            out.append({**_TECHNIQUE_BY_ID[item["id"]], "count": count})
    return out
