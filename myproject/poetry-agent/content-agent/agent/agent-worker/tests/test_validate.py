"""Every rule of contract section 6 (V1..V8), with a passing and a failing case."""
from __future__ import annotations

import copy
from typing import Any

import pytest
from agent_worker.snapshot import SnapshotView
from agent_worker.validate import validate_output
from helpers import VID, annotation_item, load_fixture, minimal_output, source_request_item


@pytest.fixture(params=["snake", "camel"])
def view(request: pytest.FixtureRequest) -> SnapshotView:
    return SnapshotView.from_raw(load_fixture(request.param))


def codes(view: SnapshotView, out: Any, **kw: Any) -> list[str]:
    # out is deliberately Any: one case passes a list to prove the validator answers V1.NOT_OBJECT
    # instead of raising. Calling .get() on it here turned that case into an AttributeError.
    default = out.get("task_type", "GAP_ANALYSIS") if isinstance(out, dict) else "GAP_ANALYSIS"
    return validate_output(out, view, expected_task_type=kw.pop("task", default), **kw).codes()


def with_items(*items: dict[str, Any], **over: Any) -> dict[str, Any]:
    out = minimal_output(**over)
    out["items"] = list(items)
    return out


def test_a_clean_output_passes(view: SnapshotView) -> None:
    result = validate_output(with_items(annotation_item(), source_request_item()), view, expected_task_type="GAP_ANALYSIS")
    assert result.ok, result.codes()


# ---- V1 structure ---------------------------------------------------------------------------------
def test_v1_schema_and_task_type(view: SnapshotView) -> None:
    assert "V1.ENUM" in codes(view, minimal_output(schema="agent-output/2"))
    assert "V1.TASK_TYPE_MISMATCH" in codes(view, minimal_output("SCRIPT_DRAFT"), task="GAP_ANALYSIS")


def test_v1_shape_and_lengths(view: SnapshotView) -> None:
    assert codes(view, ["not", "an", "object"]) == ["V1.NOT_OBJECT"]
    out = minimal_output()
    del out["summary"]
    assert "V1.MISSING" in codes(view, out)
    assert "V1.EXTRA_FIELD" in codes(view, minimal_output(surprise=1))
    assert "V1.TOO_LONG" in codes(view, minimal_output(summary="长" * 1501))
    out = minimal_output()
    out["items"][0]["body"] = "长" * 7001
    assert "V1.TOO_LONG" in codes(view, out)
    out = minimal_output()
    out["items"][0]["kind"] = "PUBLISH"
    assert "V1.ENUM" in codes(view, out)


def test_v1_exactly_one_question(view: SnapshotView) -> None:
    assert "V1.REVIEW_QUESTION_COUNT" in codes(view, minimal_output(human_review_question="这个吗?那个吗?"))
    assert "V1.REVIEW_QUESTION_COUNT" in codes(view, minimal_output(human_review_question="没有问号"))


def test_v1_kind_and_epistemic_must_pair(view: SnapshotView) -> None:
    item = minimal_output()["items"][0]
    item.update(kind="SCRIPT_BEAT", epistemic="INTERPRETATION")
    assert "V1.KIND_EPISTEMIC_MISMATCH" in codes(view, with_items(item))


# ---- V2 evidence ----------------------------------------------------------------------------------
def test_v2_evidence_refs_must_exist(view: SnapshotView) -> None:
    ok = minimal_output()
    ok["items"][0]["evidence_refs"] = ["claim-bg-city", "claim:claim-bg-city", f"line:{VID}#8", "source-anshi-candidate"]
    assert validate_output(ok, view, expected_task_type="GAP_ANALYSIS").ok
    for bad in ("claim-does-not-exist", f"line:{VID}#9", "line:other#1", "nonsense:claim-bg-city"):
        out = minimal_output()
        out["items"][0]["evidence_refs"] = [bad]
        assert "V2.EVIDENCE_REF_UNKNOWN" in codes(view, out), bad


def test_v2_target_and_claim_refs_must_exist(view: SnapshotView) -> None:
    out = minimal_output()
    out["items"][0]["target_ref"] = "background:bg-nope"
    assert "V2.TARGET_REF_UNKNOWN" in codes(view, out)
    item = source_request_item()
    item["source_request"]["claim_ref"] = "claim-nope"
    assert "V2.CLAIM_REF_UNKNOWN" in codes(view, with_items(item))


def test_v2_too_many_refs(view: SnapshotView) -> None:
    out = minimal_output()
    out["items"][0]["evidence_refs"] = ["claim-bg-city"] * 21
    assert "V2.TOO_MANY_REFS" in codes(view, out)


