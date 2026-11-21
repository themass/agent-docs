"""The four deterministic generators against the 《春望》 studio-view fixture (both key styles).

Fixture facts (from V002/V004 + the mock seed): 1 text version ``text-chun-wang-draft`` with 8 lines,
15 claims, 13 citations, 4 sources all PENDING, 4 backgrounds linked to 8 lines, 2 annotations (lines 1 and 5).
"""
from __future__ import annotations

import re
from typing import Any

import pytest
from agent_worker.compile import compile_proposal, validate_proposal
from agent_worker.snapshot import SnapshotView
from agent_worker.stub import generate
from agent_worker.stub.rules import RULE_NAMES, evaluate
from agent_worker.validate import validate_output
from helpers import RUN_ID, load_fixture

VID = "text-chun-wang-draft"
TASKS = ("GAP_ANALYSIS", "ANNOTATION_DRAFT", "SCRIPT_DRAFT", "COMPILE_TRIAGE", "CONTENT_REVIEW")


@pytest.fixture(params=["snake", "camel"])
def view(request: pytest.FixtureRequest) -> SnapshotView:
    return SnapshotView.from_raw(load_fixture(request.param))


def by_code(output: dict[str, Any], code: str) -> dict[str, Any]:
    return next(i for i in output["items"] if i["body"].startswith(f"[{code}]"))


def test_both_key_styles_normalise_to_the_same_view() -> None:
    snake, camel = SnapshotView.from_raw(load_fixture("snake")), SnapshotView.from_raw(load_fixture("camel"))
    assert snake.digest() == camel.digest()
    assert snake.counts() == {"versions": 1, "lines": 8, "claims": 15, "citations": 13, "backgrounds": 4,
                              "annotations": 2, "sources": 4, "background_lines": 8, "coverage_rows": 3}


def test_the_plain_snapshot_shape_works_too() -> None:
    """Without the studio-view extras the stubs still run and say what they cannot judge."""
    raw = load_fixture("snake")
    for key in ("background_lines", "coverage_rows", "gap_report"):
        raw.pop(key)
    plain = SnapshotView.from_raw({"status": "OK", "data": raw, "audit_refs": [], "next_action": "NONE"})
    out = generate("GAP_ANALYSIS", plain)
    assert validate_output(out, plain, expected_task_type="GAP_ANALYSIS").ok
    assert by_code(out, "BACKGROUND_LINKS_UNKNOWN")["severity"] == "LOW"
    assert by_code(out, "COVERAGE_UNKNOWN")
    assert any("关联表" in u for u in out["unknowns"])


@pytest.mark.parametrize("task", TASKS)
def test_every_stub_output_passes_the_same_validator_and_compiles(view: SnapshotView, task: str) -> None:
    out = generate(task, view)
    result = validate_output(out, view, expected_task_type=task)
    assert result.ok, result.codes()
    proposal = compile_proposal(result.output, RUN_ID)
    assert validate_proposal(proposal) == []
    assert proposal["changes"] and all(c["draft_payload"] is None for c in proposal["changes"])  # STUB is never executable


def test_the_editor_instructions_are_not_an_input(view: SnapshotView) -> None:
    import inspect

    from agent_worker import stub

    assert "instructions" not in inspect.signature(stub.generate).parameters
    assert generate("GAP_ANALYSIS", view) == generate("GAP_ANALYSIS", view)  # deterministic


