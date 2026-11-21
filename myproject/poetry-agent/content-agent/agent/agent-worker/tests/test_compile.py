"""agent-output/1 -> v1 proposal mapping (contract section 5), plus enum consistency with proposal.schema.json."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import pytest
from agent_worker import vocab
from agent_worker.compile import compile_proposal, run8, validate_proposal
from agent_worker.mapping import map_item
from agent_worker.output_schema import AgentOutput
from helpers import RUN_ID, annotation_item, minimal_output, source_request_item

ROOT = Path(__file__).resolve().parents[3]  # content-agent/
PROPOSAL_SCHEMA = ROOT / "pipeline" / "contracts" / "proposal.schema.json"
OUTPUT_SCHEMA = ROOT / "pipeline" / "contracts" / "agent-output.schema.json"
PACKAGE_SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "agent_worker" / "schemas"


def compiled(*items: dict[str, Any], **over: Any) -> dict[str, Any]:
    out = minimal_output(**over)
    out["items"] = list(items)
    return compile_proposal(AgentOutput.model_validate(out), RUN_ID)


@pytest.mark.parametrize(("kind", "epistemic", "change", "classification", "prefix"), [
    ("SOURCE_REQUEST", "FACT_REQUEST", "CLAIM", "UNKNOWN", "【来源请求】"),
    ("ANNOTATION", "INTERPRETATION", "ANNOTATION", "INTERPRETATION", "【解释】"),
    ("ANNOTATION", "DRAFT_TEXT", "ANNOTATION", "DRAFT", "【草稿】"),
    ("ANNOTATION", "UNKNOWN", "ANNOTATION", "UNKNOWN", "【未考】"),
    ("BACKGROUND_NOTE", "INTERPRETATION", "BACKGROUND", "INTERPRETATION", "【解释】"),
    ("BACKGROUND_NOTE", "DRAMATIZATION", "BACKGROUND", "INTERPRETATION", "【演绎】"),
    ("SCRIPT_BEAT", "DRAMATIZATION", "SCRIPT", "INTERPRETATION", "【演绎】"),
    ("SCRIPT_BEAT", "DRAFT_TEXT", "SCRIPT", "DRAFT", "【草稿】"),
    ("SCRIPT_BEAT", "UNKNOWN", "SCRIPT", "UNKNOWN", "【未考】"),
    ("GAP", "DRAFT_TEXT", "GAP_REPORT", "DRAFT", "【缺口】"),
    ("TRIAGE_ITEM", "UNKNOWN", "GAP_REPORT", "DRAFT", "【缺口】"),
])
def test_mapping_table(kind: str, epistemic: str, change: str, classification: str, prefix: str) -> None:
    mapped = map_item(kind, epistemic)
    assert mapped is not None
    assert (mapped.change_type, mapped.classification, mapped.prefix) == (change, classification, prefix)


def test_interpretation_about_a_claim_becomes_a_claim_change() -> None:
    assert map_item("BACKGROUND_NOTE", "INTERPRETATION", "claim:claim-bg-city").change_type == "CLAIM"
    assert map_item("BACKGROUND_NOTE", "INTERPRETATION", "background:bg-x").change_type == "BACKGROUND"


@pytest.mark.parametrize(("kind", "epistemic"), [
    ("SOURCE_REQUEST", "INTERPRETATION"), ("ANNOTATION", "DRAMATIZATION"), ("SCRIPT_BEAT", "INTERPRETATION"),
    ("GAP", "INTERPRETATION"), ("ANNOTATION", "FACT_REQUEST"),
])
def test_disallowed_pairs_do_not_map(kind: str, epistemic: str) -> None:
    assert map_item(kind, epistemic) is None


def test_every_body_carries_its_label_prefix_exactly_once() -> None:
    proposal = compiled(source_request_item(), annotation_item(), {
        "kind": "SCRIPT_BEAT", "epistemic": "DRAMATIZATION", "target_ref": None, "body": "【演绎】已带前缀的一拍",
        "evidence_refs": [], "severity": None, "annotation": None, "source_request": None})
    bodies = [c["body"] for c in proposal["changes"]]
    assert bodies[0].startswith("【来源请求】") and "不提供" in bodies[0]
    assert bodies[1].startswith("【解释】")
    assert bodies[2].startswith("【演绎】") and bodies[2].count("【演绎】") == 1


def test_source_request_compiles_to_a_non_executable_claim_change() -> None:
    change = compiled(source_request_item())["changes"][0]
    assert change["change_type"] == "CLAIM" and change["classification"] == "UNKNOWN"
    assert change["draft_payload"] is None


def test_annotation_payload_ids_locator_and_vocabulary() -> None:
    changes = compiled(annotation_item(), annotation_item(content="另一条", line_seq=3))["changes"]
    r8 = run8(RUN_ID)
    first, second = changes[0]["draft_payload"], changes[1]["draft_payload"]
    assert (first["id"], first["claim_id"]) == (f"ann-{r8}-1", f"claim-ann-{r8}-1")
    assert (second["id"], second["claim_id"]) == (f"ann-{r8}-2", f"claim-ann-{r8}-2")
    for payload in (first, second):
        assert payload["operation"] == "CREATE_ANNOTATION"
        assert payload["locator"] is None
        assert payload["certainty"] in vocab.CERTAINTIES_AGENT and payload["certainty"] != "KNOWN"
        assert payload["audience"] in vocab.AUDIENCES
        assert re.fullmatch(r"^[A-Za-z][A-Za-z0-9_-]{1,63}$", payload["id"])
        assert re.fullmatch(r"^[A-Za-z][A-Za-z0-9_-]{1,63}$", payload["claim_id"])
    assert validate_proposal({"schema_version": 1, "status": "DRAFT", "summary": "s", "changes": changes,
                              "unknowns": [], "human_review_question": "q?"}) == []


def test_claim_value_defaults_to_content_and_non_annotation_items_get_no_payload() -> None:
    item = annotation_item()
    del item["annotation"]["claim_value"]
    payload = compiled(item)["changes"][0]["draft_payload"]
    assert payload["claim_value"] == payload["content"]
    unknown = annotation_item()
    unknown["epistemic"], unknown["annotation"] = "UNKNOWN", None
    assert compiled(unknown)["changes"][0]["draft_payload"] is None


def test_a_read_only_report_still_yields_one_gap_report_change() -> None:
    proposal = compiled()
    assert len(proposal["changes"]) == 1
    assert proposal["changes"][0]["change_type"] == "GAP_REPORT"
    assert proposal["changes"][0]["body"].startswith("【缺口】")


def test_the_generator_is_never_part_of_the_proposal_body() -> None:
    blob = json.dumps(compiled(source_request_item()), ensure_ascii=False)
    for word in ("generator", "STUB", "DEERFLOW"):
        assert word not in blob
    assert set(compiled(source_request_item())) == {"schema_version", "status", "summary", "changes", "unknowns", "human_review_question"}


def test_run8_is_stable_and_id_safe() -> None:
    assert run8("run_0123456789abcdef") == "01234567"
    assert re.fullmatch(r"[A-Za-z0-9]{8}", run8("run_a-b"))


def test_cross_layer_validation_catches_bad_payloads() -> None:
    base = compiled(annotation_item())
    assert validate_proposal(base) == []
    for mutate, code in [
        (lambda p: p["changes"][0]["draft_payload"].update(locator="卷三"), "P.LOCATOR"),
        (lambda p: p["changes"][0]["draft_payload"].update(certainty="KNOWN"), "P.CERTAINTY"),
        (lambda p: p["changes"][0]["draft_payload"].update(audience="MIDDLE"), "P.AUDIENCE"),
        (lambda p: p["changes"][0]["draft_payload"].update(id="1bad"), "P.ID_ID"),
        (lambda p: p["changes"][0]["draft_payload"].update(operation="DELETE"), "P.OPERATION"),
        (lambda p: p.update(status="APPROVED"), "P.STATUS"),
        (lambda p: p.update(changes=[]), "P.CHANGES_COUNT"),
    ]:
        proposal = json.loads(json.dumps(base))
        mutate(proposal)
        assert any(problem.startswith(code) for problem in validate_proposal(proposal)), code


# ---- enum consistency with proposal.schema.json (and between the three layers) ---------------------
def test_vocabulary_matches_proposal_schema() -> None:
    schema = json.loads(PROPOSAL_SCHEMA.read_text(encoding="utf-8"))
    change = schema["properties"]["changes"]["items"]["properties"]
    payload = change["draft_payload"]["oneOf"][1]["properties"]
    assert tuple(change["change_type"]["enum"]) == vocab.CHANGE_TYPES
    assert tuple(change["classification"]["enum"]) == vocab.CLASSIFICATIONS
    assert tuple(payload["annotation_kind"]["enum"]) == vocab.ANNOTATION_KINDS
    assert tuple(payload["audience"]["enum"]) == vocab.AUDIENCES        # PRIMARY|JUNIOR|SENIOR, not MIDDLE/GENERAL
    assert set(payload["certainty"]["enum"]) == set(vocab.CERTAINTIES_JAVA)  # the schema allows what Java allows
    assert set(vocab.CERTAINTIES_AGENT) == set(vocab.CERTAINTIES_JAVA) - {"KNOWN"}
    assert schema["properties"]["changes"]["maxItems"] == vocab.MAX_ITEMS


def test_agent_output_schema_matches_the_pydantic_model_and_vocabulary() -> None:
    schema = json.loads(OUTPUT_SCHEMA.read_text(encoding="utf-8"))
    item = schema["$defs"]["item"]["properties"]
    assert tuple(schema["properties"]["task_type"]["enum"]) == vocab.TASK_TYPES
    assert tuple(item["kind"]["enum"]) == vocab.ITEM_KINDS
    assert tuple(item["epistemic"]["enum"]) == vocab.EPISTEMICS
    assert tuple(x for x in item["severity"]["enum"] if x) == vocab.SEVERITIES
    ann = schema["$defs"]["annotation"]["properties"]
    assert tuple(ann["annotation_kind"]["enum"]) == vocab.ANNOTATION_KINDS
    assert tuple(ann["audience"]["enum"]) == vocab.AUDIENCES
    assert set(ann["certainty"]["enum"]) == set(vocab.CERTAINTIES_AGENT)
    assert {x for x in schema["$defs"]["source_request"]["properties"]["suggested_source_kind"]["enum"] if x} == set(vocab.SOURCE_KINDS)
    model_fields = set(AgentOutput.model_fields)
    assert {"schema_id", "task_type", "summary", "items", "unknowns", "human_review_question"} == model_fields
    assert set(schema["required"]) == {"schema", "task_type", "summary", "items", "unknowns", "human_review_question"}


def test_packaged_schema_copies_are_byte_identical_to_pipeline_contracts() -> None:
    """The image cannot COPY pipeline/ (.dockerignore), so the worker ships copies inside the package."""
    assert (PACKAGE_SCHEMAS / "agent-output.schema.json").read_bytes() == OUTPUT_SCHEMA.read_bytes()
    assert (PACKAGE_SCHEMAS / "proposal.schema.json").read_bytes() == PROPOSAL_SCHEMA.read_bytes()


def test_vocabulary_matches_the_other_two_validation_layers() -> None:
    """BFF models.py and the MCP server declare the same audience/certainty sets (parsed, not imported)."""
    agent = ROOT / "agent"
    mcp = (agent / "poetry-domain-mcp" / "src" / "poetry_domain_mcp" / "server.py").read_text(encoding="utf-8")
    bff = (agent / "agent-bff" / "src" / "agent_bff" / "models.py").read_text(encoding="utf-8")

    def frozenset_of(name: str) -> set[str]:
        node = next(n for n in ast.parse(mcp).body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == name)
        return {e.value for e in node.value.args[0].elts}

    assert frozenset_of("AGENT_AUDIENCES") == set(vocab.AUDIENCES)
    assert frozenset_of("AGENT_CERTAINTIES") == set(vocab.CERTAINTIES_AGENT)
    assert 'audience: Literal["PRIMARY", "JUNIOR", "SENIOR"]' in bff
    assert 'certainty: Literal["LIKELY", "DISPUTED", "UNKNOWN"]' in bff
