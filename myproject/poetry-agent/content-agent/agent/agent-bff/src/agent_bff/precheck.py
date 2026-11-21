"""Pre-publication checklist: a Python port of the 12 compile rules in
``pipeline/tools/scene-validator/rules.mjs`` (names and ids match).

Two evaluation levels, and the difference is never hidden:

* ``DATA``   rules can be judged from the Java studio-view alone (work-level preconditions).
* ``BUNDLE`` rules need a compiled scene bundle. Without one they are ``NOT_EVALUATED``, never PASS.

``READY_FOR_HUMAN_PUBLISH`` means a human may now consider publishing. It is not publication, and this
module offers no way to publish.
"""
from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PLACEHOLDER_LOCATORS = ("待核查", "待人工", "未核对", "tbd", "todo", "pending")
STEPS = ("read", "arrive", "meet", "return", "recite")
KINDS = ("FACT", "INTERPRETATION", "DRAMATIZATION")
LEVELS = ("L0", "L1", "L2", "L3", "L4")
TERMINAL = "L0-text"

RULES: tuple[tuple[str, str, str], ...] = (
    ("R1", "reference exists", "DATA"),
    ("R2", "published only", "DATA"),
    ("R3", "basis", "DATA"),
    ("R4", "fallback", "BUNDLE"),
    ("R5", "coverage declared", "BUNDLE"),
    ("R6", "unknown dates", "BUNDLE"),
    ("R7", "annotations from base", "DATA"),
    ("R8", "line link", "DATA"),
    ("R9", "hash", "BUNDLE"),
    ("R10", "rights and meaning", "BUNDLE"),
    ("R11", "no pile-up", "DATA"),
    ("R12", "free movement", "BUNDLE"),
)


def is_real_locator(locator: Any) -> bool:
    text = str(locator or "").strip()
    return bool(text) and not any(mark in text.lower() for mark in PLACEHOLDER_LOCATORS)


def load_bundle() -> dict[str, Any] | None:
    """Read ``bundle.json`` from POETRY_BUNDLE_DIR when it is mounted and parses; otherwise None."""
    directory = os.getenv("POETRY_BUNDLE_DIR", "")
    if not directory:
        return None
    path = Path(directory) / "bundle.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


class Facts:
    """What the studio-view says about one work, in the shapes the rules need."""

    def __init__(self, view: dict[str, Any]) -> None:
        self.work = view.get("work") or {}
        self.work_id = self.work.get("id", "")
        self.versions = view.get("versions") or []
        self.lines = view.get("lines") or []
        self.claims = view.get("claims") or []
        self.citations = view.get("citations") or []
        self.backgrounds = view.get("backgrounds") or []
        self.annotations = view.get("annotations") or []
        self.links = view.get("background_lines") or []
        content_status = view.get("content_status_by_id") or {}
        claim_status = view.get("claim_status_by_id") or {}
        version_status = view.get("version_status_by_id") or {}
        self.claim_status = {c.get("id"): c.get("status") for c in self.claims} | dict(claim_status)
        self.content_status = dict(content_status)
        if self.work_id:
            self.content_status.setdefault(self.work_id, self.work.get("status"))
        self.version_status = {v.get("id"): v.get("status") for v in self.versions} | dict(version_status)
        self.source_verification = {s.get("id"): s.get("verification_status") for s in view.get("sources") or []}
        self.source_verification |= dict(view.get("source_verification_by_id") or {})
        self.line_keys = {(str(line.get("version_id")), int(line.get("line_seq", 0))) for line in self.lines}
        self.bg_ids = {b.get("id") for b in self.backgrounds}
        self.claim_ids = {c.get("id") for c in self.claims}
        self.bg_line_counts: dict[str, int] = {}
        for link in self.links:
            self.bg_line_counts[link.get("background_id")] = self.bg_line_counts.get(link.get("background_id"), 0) + 1
        self.checkable_claims = {
            c.get("claim_id") for c in self.citations
            if self.source_verification.get(c.get("source_id")) == "VERIFIED" and is_real_locator(c.get("locator"))
        }

    def published(self, ident: str) -> bool:
        return "PUBLISHED" in (self.content_status.get(ident), self.claim_status.get(ident), self.version_status.get(ident))

    def known(self, ident: str) -> bool:
        return any(ident in table for table in (self.content_status, self.claim_status, self.version_status))


def _result(rule: tuple[str, str, str], status: str, details: list[str]) -> dict[str, Any]:
    return {"id": rule[0], "name": rule[1], "evaluation": rule[2], "status": status, "details": details}


def _verdict(rules: list[dict[str, Any]], shape_failures: list[str]) -> str:
    if shape_failures or any(r["status"] == "FAIL" for r in rules):
        return "BLOCKED"
    if any(r["status"] == "NOT_EVALUATED" for r in rules):
        return "INCOMPLETE"
    return "READY_FOR_HUMAN_PUBLISH"