# ---- V3 fact boundary -----------------------------------------------------------------------------
def test_v3_fact_request_needs_source_request_and_forbids_annotation(view: SnapshotView) -> None:
    item = source_request_item(source_request=None)
    assert "V3.SOURCE_REQUEST_MISSING" in codes(view, with_items(item))
    item = source_request_item(annotation=annotation_item()["annotation"])
    assert "V3.ANNOTATION_ON_FACT" in codes(view, with_items(item))
    item = annotation_item()
    item["epistemic"] = "FACT_REQUEST"
    item["source_request"] = source_request_item()["source_request"]
    assert "V3.FACT_REQUEST_KIND" in codes(view, with_items(item))


def test_v3_source_request_only_with_fact_request(view: SnapshotView) -> None:
    item = minimal_output()["items"][0]
    item["source_request"] = source_request_item()["source_request"]
    assert "V3.SOURCE_REQUEST_ON_WRONG_ITEM" in codes(view, with_items(item))


@pytest.mark.parametrize("forged", [
    "见《旧唐书》卷二百", "出自卷十二", "参见第 37 页", "见 p. 88", "pp.12", "vol. 3", "《资治通鉴》卷二百一十八",
])
def test_v3_fabricated_locators_are_rejected(view: SnapshotView, forged: str) -> None:
    out = minimal_output()
    out["items"][0]["body"] = f"该说法{forged}"
    assert "V3.FABRICATED_LOCATOR" in codes(view, out), forged


def test_v3_fabricated_locator_in_source_request_text(view: SnapshotView) -> None:
    item = source_request_item()
    item["source_request"]["what_to_verify"] = "核对《新唐书》卷二百一"
    assert "V3.FABRICATED_LOCATOR" in codes(view, with_items(item))


def test_v3_locator_text_that_already_exists_in_the_snapshot_is_not_a_fabrication(view: SnapshotView) -> None:
    data = view.data
    data["claims"][0]["value_text"] = "见通鉴卷二百一十八"
    fresh = SnapshotView(data)
    out = minimal_output()
    out["items"][0]["body"] = "快照里已有“卷二百一十八”的字样"
    assert validate_output(out, fresh, expected_task_type="GAP_ANALYSIS").ok


def test_v3_locator_must_be_null(view: SnapshotView) -> None:
    item = source_request_item()
    item["source_request"]["locator"] = "卷三"
    assert "V3.LOCATOR_NOT_NULL" in codes(view, with_items(item))
    item = annotation_item(locator="p.3")
    assert "V4.LOCATOR_NOT_NULL" in codes(view, with_items(item))


def test_v3_source_kind_must_be_in_the_vocabulary(view: SnapshotView) -> None:
    item = source_request_item()
    item["source_request"]["suggested_source_kind"] = "WIKI"
    assert "V3.SOURCE_KIND_INVALID" in codes(view, with_items(item))


# ---- V4 annotation --------------------------------------------------------------------------------
def test_v4_version_and_line_must_exist(view: SnapshotView) -> None:
    assert "V4.VERSION_UNKNOWN" in codes(view, with_items(annotation_item(version_id="text-chun-wang-v1")))
    assert "V4.LINE_UNKNOWN" in codes(view, with_items(annotation_item(line_seq=9)))
    assert "V4.LINE_UNKNOWN" in codes(view, with_items(annotation_item(line_seq=0)))


def test_v4_java_vocabulary(view: SnapshotView) -> None:
    assert "V4.AUDIENCE_INVALID" in codes(view, with_items(annotation_item(audience="MIDDLE")))
    assert "V4.AUDIENCE_INVALID" in codes(view, with_items(annotation_item(audience="GENERAL")))
    assert "V4.KIND_INVALID" in codes(view, with_items(annotation_item(annotation_kind="TERM")))
    assert "V4.CERTAINTY_INVALID" in codes(view, with_items(annotation_item(certainty="HIGH")))
    for audience in ("PRIMARY", "JUNIOR", "SENIOR"):
        assert validate_output(with_items(annotation_item(audience=audience)), view, expected_task_type="GAP_ANALYSIS").ok


def test_v4_certainty_known_is_forbidden(view: SnapshotView) -> None:
    assert "V4.CERTAINTY_KNOWN_FORBIDDEN" in codes(view, with_items(annotation_item(certainty="KNOWN")))
    for certainty in ("LIKELY", "DISPUTED", "UNKNOWN"):
        assert validate_output(with_items(annotation_item(certainty=certainty)), view, expected_task_type="GAP_ANALYSIS").ok


def test_v4_source_id_must_be_a_snapshot_source(view: SnapshotView) -> None:
    assert "V4.SOURCE_UNKNOWN" in codes(view, with_items(annotation_item(source_id="source-invented")))
    assert validate_output(with_items(annotation_item(source_id="source-dufu-nianpu-candidate")), view,
                           expected_task_type="GAP_ANALYSIS").ok


