"""Mock Poetry Domain API 的内存业务层。

行为对齐 vvv-poetry 的 PoetryAgentService / PoetryAgentOrchestrationService,以及契约 §3 的新端点。
本模块不含 HTTP 细节;HTTP 信封、令牌、状态码在 mock_domain_api.py。
所有方法返回 snake_case 的普通 dict;旧端点的 camelCase 渲染由 HTTP 层按 MOCK_JSON_NAMING 处理。
"""
from __future__ import annotations

import copy
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import seed as seed_data

# ---- 词表(与 Vocabulary.java 一致)----
AUDIENCES = {"PRIMARY", "JUNIOR", "SENIOR"}
CERTAINTIES = {"KNOWN", "LIKELY", "DISPUTED", "UNKNOWN"}
ANNOTATION_KINDS = {"WORD", "PHRASE", "ALLUSION", "IMAGE", "RHYME", "OTHER"}
VERIFICATION_STATUSES = {"PENDING", "VERIFIED", "REJECTED"}
LAYERS = ["SCENE", "CITY", "WORLD", "PERSON"]
SOURCE_KINDS = {"OFFICIAL_HISTORY", "YEAR_BOOK", "ANTHOLOGY", "TEXTBOOK", "MODERN_STUDY",
                "DIGITIZED_TEXT", "ONLINE_ENTRY", "OTHER"}
RELIABILITIES = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}

CHANGE_TYPES = {"GAP_REPORT", "ANNOTATION", "BACKGROUND", "CLAIM", "SCRIPT"}
CLASSIFICATIONS = {"DRAFT", "INTERPRETATION", "UNKNOWN"}
TASK_TYPES = {"GAP_ANALYSIS", "ANNOTATION_DRAFT", "SCRIPT_DRAFT", "COMPILE_TRIAGE", "CONTENT_REVIEW"}
ROLES = {"CONTENT_EDITOR", "HISTORICAL_REVIEWER", "RELEASE_MANAGER", "PLATFORM_ADMIN"}
RUN_STATES = {"RUNNING", "WAITING_FOR_RUNTIME", "AWAITING_REVIEW", "COMPLETED", "FAILED"}
STUDIO_ROLES = {"HISTORICAL_REVIEWER", "PLATFORM_ADMIN", "CONTENT_EDITOR"}
SOURCE_REVIEW_ROLES = {"HISTORICAL_REVIEWER", "PLATFORM_ADMIN"}

AUDIT_TOTAL_CHECKS = 106  # DRAFT 种子上 106 项审计全为 0;Mock 不重算。

_ID_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,63}")
_WORK_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{1,127}")
_FINGERPRINT = re.compile(r"[a-f0-9]{64}")
_REVIEWER_BLOCKED = re.compile(r"agent|bot|deerflow|system|mcp|llm|ai", re.IGNORECASE)
_PLACEHOLDER = re.compile(r"^\s*(待|未核对|tbd)", re.IGNORECASE)
_GATE_BLOCKED_NAMES = {"LIVE-PROBE", "SYSTEM", "ROOT", "NULL"}


class Rejected(Exception):
    """Java 的 Rejected:HTTP 400 + AgentResponse.rejected。"""