# ----------------------------------------------------------------------------- bundle walking

def _layers_of(step: dict[str, Any]) -> list[dict[str, Any]]:
    out = list(step.get("layers") or [])
    if isinstance(step.get("roleplay"), dict):
        out += step["roleplay"].get("layers") or []
    for branch in step.get("branches") or []:
        out += _layers_of(branch)
    return out


def _bundle_findings(bundle: dict[str, Any], facts: Facts) -> dict[str, list[str]]:
    fail: dict[str, list[str]] = {rule[0]: [] for rule in RULES}
    unchecked: dict[str, list[str]] = {rule[0]: [] for rule in RULES}
    steps = bundle.get("steps") or []
    layers = [layer for step in steps for layer in _layers_of(step)]
    all_lines = [line for layer in layers for line in layer.get("lines") or []]
    assets = bundle.get("assets") or {}

    # R12 free movement
    for step in steps:
        for flag in ("skip_allowed", "back_allowed"):
            if step.get(flag) is not True:
                fail["R12"].append(f"{step.get('step')} 必须设 {flag}:true")
    # R5 coverage declared
    notice = bundle.get("coverage_notice")
    if not (isinstance(notice, str) and len(notice.strip()) >= 12):
        fail["R5"].append("coverage_notice 必须存在,并说明本轮不覆盖什么(至少 12 字)")
    # R6 unknown dates (only the work's own time precision is visible here)
    precision = (facts.work.get("time_precision") or "").upper()
    unknown_notice = bundle.get("unknown_dates_notice")
    if precision in {"UNKNOWN", "APPROXIMATE"}:
        if not (isinstance(unknown_notice, str) and len(unknown_notice.strip()) >= 6):
            fail["R6"].append(f"作品时间精度为 {precision},bundle 需要 unknown_dates_notice")
    else:
        unchecked["R6"].append("其他被引用实体(人/地/事件)的时间精度不在本作品快照中,未核对")
    # R3 basis
    for step in steps:
        roleplay = step.get("roleplay")
        if isinstance(roleplay, dict) and roleplay.get("declared_as") != "DRAMATIZATION":
            fail["R3"].append(f"{step.get('step')}: roleplay 必须声明 declared_as:\"DRAMATIZATION\"")
    for line in all_lines:
        tag = f"“{str(line.get('text', ''))[:14]}”"
        if line.get("kind") not in KINDS:
            fail["R3"].append(f"台词 {tag} 没有 claim_kind")
        elif line["kind"] == "DRAMATIZATION":
            if not (isinstance(line.get("badge"), str) and len(line["badge"].strip()) >= 2):
                fail["R3"].append(f"演绎台词 {tag} 必须带可见角标")
        else:
            claim_id = (line.get("basis") or {}).get("claim_id")
            if not claim_id:
                fail["R3"].append(f"台词 {tag} 断言 {line['kind']} 却没有 claim_id")
            elif facts.known(claim_id):
                if not facts.published(claim_id):
                    fail["R3"].append(f"claim {claim_id} 未发布")
                if claim_id not in facts.checkable_claims:
                    fail["R3"].append(f"claim {claim_id} 没有可核查引用(已核验来源 + 真实 locator)")
            else:
                unchecked["R3"].append(f"claim {claim_id} 不在本作品快照中,未核对")
    # R4 / R9 / R10 asset rules
    for asset_id, asset in assets.items():
        if asset.get("level") not in LEVELS:
            fail["R4"].append(f"{asset_id} 没有媒体级别")
        cursor, depth = asset, 0
        while isinstance(cursor, dict) and cursor.get("fallback") and depth < 10:
            depth += 1
            next_id = cursor["fallback"][0]
            cursor = assets.get(next_id)
            if cursor is None and next_id != TERMINAL:
                fail["R4"].append(f"{asset_id} 的降级链到 {next_id},它既不是已声明素材也不是 {TERMINAL}")
        # The chain must end at TERMINAL (cursor None); a dict here means it stopped early or looped.
        if isinstance(cursor, dict):
            fail["R4"].append(f"{asset_id} 没有通向 {TERMINAL} 的降级链或链成环")
        if not (isinstance(asset.get("hash"), str) and re.fullmatch(r"[a-f0-9]{12,64}", asset["hash"])):
            fail["R9"].append(f"{asset_id} 没有内容哈希")
        rights = asset.get("rights") or {}
        if not (rights.get("origin") and rights.get("license")):
            fail["R10"].append(f"{asset_id} 没有来源/许可")
        if not (isinstance(asset.get("meaning"), str) and len(asset["meaning"].strip()) >= 8):
            fail["R10"].append(f"{asset_id} 说不清它帮助理解哪一句")
    for layer in layers:
        for ref in layer.get("assets") or []:
            if ref not in assets:
                fail["R4"].append(f"{layer.get('layer')} 引用了未声明的素材 {ref}")
    # R1 / R2 / R11 / R8 / R7 against the work's own ids
    base_ids = {bundle.get("work_id"), bundle.get("text_version_id")}
    base_ids |= {layer.get("bg_id") for layer in layers}
    for ident in sorted(i for i in base_ids if i):
        if facts.known(ident):
            if not facts.published(ident):
                fail["R2"].append(f"{ident} 未发布,未发布内容不得到达学生")
        elif ident in facts.bg_ids:
            if facts.content_status.get(ident) != "PUBLISHED":
                fail["R2"].append(f"{ident} 未发布,未发布内容不得到达学生")
        else:
            unchecked["R1"].append(f"{ident} 不在本作品快照中,未核对存在性")
    version_lines = {seq for version, seq in facts.line_keys if version == str(bundle.get("text_version_id"))}
    for layer in layers:
        for seq in layer.get("line_seqs") or []:
            if int(seq) not in version_lines:
                fail["R8"].append(f"{layer.get('bg_id')} 关联到第 {seq} 句,它在 {bundle.get('text_version_id')} 中不存在")
        if facts.bg_line_counts.get(layer.get("bg_id"), 0) == 0:
            fail["R11"].append(f"{layer.get('bg_id')} 没有绑定任何诗句:不能解释诗句的背景是堆砌,不是教学")
    if bundle.get("glossary_bindings") is not True:
        fail["R7"].append("glossary_bindings 必须为 true")
    annotation_ids = list(bundle.get("annotation_ids") or [])
    annotation_ids += [a for step in steps for a in (step.get("text_side") or {}).get("annotations") or []]
    by_id = {a.get("id"): a for a in facts.annotations}
    for ident in annotation_ids:
        annotation = by_id.get(ident)
        if annotation is None:
            fail["R1"].append(f"注释 {ident} 在底座中不存在")
        elif facts.claim_status.get(annotation.get("claim_id")) != "PUBLISHED":
            fail["R7"].append(f"注释 {ident} 未发布")
    return {**{f"F{k}": v for k, v in fail.items()}, **{f"U{k}": v for k, v in unchecked.items()}}