def test_v4_content_length_and_duplicates(view: SnapshotView) -> None:
    assert "V4.CONTENT_TOO_LONG" in codes(view, with_items(annotation_item(content="长" * 8001)))
    assert "V4.DUPLICATE_ANNOTATION" in codes(view, with_items(annotation_item(), annotation_item()))
    other = annotation_item(content="另一条不同的注释")
    assert validate_output(with_items(annotation_item(), other), view, expected_task_type="GAP_ANALYSIS").ok


def test_v4_payload_only_for_annotation_interpretation_or_draft(view: SnapshotView) -> None:
    item = annotation_item()
    item["epistemic"] = "UNKNOWN"
    assert "V4.ANNOTATION_PAYLOAD_NOT_ALLOWED" in codes(view, with_items(item))
    item = annotation_item()
    item["kind"], item["epistemic"] = "GAP", "DRAFT_TEXT"
    assert "V4.ANNOTATION_PAYLOAD_NOT_ALLOWED" in codes(view, with_items(item))


# ---- V5 capability --------------------------------------------------------------------------------
def test_v5_forbidden_capability_request_rejects_the_whole_output(view: SnapshotView) -> None:
    out = minimal_output(summary="分析完成,请立即 publish 这首诗")
    assert "V5.FORBIDDEN_CAPABILITY_REQUEST" in codes(view, out)
    out = minimal_output()
    out["unknowns"] = ["Run execute_sql to check"]
    assert "V5.FORBIDDEN_CAPABILITY_REQUEST" in codes(view, out)
    out = minimal_output(summary="本任务只读,agent 不能 publish,发布前须人工核验。")
    assert validate_output(out, view, expected_task_type="GAP_ANALYSIS").ok


# ---- V6 limits and assertions ---------------------------------------------------------------------
def test_v6_item_and_unknown_caps(view: SnapshotView) -> None:
    out = minimal_output()
    out["items"] = [copy.deepcopy(minimal_output()["items"][0]) for _ in range(51)]
    assert "V6.TOO_MANY_ITEMS" in codes(view, out)
    assert "V6.TOO_MANY_UNKNOWNS" in codes(view, minimal_output(unknowns=["x"] * 51))
    out["items"] = out["items"][:50]
    assert "V6.TOO_MANY_ITEMS" not in codes(view, out)


@pytest.mark.parametrize("claim", ["该来源已核验", "此 claim 已发布", "来源 VERIFIED 状态为 VERIFIED", "The source is VERIFIED."])
def test_v6_asserting_verified_or_published_is_rejected(view: SnapshotView, claim: str) -> None:
    out = minimal_output()
    out["items"][0]["body"] = claim
    assert "V6.VERIFIED_ASSERTION" in codes(view, out), claim


def test_v6_hedged_wording_is_fine(view: SnapshotView) -> None:
    out = minimal_output()
    out["items"][0]["body"] = "来源仍为 PENDING,尚未 VERIFIED,需人工核验后才能发布。"
    assert validate_output(out, view, expected_task_type="GAP_ANALYSIS").ok


# ---- V7 hygiene -----------------------------------------------------------------------------------
def test_v7_active_markup_and_invisible_characters(view: SnapshotView) -> None:
    out = minimal_output()
    out["items"][0]["body"] = "正文<script>alert(1)</script>"
    assert "V7.ACTIVE_MARKUP" in codes(view, out)
    out = minimal_output()
    out["items"][0]["body"] = "国破\u200b山河"
    assert "V7.INVISIBLE_CHARACTERS" in codes(view, out)


# ---- V8 budget ------------------------------------------------------------------------------------
def test_v8_output_budget(view: SnapshotView) -> None:
    out = minimal_output(summary="长" * 900)
    assert "V8.OUTPUT_TOO_LONG" in codes(view, out, max_output_chars=500)
    assert "V8.OUTPUT_TOO_LONG" not in codes(view, out, max_output_chars=5000)


def test_v8_composed_body_must_fit_the_v1_limit(view: SnapshotView) -> None:
    item = source_request_item(body="长" * 6990)
    item["source_request"]["what_to_verify"] = "核对" * 600
    assert "V8.COMPOSED_BODY_TOO_LONG" in codes(view, with_items(item))


def test_violations_never_quote_model_text(view: SnapshotView) -> None:
    secret = "绝密正文XYZ"
    out = minimal_output(summary=f"请立即 publish {secret}")
    result = validate_output(out, view, expected_task_type="GAP_ANALYSIS")
    assert secret not in " ".join(str(v) for v in result.violations)