class Conflict(Exception):
    """Java 的 Conflict:HTTP 409 + AgentResponse.conflict;extra 并入 data。"""

    def __init__(self, message: str, extra: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.extra = extra or {}


class Invalid(Exception):
    """PoetryDraftService.Invalid:PoetryAuthoringAdvice 会渲染成 {errno,data,error},HTTP 400。"""


class NotFound(Exception):
    """studio 端点:HTTP 404。"""


class Forbidden(Exception):
    """studio 端点:角色不允许,HTTP 403。"""


class Internal(Exception):
    """数据库唯一键冲突之类 Java 里会变成未处理异常(500)的情形。"""


@dataclass(frozen=True)
class Ctx:
    run_id: str
    mandate_id: str
    key: str
    role: str


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def fld(body: Any, name: str, default: Any = None) -> Any:
    """读取请求字段,同时接受 snake_case 与 camelCase(Jackson 默认只认 camelCase,MCP 发 snake_case)。"""
    if not isinstance(body, dict):
        return default
    if name in body:
        return body[name]
    head, *rest = name.split("_")
    camel = head + "".join(p.capitalize() for p in rest)
    return body.get(camel, default)


def text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def as_int(value: Any, default: int = -1) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value == int(value):
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
        return int(value.strip())
    return default


def locator_state(locator: str | None) -> str:
    if locator is None or not locator.strip():
        return "MISSING"
    if _PLACEHOLDER.match(locator):
        return "PLACEHOLDER"
    return "SET"


def page(rows: list[Any], limit_raw: str | None, offset_raw: str | None) -> dict[str, Any]:
    limit, offset = 50, 0
    if limit_raw not in (None, ""):
        limit = as_int(limit_raw, -1)
        if limit < 1:
            raise Rejected("limit must be a positive integer")
        limit = min(limit, 200)
    if offset_raw not in (None, ""):
        offset = as_int(offset_raw, -1)
        if offset < 0:
            raise Rejected("offset must be a non-negative integer")
    items = rows[offset:offset + limit]
    return {"items": copy.deepcopy(items), "limit": limit, "offset": offset,
            "has_more": offset + limit < len(rows)}


def reviewer_problems(reviewer: str | None) -> list[str]:
    """PublicationGate.reviewerProblems。"""
    if blank(reviewer):
        return ["Human reviewer is required"]
    name = reviewer.strip()  # type: ignore[union-attr]
    problems = []
    if name.upper().startswith("DEMO"):
        problems.append(f"Rehearsal marker cannot publish: {name}")
    if name.upper() in _GATE_BLOCKED_NAMES:
        problems.append(f"Machine identity cannot publish: {name}")
    return problems


def source_problems(reviewer: str | None, kind: str | None, reliability: str | None) -> list[str]:
    problems = reviewer_problems(reviewer)
    if kind not in SOURCE_KINDS:
        problems.append("source_kind missing or outside vocabulary")
    if reliability not in RELIABILITIES:
        problems.append("reliability missing or outside vocabulary")
    return problems


class Store:
    def __init__(self, v004_annotations: bool = False) -> None:
        self.v004_annotations = v004_annotations
        self.reset()

    # ------------------------------------------------------------------ 初始化
    def reset(self) -> None:
        s = seed_data.build_seed(self.v004_annotations)
        self.contents: dict[str, dict] = s["contents"]
        self.works: dict[str, dict] = s["works"]
        self.versions: dict[str, dict] = s["versions"]
        self.lines: dict[tuple[str, int], dict] = s["lines"]
        self.sources: dict[str, dict] = s["sources"]
        self.claims: dict[str, dict] = s["claims"]
        self.citations: dict[tuple[str, str], dict] = s["citations"]
        self.backgrounds: dict[str, dict] = s["backgrounds"]
        self.background_lines: list[dict] = s["background_lines"]
        self.annotations: dict[str, dict] = s["annotations"]
        self.coverage_rows: list[dict] = s["coverage_rows"]
        self.tasks: dict[str, dict] = {}
        self.runs: dict[str, dict] = {}
        self.profiles: dict[str, dict] = {}
        self.mandates: dict[tuple[str, str], dict] = {}
        self.events: list[dict] = []
        self.proposals: dict[str, dict] = {}
        self.reviews: dict[str, dict] = {}
        self.receipts: dict[tuple[str, str], str] = {}
        self.compile_requests: dict[str, dict] = {}
        self.items: dict[tuple[str, int], dict] = {}
        self.check_log: list[dict] = []
        self._event_seq = 0

    def counts(self) -> dict[str, int]:
        return {"works": len(self.works), "lines": len(self.lines), "claims": len(self.claims),
                "citations": len(self.citations), "sources": len(self.sources),
                "annotations": len(self.annotations)}

    # ------------------------------------------------------------------ 作品读取
    def _require_work(self, work_id: Any) -> dict:
        if blank(work_id) or not _WORK_ID_PATTERN.fullmatch(work_id):
            raise Rejected("invalid work id")
        row = self.contents.get(work_id)
        if row is None or row["entity_type"] != "WORK":
            raise Rejected("work not found")
        return row

    def _work_versions(self, work_id: str) -> list[dict]:
        return sorted((v for v in self.versions.values() if v["work_id"] == work_id), key=lambda v: v["id"])

    def _work_lines(self, work_id: str) -> list[dict]:
        ids = {v["id"] for v in self._work_versions(work_id)}
        rows = [r for (vid, _), r in self.lines.items() if vid in ids]
        return sorted(rows, key=lambda r: (r["version_id"], r["line_seq"]))

    def _strict_claims(self, work_id: str) -> list[dict]:
        rows = [c for c in self.claims.values() if c["subject_id"] == work_id]
        return sorted(rows, key=lambda c: (c["property_key"], c["id"]))

    def _work_backgrounds(self, work_id: str) -> list[dict]:
        rows = [b for b in self.backgrounds.values() if b["work_id"] == work_id]
        return sorted(rows, key=lambda b: (b["layer"], b["id"]))

    def _work_annotations(self, work_id: str) -> list[dict]:
        ids = {v["id"] for v in self._work_versions(work_id)}
        rows = [a for a in self.annotations.values() if a["version_id"] in ids]
        return sorted(rows, key=lambda a: (a["version_id"], a["line_seq"], a["id"]))

    def _citations_of(self, claim_ids: set[str]) -> list[dict]:
        rows = [c for c in self.citations.values() if c["claim_id"] in claim_ids]
        return sorted(rows, key=lambda c: (c["claim_id"], c["source_id"]))

    def _citation_rows(self, claim_ids: set[str]) -> list[dict]:
        out = []
        for c in self._citations_of(claim_ids):
            src = self.sources.get(c["source_id"])
            if src is None:
                continue
            out.append({"claim_id": c["claim_id"], "source_id": c["source_id"], "locator": c["locator"],
                        "evidence_excerpt": c["evidence_excerpt"], "verification_status": src["verification_status"]})
        return out

    def _sources_for(self, work_id: str, claim_ids: set[str]) -> list[dict]:
        ids = {v["source_id"] for v in self._work_versions(work_id) if v["source_id"]}
        ids |= {c["source_id"] for c in self._citations_of(claim_ids)}
        return [self._source_row(self.sources[i]) for i in sorted(ids) if i in self.sources]

    @staticmethod
    def _source_row(s: dict) -> dict:
        keys = ("id", "title", "author", "edition", "url", "rights_note", "source_kind", "reliability",
                "verification_status")
        return {k: s[k] for k in keys}

    def snapshot(self, work_id: str) -> dict:
        """与 PoetryAgentService.snapshot 一致:claims/citations 只取 subject_id = 作品 的 claim。"""
        work = self._require_work(work_id)
        claims = self._strict_claims(work_id)
        ids = {c["id"] for c in claims}
        info = self.works.get(work_id, {"id": work_id, "genre": None, "dynasty_id": None, "creation_place_id": None})
        data = {
            "work": {k: work[k] for k in ("id", "entity_type", "slug", "title", "summary", "start_year",
                                           "end_year", "time_precision", "status", "revision", "reviewed_by")},
            "work_info": dict(info),
            "versions": [dict(v) for v in self._work_versions(work_id)],
            "lines": [dict(r) for r in self._work_lines(work_id)],
            "claims": [dict(c) for c in claims],
            "citations": self._citation_rows(ids),
            "backgrounds": [dict(b) for b in self._work_backgrounds(work_id)],
            "annotations": [dict(a) for a in self._work_annotations(work_id)],
            "sources": self._sources_for(work_id, ids),
        }
        return copy.deepcopy(data)

    def gaps(self, work_id: str) -> dict:
        """与 PoetryAgentService.gaps 一致(code / severity / message / target_ref)。"""
        self._require_work(work_id)
        out: list[dict] = []

        def gap(code: str, severity: str, message: str) -> None:
            out.append({"code": code, "severity": severity, "message": message, "target_ref": work_id})

        versions = self._work_versions(work_id)
        if not versions:
            gap("TEXT_VERSION_MISSING", "HIGH", "作品尚无文本定本草稿。")
        if not self._work_lines(work_id):
            gap("TEXT_LINES_MISSING", "HIGH", "文本定本没有逐句行，不能形成可核验阅读路径。")
        unverified = 0
        for claim in self._strict_claims(work_id):
            ok = False
            for c in self._citations_of({claim["id"]}):
                src = self.sources.get(c["source_id"])
                if src and src["verification_status"] == "VERIFIED" and c["locator"] and c["locator"].strip():
                    ok = True
            if not ok:
                unverified += 1
        if unverified > 0:
            gap("CLAIM_VERIFIED_CITATION_MISSING", "HIGH", f"有 {unverified} 条 Claim 缺少已核验且带 locator 的出处。")
        pending = sum(1 for v in versions
                      if v["source_id"] in self.sources
                      and self.sources[v["source_id"]]["verification_status"] != "VERIFIED")
        if pending > 0:
            gap("TEXT_SOURCE_NOT_VERIFIED", "HIGH",
                f"有 {pending} 个文本定本来源仍非 VERIFIED；本报告不要求 Agent 验证来源。")
        layers = {b["layer"] for b in self._work_backgrounds(work_id)}
        for layer in LAYERS:
            if layer not in layers:
                gap("BACKGROUND_LAYER_MISSING", "MEDIUM", f"缺少 {layer} 背景草稿。")
        if len(self._work_annotations(work_id)) < 4:
            gap("ANNOTATION_COVERAGE_LOW", "MEDIUM", "当前注释少于 4 条；数量不是发布条件，需由人工判断学习价值。")
        return {"work_id": work_id, "gaps": out, "audit_checks": AUDIT_TOTAL_CHECKS, "audit_non_zero": []}

    # ------------------------------------------------------------------ 提案(agent 面)
    def _ensure_mandate(self, c: Ctx, work_id: str) -> None:
        self.mandates.setdefault((c.run_id, c.mandate_id),
                                 {"work_id": work_id, "role": c.role, "status": "ACTIVE"})

    def _require_mandate(self, c: Ctx, work_id: str) -> None:
        if blank(c.run_id) or blank(c.mandate_id) or blank(c.key):
            raise Rejected("run, mandate and idempotency headers are required")
        m = self.mandates.get((c.run_id, c.mandate_id))
        if m is None or m["work_id"] != work_id or m["status"] != "ACTIVE":
            raise Rejected("active mandate not found for this work")

    def _validate_proposal(self, proposal: Any, work_id: str) -> None:
        if (not isinstance(proposal, dict) or as_int(proposal.get("schema_version"), -1) != 1
                or proposal.get("status") != "DRAFT"):
            raise Rejected("proposal must be a schema_version=1 DRAFT object")
        if blank(text(proposal.get("summary"))) or blank(text(proposal.get("human_review_question"))):
            raise Rejected("proposal summary and human_review_question are required")
        changes = proposal.get("changes")
        if not isinstance(changes, list) or not changes or len(changes) > 50:
            raise Rejected("proposal changes must contain 1..50 items")
        for change in changes:
            if (not isinstance(change, dict) or change.get("change_type") not in CHANGE_TYPES
                    or blank(text(change.get("body")))):
                raise Rejected("invalid proposal change")
            if change.get("classification") not in CLASSIFICATIONS:
                raise Rejected("invalid change classification")
            payload = change.get("draft_payload")
            if payload is not None and (not isinstance(payload, dict)
                                        or payload.get("operation") != "CREATE_ANNOTATION"):
                raise Rejected("only CREATE_ANNOTATION is an executable v1 operation")
        self._require_work(work_id)

    def create_proposal(self, c: Ctx, body: Any) -> tuple[str, dict, list[str]]:
        work_id = fld(body, "work_id")
        proposal = fld(body, "proposal")
        self._require_work(work_id)
        self._validate_proposal(proposal, work_id)
        given = fld(body, "proposal_id")
        pid = given if not blank(given) else "proposal_" + uuid.uuid4().hex
        existing = self.receipts.get(("CREATE_PROPOSAL", c.key))
        if existing is not None:
            return "ok", {"proposal_id": existing, "idempotent": True}, [f"agent-receipt:{existing}"]
        self._ensure_mandate(c, work_id)
        if pid in self.proposals:
            raise Conflict("proposal or idempotency key already exists")
        self.proposals[pid] = {
            "id": pid, "work_id": work_id, "run_id": c.run_id, "mandate_id": c.mandate_id,
            "proposal_json": json.dumps(proposal, ensure_ascii=False), "status": "DRAFT",
            "review_status": "PENDING", "review_id": None, "reviewed_by": None, "reviewed_at": None,
            "review_comment": None, "created_by": "DEERFLOW", "created_at": now_iso(), "applied_at": None,
        }
        self.receipts[("CREATE_PROPOSAL", c.key)] = pid
        return "review", {"proposal_id": pid, "stored_status": "DRAFT", "review_status": "PENDING"}, \
            [f"agent-proposal:{pid}"]

    def review_proposal(self, c: Ctx, pid: str, body: Any) -> tuple[str, dict, list[str]]:
        p = self.proposals.get(pid)
        if p is None:
            raise Rejected("proposal not found")
        self._require_mandate(c, p["work_id"])
        decision = fld(body, "decision")
        review_id = text(fld(body, "review_id"))
        reviewer_id = text(fld(body, "reviewer_id"))
        comment = text(fld(body, "comment"))
        if decision not in ("APPROVE", "REJECT"):
            raise Rejected("decision must be APPROVE or REJECT")
        if blank(review_id) or blank(reviewer_id):
            raise Rejected("review_id and reviewer_id are required")
        receipt = self.receipts.get(("REVIEW_PROPOSAL", c.key))
        if receipt is not None:
            return "ok", {"proposal_id": pid, "review_id": receipt, "idempotent": True}, [f"agent-review:{receipt}"]
        if p["review_status"] != "PENDING":
            raise Conflict("proposal is no longer pending review")
        if any(q["review_id"] == review_id for q in self.proposals.values()):
            raise Internal("duplicate review_id")
        new_status = "APPROVED" if decision == "APPROVE" else "REJECTED"
        p.update(review_status=new_status, review_id=review_id, reviewed_by=reviewer_id,
                 reviewed_at=now_iso(), review_comment=comment)
        self.reviews[review_id] = {"id": review_id, "proposal_id": pid, "reviewer_id": reviewer_id,
                                   "decision": decision, "comment": comment, "created_at": now_iso()}
        self.receipts[("REVIEW_PROPOSAL", c.key)] = review_id
        return "ok", {"proposal_id": pid, "review_status": new_status}, [f"agent-review:{review_id}"]

    def apply(self, c: Ctx, pid: str, body: Any) -> tuple[str, dict, list[str]]:
        p = self.proposals.get(pid)
        if p is None:
            raise Rejected("proposal not found")
        self._require_mandate(c, p["work_id"])
        if p["review_status"] != "APPROVED":
            raise Conflict("proposal needs an APPROVED human review")
        review_id = text(fld(body, "review_id"))
        if blank(review_id):
            raise Rejected("review_id is required")
        if review_id != p["review_id"]:
            raise Rejected("review_id does not belong to this proposal")
        receipt = self.receipts.get(("APPLY_PROPOSAL", c.key))
        if receipt is not None:
            return "ok", {"proposal_id": pid, "application_id": receipt, "idempotent": True}, \
                [f"agent-receipt:{receipt}"]
        try:
            proposal = json.loads(p["proposal_json"])
        except ValueError as exc:
            raise Rejected("stored proposal JSON is unreadable") from exc
        decisions = {idx: d["decision"] for (q, idx), d in self.items.items() if q == pid}
        backup = (copy.deepcopy(self.claims), copy.deepcopy(self.citations), copy.deepcopy(self.annotations))
        applied: list[str] = []
        retained: list[str] = []
        try:
            for idx, change in enumerate(proposal.get("changes", [])):
                payload = change.get("draft_payload")
                if payload is None:
                    retained.append(str(change.get("change_type")))
                    continue
                operation = text(payload.get("operation")) or ""
                if operation != "CREATE_ANNOTATION":
                    raise Rejected(f"unsupported DRAFT operation: {operation}")
                # D7:存在逐项记录时只执行被明确 APPROVE 的可执行项;没有任何逐项记录则全部执行(旧行为)。
                if decisions and decisions.get(idx) != "APPROVE":
                    continue
                annotation = self._annotation_from_payload(payload)
                self._create_annotation(annotation)
                applied.append("CREATE_ANNOTATION:" + annotation["id"])
            if p["status"] != "DRAFT":
                raise Conflict("proposal cannot transition to APPLIED")
        except Exception:
            self.claims, self.citations, self.annotations = backup
            raise
        p["status"] = "APPLIED"
        p["applied_at"] = now_iso()
        application_id = "application_" + uuid.uuid4().hex
        self.receipts[("APPLY_PROPOSAL", c.key)] = application_id
        data = {"proposal_id": pid, "application_id": application_id, "content_state": "DRAFT_ONLY",
                "applied_operations": applied, "retained_editorial_changes": retained}
        return "ok", data, [f"agent-application:{application_id}", f"agent-review:{review_id}"]

    @staticmethod
    def _annotation_from_payload(payload: dict) -> dict:
        def req(key: str) -> str:
            value = payload.get(key)
            if blank(text(value)):
                raise Rejected(f"draft_payload.{key} is required")
            return text(value)  # type: ignore[return-value]

        def nullable(key: str) -> str | None:
            return text(payload.get(key))

        ann_id = req("id")
        version_id = req("version_id")
        seq = payload.get("line_seq")
        if isinstance(seq, bool) or not isinstance(seq, (int, float)) or seq != int(seq):
            raise Rejected("draft_payload.line_seq must be an integer")
        return {"id": ann_id, "version_id": version_id, "line_seq": int(seq),
                "annotation_kind": req("annotation_kind"), "audience": req("audience"),
                "content": req("content"), "claim_id": req("claim_id"), "claim_value": req("claim_value"),
                "certainty": req("certainty"), "source_id": nullable("source_id"),
                "locator": nullable("locator")}

    def _create_annotation(self, a: dict) -> None:
        """PoetryTextService.createAnnotation:词表、存在性、claim 唯一性校验;失败抛 Invalid。"""
        for value in (a["id"], a["version_id"]):
            if not _ID_PATTERN.fullmatch(value or ""):
                raise Invalid(f"id must match {_ID_PATTERN.pattern} (got: {value})")
        if (a["version_id"], a["line_seq"]) not in self.lines:
            raise Invalid(f"line not found (先录行，再注释): {a['version_id']}#{a['line_seq']}")
        if blank(a["content"]):
            raise Invalid("annotation content is required")
        kind = a["annotation_kind"].strip().upper()
        if kind not in ANNOTATION_KINDS:
            raise Invalid(f"annotation_kind outside vocabulary: {a['annotation_kind']}")
        audience = a["audience"].strip().upper()
        if audience not in AUDIENCES:
            raise Invalid(f"audience outside vocabulary: {a['audience']}")
        if not _ID_PATTERN.fullmatch(a["claim_id"] or ""):
            raise Invalid(f"id must match {_ID_PATTERN.pattern} (got: {a['claim_id']})")
        if a["claim_id"] in self.claims:
            raise Invalid(f"claim id already exists: {a['claim_id']}")
        if blank(a["claim_value"]):
            raise Invalid("claim value is required")
        certainty = a["certainty"].strip().upper() if a["certainty"] else "KNOWN"
        if certainty not in CERTAINTIES:
            raise Invalid(f"certainty outside vocabulary: {a['certainty']}")
        if a["id"] in self.annotations:
            raise Invalid(f"annotation id already exists: {a['id']}")
        work_id = self.versions[a["version_id"]]["work_id"]
        self.claims[a["claim_id"]] = {
            "id": a["claim_id"], "subject_id": work_id, "property_key": "annotation." + kind,
            "value_text": a["claim_value"].strip(), "claim_kind": "INTERPRETATION",
            "certainty": certainty, "status": "DRAFT"}
        self.annotations[a["id"]] = {
            "id": a["id"], "version_id": a["version_id"], "line_seq": a["line_seq"],
            "annotation_kind": kind, "audience": audience, "content": a["content"].strip(),
            "claim_id": a["claim_id"]}
        if not blank(a["source_id"]):
            if a["source_id"] not in self.sources:
                raise Invalid(f"source not found: {a['source_id']}")
            if blank(a["locator"]):
                raise Invalid("locator is required with a source")
            self.citations[(a["claim_id"], a["source_id"])] = {
                "claim_id": a["claim_id"], "source_id": a["source_id"],
                "locator": a["locator"].strip(), "evidence_excerpt": None}

    def request_compile(self, c: Ctx, work_id: str, body: Any) -> tuple[str, dict, list[str]]:
        self._require_work(work_id)
        self._require_mandate(c, work_id)
        version = text(fld(body, "script_version"))
        if blank(version):
            raise Rejected("script_version is required")
        receipt = self.receipts.get(("REQUEST_COMPILE", c.key))
        if receipt is not None:
            return "review", {"compile_request_id": receipt, "idempotent": True}, [f"compile-request:{receipt}"]
        report = self.gaps(work_id)
        cid = "compile_" + uuid.uuid4().hex
        state = "PENDING_REVIEW" if not report["gaps"] else "BLOCKED"
        reason = ("Agent requested eligibility review; this is not compilation or publication."
                  if not report["gaps"] else "Gap report must be reviewed before compiler eligibility.")
        self.compile_requests[cid] = {"id": cid, "work_id": work_id, "script_version": version,
                                      "status": state, "reason": reason}
        self.receipts[("REQUEST_COMPILE", c.key)] = cid
        return "review", {"compile_request_id": cid, "state": state, "reason": reason}, [f"compile-request:{cid}"]

    # ------------------------------------------------------------------ 编排(任务/运行/事件)
    @staticmethod
    def _require_id(value: Any, prefix: str) -> None:
        if blank(value) or not value.startswith(prefix) or len(value) > 64:
            raise Rejected(f"invalid {prefix} identifier")

    @staticmethod
    def _nullable(value: Any, limit: int) -> str | None:
        value = text(value)
        if value is not None and len(value) > limit:
            raise Rejected("field too long")
        return value

    def task(self, task_id: str) -> dict:
        row = self.tasks.get(task_id)
        if row is None:
            raise Rejected("task not found")
        return dict(row)

    def run(self, run_id: str) -> dict:
        row = self.runs.get(run_id)
        if row is None:
            raise Rejected("run not found")
        task = self.tasks[row["task_id"]]
        out = dict(row)
        out.update(work_id=task["work_id"], requested_by=task["requested_by"],
                   requested_role=task["requested_role"])
        return out

    def _task_state(self, task_id: str, status: str, run_id: str) -> None:
        self.tasks[task_id].update(status=status, active_run_id=run_id, updated_at=now_iso())

    def create_task(self, body: Any) -> dict:
        task_id = text(fld(body, "task_id"))
        work_id = fld(body, "work_id")
        self._require_id(task_id, "task_")
        self._require_work(work_id)
        task_type = fld(body, "task_type")
        role = fld(body, "requested_role")
        title = text(fld(body, "title"))
        instructions = text(fld(body, "instructions"))
        requested_by = text(fld(body, "requested_by"))
        profile = text(fld(body, "requested_profile"))
        if task_type not in TASK_TYPES:
            raise Rejected("unsupported task type")
        if role not in ROLES:
            raise Rejected("unsupported requested role")
        if blank(title) or len(title) > 200 or blank(instructions) or len(instructions) > 8000:  # type: ignore[arg-type]
            raise Rejected("task title or instructions invalid")
        if (blank(requested_by) or len(requested_by) > 100  # type: ignore[arg-type]
                or blank(profile) or len(profile) > 64):  # type: ignore[arg-type]
            raise Rejected("task actor or profile invalid")
        if task_id in self.tasks:
            raise Conflict("task already exists")
        self.tasks[task_id] = {  # type: ignore[index]
            "task_id": task_id, "work_id": work_id, "title": title, "task_type": task_type,
            "status": "CREATED", "requested_by": requested_by, "requested_role": role,
            "instructions": instructions, "requested_profile": profile, "active_run_id": None,
            "created_at": now_iso(), "updated_at": None}
        return self.task(task_id)  # type: ignore[arg-type]

    def create_run(self, task_id: str, body: Any) -> dict:
        task = self.task(task_id)
        run_id = text(fld(body, "run_id"))
        mandate_id = text(fld(body, "mandate_id"))
        self._require_id(run_id, "run_")
        self._require_id(mandate_id, "mandate_")
        if run_id in self.runs:
            raise Conflict("run already exists")
        runtime = fld(body, "runtime")
        if runtime not in ("DEERFLOW", "STUB"):
            raise Rejected("unsupported runtime")
        name = text(fld(body, "profile_name"))
        fingerprint = text(fld(body, "profile_fingerprint"))
        manifest = fld(body, "profile_manifest")
        if blank(name) or blank(fingerprint) or not _FINGERPRINT.fullmatch(fingerprint or "") \
                or not isinstance(manifest, dict):
            raise Rejected("profile identity invalid")
        # 与 Java 一致(审查项 A-07):一个任务同一时刻只能有一个活动运行,占用是原子的。
        if task["status"] == "RUNNING":
            raise Conflict("task already has an active run")
        self.profiles.setdefault(fingerprint, {"name": name, "manifest": manifest})  # type: ignore[arg-type]
        now = now_iso()
        self.runs[run_id] = {  # type: ignore[index]
            "run_id": run_id, "task_id": task_id, "mandate_id": mandate_id, "runtime": runtime,
            "profile_name": name, "profile_fingerprint": fingerprint, "status": "WAITING_FOR_RUNTIME",
            "runtime_thread_id": None, "runtime_run_id": None, "reason": None,
            "created_at": now, "updated_at": None}
        self.mandates[(run_id, mandate_id)] = {"work_id": task["work_id"], "role": task["requested_role"],  # type: ignore[index]
                                               "status": "ACTIVE"}
        self._task_state(task_id, "RUNNING", run_id)  # type: ignore[arg-type]
        self.append_event(run_id, "RUN_CREATED",  # type: ignore[arg-type]
                          {"task_id": task_id, "mandate_id": mandate_id, "runtime": runtime})
        return self.run(run_id)  # type: ignore[arg-type]

    def admit_run(self, run_id: str, body: Any) -> dict:
        self.run(run_id)
        status = fld(body, "status")
        if status not in RUN_STATES:
            raise Rejected("unsupported run state")
        thread = self._nullable(fld(body, "runtime_thread_id"), 128)
        runtime_run = self._nullable(fld(body, "runtime_run_id"), 128)
        reason = self._nullable(fld(body, "reason"), 4000)
        self.runs[run_id].update(status=status, runtime_thread_id=thread, runtime_run_id=runtime_run,
                                 reason=reason, updated_at=now_iso())
        self._task_state(self.runs[run_id]["task_id"], status, run_id)
        self.append_event(run_id, "RUNTIME_ADMISSION", {
            "status": status, "runtime_thread_id": thread or "", "runtime_run_id": runtime_run or "",
            "reason": reason or ""})
        return self.run(run_id)

    def change_run_state(self, run_id: str, body: Any) -> dict:
        current = self.run(run_id)
        status = fld(body, "status")
        if status not in RUN_STATES:
            raise Rejected("unsupported run state")
        reason = self._nullable(fld(body, "reason"), 4000)
        self.runs[run_id].update(status=status, reason=reason, updated_at=now_iso())
        self._task_state(current["task_id"], status, run_id)
        self.append_event(run_id, "RUN_STATE_CHANGED", {"status": status, "reason": reason or ""})
        return self.run(run_id)

    def append_event(self, run_id: str, event_type: Any, payload: Any) -> None:
        self.run(run_id)
        if blank(event_type) or len(event_type) > 64:
            raise Rejected("event type invalid")
        self._event_seq += 1
        self.events.append({
            "event_id": self._event_seq, "run_id": run_id, "event_type": event_type,
            "payload_json": json.dumps(payload if payload is not None else {}, ensure_ascii=False),
            "occurred_at": now_iso()})

    def list_events(self, run_id: str, after: int) -> list[dict]:
        self.run(run_id)
        if after < 0:
            raise Rejected("after_event_id invalid")
        rows = [e for e in self.events if e["run_id"] == run_id and e["event_id"] > after]
        return copy.deepcopy(rows[:250])

    def proposal(self, pid: str) -> dict:
        p = self.proposals.get(pid)
        run = self.runs.get(p["run_id"]) if p else None
        if p is None or run is None:  # 与 Java 的 JOIN poetry_agent_run 一致
            raise Rejected("proposal not found")
        return {
            "proposal_id": p["id"], "work_id": p["work_id"], "run_id": p["run_id"],
            "mandate_id": p["mandate_id"], "proposal_json": p["proposal_json"], "status": p["status"],
            "review_status": p["review_status"], "review_id": p["review_id"],
            "created_at": p["created_at"], "applied_at": p["applied_at"], "task_id": run["task_id"]}

    # ------------------------------------------------------------------ 契约 §3.1 新读端点
    def list_tasks(self, q: dict[str, str | None]) -> dict:
        rows = [t for t in reversed(list(self.tasks.values()))
                if all(q.get(k) in (None, "") or t[col] == q[k]
                       for k, col in (("work_id", "work_id"), ("status", "status"), ("task_type", "task_type")))]
        return page(rows, q.get("limit"), q.get("offset"))

    def list_runs(self, task_id: str) -> dict:
        self.task(task_id)
        rows = [self.run(r["run_id"]) for r in reversed(list(self.runs.values())) if r["task_id"] == task_id]
        return {"items": rows}

    def list_proposals(self, q: dict[str, str | None]) -> dict:
        rows = []
        for p in reversed(list(self.proposals.values())):
            run = self.runs.get(p["run_id"])
            if run is None:
                continue
            row = {
                "proposal_id": p["id"], "work_id": p["work_id"], "run_id": p["run_id"],
                "task_id": run["task_id"], "mandate_id": p["mandate_id"], "status": p["status"],
                "review_status": p["review_status"], "review_id": p["review_id"],
                "reviewed_by": p["reviewed_by"], "review_comment": p["review_comment"],
                "created_at": p["created_at"], "applied_at": p["applied_at"],
                "proposal_json": p["proposal_json"]}
            if all(q.get(k) in (None, "") or row[k] == q[k]
                   for k in ("work_id", "status", "review_status", "run_id", "task_id")):
                rows.append(row)
        return page(rows, q.get("limit"), q.get("offset"))

    def proposal_items(self, pid: str) -> dict:
        if pid not in self.proposals:
            raise Rejected("proposal not found")
        rows = sorted(((idx, d) for (q, idx), d in self.items.items() if q == pid), key=lambda x: x[0])
        return {"items": [{"item_index": idx, "decision": d["decision"], "reviewer": d["reviewer"],
                           "comment": d["comment"], "created_at": d["created_at"]} for idx, d in rows]}

    def _related_claim_ids(self, work_id: str) -> set[str]:
        """新端点(coverage / studio-view / works)用的 claim 范围:作品自身 + 其背景的 claim。

        旧的 snapshot 严格只取 subject_id = 作品(与 Java 一致),因此看不到背景 claim;
        Studio 要渲染四层背景的"史实/解释/演绎/未考"态,必须看到它们,所以新端点放宽到这里。
        """
        bg_ids = {b["id"] for b in self._work_backgrounds(work_id)}
        return {c["id"] for c in self.claims.values() if c["subject_id"] == work_id or c["subject_id"] in bg_ids}

    def _coverage_scope(self, work_id: str) -> tuple[list[dict], list[dict], list[dict]]:
        ids = self._related_claim_ids(work_id)
        claims = sorted((self.claims[i] for i in ids), key=lambda c: (c["property_key"], c["id"]))
        return [dict(c) for c in claims], self._citation_rows(ids), self._sources_for(work_id, ids)

    def list_works(self, q: dict[str, str | None]) -> dict:
        rows = []
        for wid in sorted(w for w, c in self.contents.items() if c["entity_type"] == "WORK"):
            content, info = self.contents[wid], self.works.get(wid, {})
            claims, _, sources = self._coverage_scope(wid)
            rows.append({
                "work_id": wid, "title": content["title"], "status": content["status"],
                "genre": info.get("genre"), "dynasty_id": info.get("dynasty_id"),
                "line_count": len(self._work_lines(wid)), "version_count": len(self._work_versions(wid)),
                "background_count": len(self._work_backgrounds(wid)),
                "annotation_count": len(self._work_annotations(wid)), "claim_count": len(claims),
                "pending_source_count": sum(1 for s in sources if s["verification_status"] == "PENDING")})
        return page(rows, q.get("limit"), q.get("offset"))

    def coverage(self, work_id: str) -> dict:
        content = self._require_work(work_id)
        claims, citations, sources = self._coverage_scope(work_id)
        lines = self._work_lines(work_id)
        backgrounds = self._work_backgrounds(work_id)
        annotations = self._work_annotations(work_id)
        layer_of = {b["id"]: b["layer"] for b in backgrounds}
        linked: dict[tuple[str, int], set[str]] = {}
        per_layer_lines: dict[str, set[tuple[str, int]]] = {layer: set() for layer in LAYERS}
        for bl in self.background_lines:
            layer = layer_of.get(bl["background_id"])
            if layer is None:
                continue
            key = (bl["version_id"], bl["line_seq"])
            linked.setdefault(key, set()).add(layer)
            per_layer_lines[layer].add(key)
        status_counts: dict[str, int] = {"DRAFT": 0, "PUBLISHED": 0}
        for c in claims:
            status_counts[c["status"]] = status_counts.get(c["status"], 0) + 1
        ver_counts = {"PENDING": 0, "VERIFIED": 0, "REJECTED": 0}
        for s in sources:
            ver_counts[s["verification_status"]] = ver_counts.get(s["verification_status"], 0) + 1
        checkable = 0
        for c in claims:
            if any(ci["claim_id"] == c["id"] and ci["verification_status"] == "VERIFIED"
                   and locator_state(ci["locator"]) == "SET" for ci in citations):
                checkable += 1
        return {
            "work_id": work_id,
            "totals": {"lines": len(lines), "versions": len(self._work_versions(work_id)),
                       "backgrounds": len(backgrounds), "annotations": len(annotations),
                       "claims": len(claims), "sources": len(sources), "citations": len(citations)},
            "claims_by_status": status_counts,
            "claims_checkable": {"checkable": checkable, "total": len(claims)},
            "sources_by_verification": ver_counts,
            "layers": {layer: {"count": sum(1 for b in backgrounds if b["layer"] == layer),
                               "linked_lines": len(per_layer_lines[layer])} for layer in LAYERS},
            "lines": [{
                "version_id": r["version_id"], "line_seq": r["line_seq"], "content": r["content"],
                "annotation_count": sum(1 for a in annotations
                                        if a["version_id"] == r["version_id"] and a["line_seq"] == r["line_seq"]),
                "background_count": sum(1 for bl in self.background_lines
                                        if (bl["version_id"], bl["line_seq"]) == (r["version_id"], r["line_seq"])
                                        and bl["background_id"] in layer_of),
                "layers": sorted(linked.get((r["version_id"], r["line_seq"]), set()))} for r in lines],
            "gap_codes": list(dict.fromkeys(g["code"] for g in self.gaps(work_id)["gaps"])),
            "publication": {"work_status": content["status"],
                            "published_claims": status_counts.get("PUBLISHED", 0),
                            "audit_checks": AUDIT_TOTAL_CHECKS, "audit_non_zero": []},
        }

    def studio_view(self, work_id: str) -> dict:
        data = self.snapshot(work_id)
        claims, citations, sources = self._coverage_scope(work_id)
        data["claims"], data["citations"], data["sources"] = claims, citations, sources
        bg_ids = {b["id"] for b in data["backgrounds"]}
        data["background_lines"] = [dict(bl) for bl in self.background_lines if bl["background_id"] in bg_ids]
        data["claim_status_by_id"] = {c["id"]: c["status"] for c in claims}
        ids = {work_id} | bg_ids
        data["content_status_by_id"] = {i: self.contents[i]["status"] for i in sorted(ids) if i in self.contents}
        data["version_status_by_id"] = {v["id"]: v["status"] for v in data["versions"]}
        data["source_verification_by_id"] = {s["id"]: s["verification_status"] for s in sources}
        data["coverage_rows"] = copy.deepcopy(self.coverage_rows)
        data["gap_report"] = self.gaps(work_id)
        return data

    def list_sources(self, q: dict[str, str | None]) -> dict:
        status = q.get("verification_status")
        if status not in (None, "") and status not in VERIFICATION_STATUSES:
            raise Rejected("verification_status outside vocabulary")
        rows = []
        for sid in sorted(self.sources):
            src = self.sources[sid]
            if status not in (None, "") and src["verification_status"] != status:
                continue
            row = self._source_row(src)
            row["citations"] = [{
                "claim_id": c["claim_id"], "claim_value": self.claims[c["claim_id"]]["value_text"],
                "claim_kind": self.claims[c["claim_id"]]["claim_kind"],
                "claim_status": self.claims[c["claim_id"]]["status"], "locator": c["locator"],
                "evidence_excerpt": c["evidence_excerpt"], "locator_state": locator_state(c["locator"])}
                for c in sorted((x for x in self.citations.values() if x["source_id"] == sid and x["claim_id"] in self.claims),
                                key=lambda x: x["claim_id"])]
            rows.append(row)
        return page(rows, q.get("limit"), q.get("offset"))

    # ------------------------------------------------------------------ 契约 §3.2 studio 人类写
    @staticmethod
    def _check_reviewer(body: Any, allowed_roles: set[str]) -> tuple[str, str]:
        reviewer = text(fld(body, "reviewer"))
        role = text(fld(body, "reviewer_role"))
        if blank(reviewer) or not 2 <= len(reviewer.strip()) <= 100:  # type: ignore[union-attr]
            raise Rejected("reviewer must be 2..100 characters")
        if _REVIEWER_BLOCKED.search(reviewer):  # type: ignore[arg-type]
            raise Rejected("reviewer must be a human signature")
        if role not in STUDIO_ROLES:
            raise Rejected("unsupported reviewer_role")
        if role not in allowed_roles:
            raise Forbidden("reviewer_role is not allowed to perform this action")
        return reviewer.strip(), role  # type: ignore[union-attr,return-value]

    def _log(self, **row: Any) -> None:
        base = {"id": len(self.check_log) + 1, "claim_id": None, "proposal_id": None, "locator": None,
                "evidence_excerpt": None, "decision": None, "note": None, "created_at": now_iso()}
        base.update(row)
        self.check_log.append(base)

    def set_locator(self, claim_id: str, source_id: str, body: Any) -> dict:
        reviewer, role = self._check_reviewer(body, SOURCE_REVIEW_ROLES)
        locator = text(fld(body, "locator"))
        if blank(locator):
            raise Rejected("locator is required")
        locator = locator.strip()  # type: ignore[union-attr]
        if len(locator) > 300:
            raise Rejected("locator longer than 300 characters")
        if locator_state(locator) != "SET":
            raise Rejected("locator must not be empty or a placeholder")
        excerpt = text(fld(body, "evidence_excerpt"))
        citation = self.citations.get((claim_id, source_id))
        if citation is None:
            raise NotFound("citation not found")
        citation["locator"] = locator
        if excerpt is not None:
            citation["evidence_excerpt"] = excerpt
        self._log(action="SET_LOCATOR", source_id=source_id, claim_id=claim_id, locator=locator,
                  evidence_excerpt=excerpt, reviewer=reviewer, reviewer_role=role, note=text(fld(body, "note")))
        return {"claim_id": claim_id, "source_id": source_id, "locator": locator,
                "locator_state": "SET", "source_verification_status": self.sources[source_id]["verification_status"]}

    def source_verification(self, source_id: str, body: Any) -> dict:
        reviewer, role = self._check_reviewer(body, SOURCE_REVIEW_ROLES)
        decision = fld(body, "decision")
        if decision not in ("VERIFY", "REJECT"):
            raise Rejected("decision must be VERIFY or REJECT")
        src = self.sources.get(source_id)
        if src is None:
            raise NotFound("source not found")
        if decision == "VERIFY":
            blocking = source_problems(reviewer, src["source_kind"], src["reliability"])
            missing = [{"claim_id": c["claim_id"], "source_id": source_id, "locator_state": locator_state(c["locator"])}
                       for c in sorted(self.citations.values(), key=lambda x: x["claim_id"])
                       if c["source_id"] == source_id and locator_state(c["locator"]) != "SET"]
            if blocking or missing:
                raise Conflict("source cannot be verified", {"blocking": blocking, "missing_locators": missing})
            src.update(verification_status="VERIFIED", verified_by=reviewer)
        else:
            blocking = reviewer_problems(reviewer)
            if blocking:
                raise Conflict("source cannot be rejected", {"blocking": blocking, "missing_locators": []})
            src.update(verification_status="REJECTED", verified_by=reviewer)
        self._log(action=decision, source_id=source_id, decision=decision, reviewer=reviewer,
                  reviewer_role=role, note=text(fld(body, "note")))
        return {"source_id": source_id, "verification_status": src["verification_status"],
                "verified_by": reviewer, "audit_checks": AUDIT_TOTAL_CHECKS if decision == "VERIFY" else 0}

    def put_items(self, pid: str, body: Any) -> dict:
        reviewer, role = self._check_reviewer(body, STUDIO_ROLES)
        decisions = fld(body, "decisions")
        if not isinstance(decisions, list) or not decisions or len(decisions) > 50:
            raise Rejected("decisions must contain 1..50 items")
        p = self.proposals.get(pid)
        if p is None:
            raise NotFound("proposal not found")
        if p["review_status"] != "PENDING":
            raise Conflict("proposal is no longer pending review")
        changes = json.loads(p["proposal_json"]).get("changes", [])
        seen: set[int] = set()
        staged: list[tuple[int, str, str | None]] = []
        for d in decisions:
            idx = as_int(fld(d, "item_index"), -1)
            verdict = fld(d, "decision")
            if idx < 0 or idx >= len(changes):
                raise Rejected("item_index out of range")
            if idx in seen:
                raise Rejected("duplicate item_index")
            if verdict not in ("APPROVE", "REJECT"):
                raise Rejected("decision must be APPROVE or REJECT")
            comment = text(fld(d, "comment"))
            seen.add(idx)
            staged.append((idx, verdict, comment))
        for idx, verdict, comment in staged:
            self.items[(pid, idx)] = {"decision": verdict, "reviewer": reviewer, "comment": comment,
                                      "created_at": now_iso()}
        self._log(action="ITEM_DECISIONS", source_id="-", proposal_id=pid, reviewer=reviewer,
                  reviewer_role=role, note=f"{len(staged)} item(s)")
        return {"proposal_id": pid, "recorded": len(staged), **self.proposal_items(pid)}