def _bundle_shape_failures(bundle: dict[str, Any]) -> list[str]:
    missing = [key for key in ("schema_version", "script_id", "script_version", "work_id", "text_version_id",
                               "audiences", "coverage_notice", "steps", "assets") if bundle.get(key) is None]
    out = [f"R0 shape: 缺少 \"{key}\"" for key in missing]
    if not isinstance(bundle.get("steps"), list) or not bundle.get("steps"):
        out.append("R0 shape: steps 必须是非空数组")
    if str(bundle.get("schema_version", "")).split(".")[0] != "1":
        out.append(f"R0 shape: schema_version {bundle.get('schema_version')} 不在 1.x 范围内")
    for step in bundle.get("steps") or []:
        if step.get("step") not in STEPS:
            out.append(f"R0 step: 未知的步骤 \"{step.get('step')}\"")
    return out


# ----------------------------------------------------------------------------- data-level rules

def _data_rule(rule_id: str, facts: Facts) -> tuple[str, list[str]]:
    if rule_id == "R1":
        bad: list[str] = []
        for b in facts.backgrounds:
            if b.get("claim_id") not in facts.claim_ids:
                bad.append(f"背景 {b.get('id')} 的 claim {b.get('claim_id')} 不存在")
        versions = {str(v.get("id")) for v in facts.versions}
        for a in facts.annotations:
            if str(a.get("version_id")) not in versions or (str(a.get("version_id")), int(a.get("line_seq", 0))) not in facts.line_keys:
                bad.append(f"注释 {a.get('id')} 指向不存在的诗句 {a.get('version_id')}#{a.get('line_seq')}")
            if a.get("claim_id") not in facts.claim_ids:
                bad.append(f"注释 {a.get('id')} 的 claim {a.get('claim_id')} 不存在")
        return ("FAIL", bad) if bad else ("PASS", ["作品内的背景/注释引用都能在底座找到"])
    if rule_id == "R2":
        bad = []
        if facts.work.get("status") != "PUBLISHED":
            bad.append(f"作品 {facts.work_id} 当前 {facts.work.get('status')}")
        bad += [f"文本版本 {v.get('id')} 当前 {v.get('status')}" for v in facts.versions if v.get("status") != "PUBLISHED"]
        bad += [f"背景 {b.get('id')} 当前 {facts.content_status.get(b.get('id'), 'UNKNOWN')}"
                for b in facts.backgrounds if facts.content_status.get(b.get("id")) != "PUBLISHED"]
        bad += [f"claim {c.get('id')} 当前 {c.get('status')}" for c in facts.claims if c.get("status") != "PUBLISHED"]
        if not facts.versions:
            bad.append("没有文本版本")
        return ("FAIL", bad) if bad else ("PASS", ["作品、文本版本、背景与 claim 均已发布"])
    if rule_id == "R3":
        bad = [f"claim {c.get('id')}({c.get('claim_kind')})没有可核查引用(已核验来源 + 真实 locator)"
               for c in facts.claims if c.get("claim_kind") != "DRAMATIZATION" and c.get("id") not in facts.checkable_claims]
        if not facts.claims:
            return "NOT_EVALUATED", ["作品没有 claim 可检查"]
        return ("FAIL", bad) if bad else ("PASS", ["每条非演绎 claim 都有可核查引用"])
    if rule_id == "R7":
        bad = [f"注释 {a.get('id')} 的 claim {a.get('claim_id')} 当前 {facts.claim_status.get(a.get('claim_id'), 'UNKNOWN')}"
               for a in facts.annotations if facts.claim_status.get(a.get("claim_id")) != "PUBLISHED"]
        if bad:
            return "FAIL", bad
        note = "尚无注释;本规则不规定数量(数量不足见缺口报告)" if not facts.annotations else "全部注释来自底座且已发布"
        return "PASS", [note]
    if rule_id == "R8":
        if not facts.links:
            return "NOT_EVALUATED", ["没有任何“背景—诗句”关联可检查"]
        bad = []
        for link in facts.links:
            if (str(link.get("version_id")), int(link.get("line_seq", 0))) not in facts.line_keys:
                bad.append(f"背景 {link.get('background_id')} 关联的 {link.get('version_id')}#{link.get('line_seq')} 不存在")
            if link.get("background_id") not in facts.bg_ids:
                bad.append(f"关联指向不存在的背景 {link.get('background_id')}")
        return ("FAIL", bad) if bad else ("PASS", ["所有背景—诗句关联都落在真实诗句上"])
    if rule_id == "R11":
        if not facts.backgrounds:
            return "NOT_EVALUATED", ["作品没有背景可检查"]
        bad = [f"背景 {b.get('id')} 没有绑定任何诗句" for b in facts.backgrounds if facts.bg_line_counts.get(b.get("id"), 0) == 0]
        return ("FAIL", bad) if bad else ("PASS", ["每条背景都解释至少一句诗"])
    return "NOT_EVALUATED", ["需要编译后的 scene bundle 才能评估"]