# ---- GAP_ANALYSIS ---------------------------------------------------------------------------------
def test_gap_analysis_findings_are_real_and_graded(view: SnapshotView) -> None:
    out = generate("GAP_ANALYSIS", view)
    gaps = {i["body"].split("]")[0][1:]: i for i in out["items"] if i["kind"] == "GAP"}
    assert gaps["TEXT_SOURCE_NOT_CHECKED"]["severity"] == "HIGH"
    assert gaps["FACT_CLAIM_NO_CHECKABLE_SOURCE"]["severity"] == "HIGH"
    assert gaps["SOURCES_PENDING"]["severity"] == "HIGH"
    assert gaps["CLAIM_NO_CITATION"]["severity"] == "HIGH"
    assert "claim:claim-tang-time" in gaps["CLAIM_NO_CITATION"]["evidence_refs"]
    assert "claim:claim-theme-anshi-time" in gaps["CLAIM_NO_CITATION"]["evidence_refs"]
    assert gaps["CITATION_LOCATOR_PLACEHOLDER"]["severity"] == "HIGH"
    assert gaps["KNOWN_WITHOUT_BASIS"]["severity"] == "HIGH"
    assert gaps["TEXT_VERSION_NOT_PUBLISHED"]["severity"] == "MEDIUM"
    assert gaps["UNKNOWN_DATES_UNDECLARED"]["severity"] == "MEDIUM"
    assert "text-chun-wang-draft" in gaps["ANNOTATION_COVERAGE"]["body"]
    assert "第 1、5 句" in gaps["ANNOTATION_COVERAGE"]["body"] and "6 句" in gaps["ANNOTATION_COVERAGE"]["body"]
    assert gaps["LINES_WITHOUT_BACKGROUND"]["evidence_refs"] == [f"line:{VID}#3", f"line:{VID}#4"]
    assert "COVERAGE_ROW_NOT_FINAL" in gaps
    sources = gaps["SOURCES_PENDING"]["evidence_refs"]
    assert sorted(sources) == sorted(f"source:{s}" for s in view.pending_sources()) and len(sources) == 4
    assert "BACKGROUND_NOT_LINKED" not in gaps and "TEXT_LINES_MISSING" not in gaps  # no false alarms
    severities = [i["severity"] for i in out["items"] if i["kind"] == "GAP"]
    assert severities == sorted(severities, key={"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get)  # most severe first


def test_gap_analysis_emits_one_source_request_per_uncheckable_claim_and_never_a_locator(view: SnapshotView) -> None:
    out = generate("GAP_ANALYSIS", view)
    requests = [i for i in out["items"] if i["kind"] == "SOURCE_REQUEST"]
    assert len(requests) == 15
    assert {r["source_request"]["claim_ref"] for r in requests} == set(view.claim_by_id)
    for r in requests:
        assert r["epistemic"] == "FACT_REQUEST" and r["annotation"] is None
        assert r["source_request"].get("locator") is None
        assert all(view.resolves(ref) for ref in r["evidence_refs"])
    facts = [r for r in requests if r["severity"] == "HIGH"]
    assert len(facts) == 9 and requests[:9] == facts  # the 9 FACT claims come first
    anshi = next(r for r in requests if r["source_request"]["claim_ref"] == "claim-anshi-time")
    assert anshi["source_request"]["suggested_source_kind"] == "OFFICIAL_HISTORY"
    assert "资治通鉴" in anshi["source_request"]["suggested_source_title"]
    text = " ".join(i["body"] for i in out["items"])
    assert not re.search(r"卷[一二三四五六七八九十百零\d]+|第?\s*\d+\s*[页頁]", text)  # no volume or page invented


def test_gap_analysis_flags_each_missing_thing_when_the_snapshot_changes() -> None:
    raw = load_fixture("snake")
    raw["background_lines"] = [r for r in raw["background_lines"] if r["background_id"] != "bg-chun-wang-world"]
    raw["backgrounds"] = [b for b in raw["backgrounds"] if b["layer"] != "PERSON"]
    raw["coverage_rows"] = []
    raw["gap_report"]["audit_non_zero"] = ["C5_citation_locator_placeholder_on_published_claim=3"]
    raw["gap_report"]["gaps"].append({"code": "SOMETHING_NEW", "severity": "LOW", "message": "x", "target_ref": None})
    view = SnapshotView.from_raw(raw)
    out = generate("GAP_ANALYSIS", view)
    assert validate_output(out, view, expected_task_type="GAP_ANALYSIS").ok
    assert by_code(out, "BACKGROUND_NOT_LINKED")["evidence_refs"] == ["background:bg-chun-wang-world"]
    assert "PERSON" in by_code(out, "BACKGROUND_LAYER_MISSING")["body"]
    assert by_code(out, "COVERAGE_NOT_DECLARED")["severity"] == "HIGH"
    assert by_code(out, "INTEGRITY_AUDIT_NONZERO")["severity"] == "HIGH"
    assert by_code(out, "SERVER_SOMETHING_NEW")["severity"] == "LOW"


def test_gap_analysis_with_no_versions_or_lines() -> None:
    raw = load_fixture("snake")
    raw.update(versions=[], lines=[], annotations=[], background_lines=[])
    view = SnapshotView.from_raw(raw)
    out = generate("GAP_ANALYSIS", view)
    assert validate_output(out, view, expected_task_type="GAP_ANALYSIS").ok
    assert by_code(out, "TEXT_VERSION_MISSING")["severity"] == "HIGH"


def test_a_checkable_claim_is_not_reported() -> None:
    raw = load_fixture("snake")
    raw["sources"][1]["verification_status"] = "VERIFIED"
    raw["source_verification_by_id"]["source-anshi-candidate"] = "VERIFIED"
    for c in raw["citations"]:
        if c["claim_id"] == "claim-anshi-time":
            c["locator"] = "卷二百一十八"
            c["verification_status"] = "VERIFIED"
    view = SnapshotView.from_raw(raw)
    assert view.claim_checkable("claim-anshi-time") and not view.claim_checkable("claim-bg-city")
    out = generate("GAP_ANALYSIS", view)
    assert "claim-anshi-time" not in {r["source_request"]["claim_ref"] for r in out["items"] if r["kind"] == "SOURCE_REQUEST"}
    assert len([i for i in out["items"] if i["kind"] == "SOURCE_REQUEST"]) == 14
    assert validate_output(out, view, expected_task_type="GAP_ANALYSIS").ok


# ---- ANNOTATION_DRAFT -----------------------------------------------------------------------------
def test_annotation_draft_is_a_scaffold_without_any_annotation_text(view: SnapshotView) -> None:
    out = generate("ANNOTATION_DRAFT", view)
    lines = [i for i in out["items"] if i["kind"] == "ANNOTATION"]
    assert [i["target_ref"] for i in lines] == [f"line:{VID}#{n}" for n in range(1, 9)]
    assert all(i["epistemic"] == "UNKNOWN" and i["annotation"] is None for i in lines)  # nothing executable, nothing invented
    assert lines[0]["severity"] == "LOW" and "已有 1 条注释" in lines[0]["body"] and "ann-chun-wang-shanhe" in lines[0]["body"]
    assert lines[1]["severity"] == "MEDIUM" and "尚无注释" in lines[1]["body"]
    assert "bg-chun-wang-scene" in lines[1]["body"] or "背景草稿" in lines[1]["body"]
    assert "STUB 不编写注释文字" in lines[1]["body"]
    assert any(i["kind"] == "GAP" and "底本" in i["body"] for i in out["items"])
    assert out["human_review_question"].count("?") == 1 and "2、3、4、6、7、8" in out["human_review_question"]
    assert out["unknowns"]


# ---- SCRIPT_DRAFT ---------------------------------------------------------------------------------
def test_script_draft_follows_the_five_steps_and_marks_basis(view: SnapshotView) -> None:
    out = generate("SCRIPT_DRAFT", view)
    beats = [i for i in out["items"] if i["kind"] == "SCRIPT_BEAT"]
    steps = [re.match(r"【(读|到|见|回|诵)", b["body"]).group(1) for b in beats]
    order = ["读", "到", "见", "回", "诵"]
    assert [order.index(s) for s in steps] == sorted(order.index(s) for s in steps) and set(steps) == set(order)
    arrive = [b for b in beats if b["body"].startswith("【到")]
    assert len(arrive) == 4 and all(b["epistemic"] == "UNKNOWN" for b in arrive)  # background claims have no checkable source
    assert all("没有可核查出处" in b["body"] for b in arrive)
    meet = next(b for b in beats if b["body"].startswith("【见"))
    assert meet["epistemic"] == "DRAMATIZATION" and "演绎" in meet["body"] and "不写台词" in meet["body"]
    assert all(view.resolves(r) for b in beats for r in b["evidence_refs"])
    assert not any(b["kind"] == "SCRIPT_BEAT" and "说:" in b["body"] for b in beats)  # no dialogue
    assert by_code(out, "UNKNOWN_DATES_UNDECLARED")
    assert "暂无依据" in out["summary"] and "演绎 1 拍" in out["summary"]


def test_script_draft_without_backgrounds_says_so() -> None:
    raw = load_fixture("snake")
    raw.update(backgrounds=[], background_lines=[], annotations=[])
    view = SnapshotView.from_raw(raw)
    out = generate("SCRIPT_DRAFT", view)
    assert validate_output(out, view, expected_task_type="SCRIPT_DRAFT").ok
    assert sum("没有 " in i["body"] and "层背景草稿" in i["body"] for i in out["items"]) == 4


# ---- COMPILE_TRIAGE -------------------------------------------------------------------------------
def test_rule_names_match_rules_mjs() -> None:
    from pathlib import Path

    js = (Path(__file__).resolve().parents[3] / "pipeline" / "tools" / "scene-validator" / "rules.mjs").read_text(encoding="utf-8")
    for rule_id, name in RULE_NAMES.items():
        if rule_id == "R10":  # rules.mjs reports this rule under two labels: "rights" and "meaning"
            assert "rule('R10', 'rights')" in js and "rule('R10', 'meaning')" in js
            assert name == "rights and meaning"
            continue
        assert f"rule('{rule_id}', '{name}')" in js, (rule_id, name)
    assert list(RULE_NAMES) == [f"R{n}" for n in range(1, 13)]


def test_data_rules_on_the_fixture(view: SnapshotView) -> None:
    status = {r.id: r.status for r in evaluate(view)}
    assert status["R1"] == status["R8"] == status["R11"] == "PASS"
    assert status["R2"] == status["R3"] == status["R7"] == "FAIL"
    assert all(status[r] == "NOT_EVALUATED" for r in ("R4", "R5", "R6", "R9", "R10", "R12"))  # need a bundle, never PASS
    r3 = next(r for r in evaluate(view) if r.id == "R3")
    assert r3.count == 15


def test_compile_triage_is_ordered_by_blocking_and_assigns_owners(view: SnapshotView) -> None:
    out = generate("COMPILE_TRIAGE", view)
    items = out["items"]
    ranks = [int(m.group(1)) for i in items if (m := re.search(r"阻塞序 (\d+)", i["body"]))]
    assert ranks == sorted(ranks) and ranks[0] == 1
    assert items[0]["body"].startswith("[R3 basis]") and items[0]["severity"] == "HIGH"
    assert "史料审核人" in items[0]["body"] and "责任" in items[0]["body"]
    assert "CLAIM_VERIFIED_CITATION_MISSING" in items[0]["body"]  # the server gap code is mapped to its rule
    assert any(i["body"].startswith("[R2 published only]") for i in items)
    bundle_rules = [i for i in items if "需要编译后的 bundle" in i["body"]]
    assert {re.match(r"\[(R\d+)", i["body"]).group(1) for i in bundle_rules} >= {"R4", "R9", "R10", "R12", "R5", "R6"}
    human_only = items[-1]["body"]
    assert "来源的核验" in human_only and "定位" in human_only and "agent 没有这项能力" in human_only
    assert not any(i["body"].startswith(("[R1 ", "[R8 ", "[R11 ")) for i in items)  # passing rules are not noise
    assert "通过 3 条(R1、R8、R11)" in out["summary"]
    assert out["human_review_question"].count("?") == 1


def test_compile_triage_when_data_rules_all_pass() -> None:
    raw = load_fixture("snake")
    raw["work"]["status"] = "PUBLISHED"
    raw["versions"][0]["status"] = "PUBLISHED"
    raw["version_status_by_id"][VID] = "PUBLISHED"
    raw["content_status_by_id"] = {k: "PUBLISHED" for k in raw["content_status_by_id"]}
    raw["claim_status_by_id"] = {k: "PUBLISHED" for k in raw["claim_status_by_id"]}
    for s in raw["sources"]:
        s["verification_status"] = "VERIFIED"
    raw["source_verification_by_id"] = {k: "VERIFIED" for k in raw["source_verification_by_id"]}
    for c in raw["citations"]:
        c["locator"], c["verification_status"] = "卷二", "VERIFIED"
    view = SnapshotView.from_raw(raw)
    claims_without_citation = [c["id"] for c in view.claims if not view.claim_checkable(c["id"]) and c["claim_kind"] != "DRAMATIZATION"]
    out = generate("COMPILE_TRIAGE", view)
    assert validate_output(out, view, expected_task_type="COMPILE_TRIAGE").ok
    assert ("[R3 basis]" in " ".join(i["body"] for i in out["items"])) == bool(claims_without_citation)
    assert not any(i["body"].startswith("[R2 ") for i in out["items"])


def test_nothing_in_any_stub_output_claims_a_verified_or_published_state(view: SnapshotView) -> None:
    from agent_worker.guard import find_assertions, find_forbidden_imperatives

    for task in TASKS:
        out = generate(task, view)
        texts = [out["summary"], out["human_review_question"], *out["unknowns"], *(i["body"] for i in out["items"])]
        for text in texts:
            assert find_assertions(text) == [] and find_forbidden_imperatives(text) == [], text