def run_precheck(work_id: str, view: dict[str, Any], bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    facts = Facts(view)
    now = datetime.now(UTC).isoformat()
    if bundle is not None and str(bundle.get("work_id")) != work_id:
        bundle = None  # a bundle for another work says nothing about this one
    shape_failures: list[str] = []
    findings: dict[str, list[str]] = {}
    if bundle is not None:
        shape_failures = _bundle_shape_failures(bundle)
        findings = _bundle_findings(bundle, facts)
    rules: list[dict[str, Any]] = []
    for rule in RULES:
        rule_id = rule[0]
        data_status, data_details = _data_rule(rule_id, facts)
        if bundle is None:
            rules.append(_result(rule, data_status, data_details if data_status != "NOT_EVALUATED" or rule[2] == "DATA"
                                 else ["需要编译后的 scene bundle 才能评估(未挂载 bundle)"]))
            continue
        failures = findings.get(f"F{rule_id}", [])
        unchecked = findings.get(f"U{rule_id}", [])
        if data_status == "FAIL" or failures:
            rules.append(_result(rule, "FAIL", (data_details if data_status == "FAIL" else []) + failures))
        elif unchecked or (data_status == "NOT_EVALUATED" and rule[2] == "DATA"):
            rules.append(_result(rule, "NOT_EVALUATED", unchecked or data_details))
        elif rule[2] == "BUNDLE" or data_status == "PASS":
            rules.append(_result(rule, "PASS", ["bundle 与底座数据均满足"] if rule[2] == "BUNDLE" else data_details))
        else:
            rules.append(_result(rule, data_status, data_details))
    result: dict[str, Any] = {
        "work_id": work_id,
        "evaluated_at": now,
        "bundle": {"state": "EVALUATED" if bundle is not None else "NOT_AVAILABLE"},
        "rules": rules,
        "verdict": _verdict(rules, shape_failures),
        "note": "READY_FOR_HUMAN_PUBLISH 只表示可以交给发布人判断,不等于已发布;本界面没有发布动作。",
    }
    if bundle is not None:
        result["bundle"].update({"script_id": bundle.get("script_id"), "script_version": bundle.get("script_version")})
        if shape_failures:
            result["bundle"]["shape_failures"] = shape_failures
    return result
