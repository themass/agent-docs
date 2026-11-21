"""Control-bridge client (httpx.MockTransport) and Java key-style normalisation."""
from __future__ import annotations

from typing import Any

import httpx
import pytest
from agent_worker.control import (
    ControlClient,
    ControlError,
    control_role,
    proposal_id_for,
    unwrap_envelope,
)
from agent_worker.naming import normalize_keys, to_snake
from helpers import CONTROL_TOKEN, MANDATE_ID, RUN_ID, WORK_ID, FakeBridge, minimal_output


def client(bridge: FakeBridge, sleeps: list[float] | None = None) -> ControlClient:
    return ControlClient("http://bridge", CONTROL_TOKEN, transport=bridge.transport(),
                         sleep=(sleeps.append if sleeps is not None else (lambda s: None)))


def scripted(*responses: Any) -> ControlClient:
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    return ControlClient("http://bridge", CONTROL_TOKEN, transport=httpx.MockTransport(handler), sleep=lambda s: None)


# ---- naming ---------------------------------------------------------------------------------------
def test_camel_keys_become_snake_but_id_keyed_maps_are_untouched() -> None:
    raw = {"workInfo": {"dynastyId": "d"}, "claimStatusById": {"claim-bgCity": "DRAFT", "ownerId": "x"},
           "auditRefs": [{"auditNonZero": []}], "already_snake": 1, "Title": "keep"}
    out = normalize_keys(raw)
    assert out["work_info"] == {"dynasty_id": "d"}
    assert out["claim_status_by_id"] == {"claim-bgCity": "DRAFT", "ownerId": "x"}   # keys are ids, not field names
    assert out["audit_refs"] == [{"audit_non_zero": []}] and out["already_snake"] == 1 and out["Title"] == "keep"
    assert to_snake("lineSeq") == "line_seq" and to_snake("line_seq") == "line_seq" and to_snake("ID") == "ID"


# ---- reads ----------------------------------------------------------------------------------------
def test_studio_view_is_fetched_with_the_control_token() -> None:
    bridge = FakeBridge()
    data = client(bridge).get_studio_view(WORK_ID)
    assert data["data"]["work"]["id"] == WORK_ID and bridge.token_seen == {CONTROL_TOKEN}
    assert bridge.requests == [("GET", f"/internal/works/{WORK_ID}/studio-view")]


def test_ids_are_validated_before_any_request() -> None:
    bridge = FakeBridge()
    c = client(bridge)
    for call in (lambda: c.get_studio_view("../../etc"), lambda: c.get_studio_view("Work"),
                 lambda: c.append_event("run_x/../y", "STEP", {}), lambda: c.set_state("nope", "FAILED"),
                 lambda: c.get_snapshot(WORK_ID, RUN_ID, "mandate bad")):
        with pytest.raises(ControlError) as info:
            call()
        assert info.value.reason.startswith("INVALID_") and not info.value.retryable
    assert bridge.requests == []


def test_a_read_is_retried_on_503_and_gives_up_after_the_bounded_attempts() -> None:
    bridge, sleeps = FakeBridge(), []
    bridge.fail_next("GET", r"studio-view$", [503, 503])
    assert client(bridge, sleeps).get_studio_view(WORK_ID)["status"] == "OK" and sleeps == [0.5, 1.5]
    bridge.fail_next("GET", r"studio-view$", [503, 503, 503, 503])
    with pytest.raises(ControlError) as info:
        client(bridge).get_studio_view(WORK_ID)
    assert info.value.retryable and info.value.reason == "HTTP_503"


def test_4xx_is_not_retried() -> None:
    bridge = FakeBridge()
    bridge.fail_next("GET", r"studio-view$", [404, 404])
    with pytest.raises(ControlError) as info:
        client(bridge).get_studio_view(WORK_ID)
    assert info.value.status == 404 and not info.value.retryable
    assert [r for r in bridge.requests if r[1].endswith("studio-view")] == [("GET", f"/internal/works/{WORK_ID}/studio-view")]


def test_envelope_statuses_map_to_retryable_or_not() -> None:
    for status, retryable in (("DOMAIN_API_UNAVAILABLE", True), ("DOMAIN_API_REJECTED", False),
                              ("REJECTED", False), ("CONFLICT", False)):
        with pytest.raises(ControlError) as info:
            unwrap_envelope({"status": status})
        assert info.value.retryable is retryable
    assert unwrap_envelope({"status": "REVIEW_REQUIRED", "data": {}})["status"] == "REVIEW_REQUIRED"
    with pytest.raises(ControlError):
        unwrap_envelope(["not", "an", "object"])


def test_malformed_json_and_network_errors_are_retryable_control_errors() -> None:
    c = scripted(httpx.Response(200, content=b"<html>"))
    with pytest.raises(ControlError) as info:
        c.get_studio_view(WORK_ID)
    assert info.value.reason == "BAD_JSON" and info.value.retryable
    c = scripted(httpx.ConnectError("refused"))
    with pytest.raises(ControlError) as info:
        c.get_studio_view(WORK_ID)
    assert info.value.reason == "NETWORK"
    c = scripted(httpx.ReadTimeout("slow"))
    with pytest.raises(ControlError) as info:
        c.get_studio_view(WORK_ID)
    assert info.value.reason == "TIMEOUT"


def test_no_response_body_ever_reaches_the_error_message() -> None:
    c = scripted(httpx.Response(500, json={"secret": "hunter2-model-text"}))
    with pytest.raises(ControlError) as info:
        c.get_studio_view(WORK_ID)
    assert "hunter2" not in str(info.value) and "hunter2" not in repr(info.value.__dict__)


def test_unconfigured_client_fails_closed() -> None:
    with pytest.raises(ControlError) as info:
        ControlClient("", "").get_studio_view(WORK_ID)
    assert info.value.reason == "NOT_CONFIGURED"
    assert not ControlClient("http://x", "").configured()


def test_load_context_falls_back_to_snapshot_plus_gap_report_when_the_bridge_is_older() -> None:
    bridge = FakeBridge()
    bridge.studio_view_404 = True
    seen: list[tuple[str, str]] = []
    data = client(bridge).load_context(WORK_ID, RUN_ID, MANDATE_ID, lambda tool, outcome, ms: seen.append((tool, outcome)))
    assert data["data"]["gap_report"]["audit_checks"] == 106 and "work" in data["data"]
    assert seen == [("studio_view", "error:HTTP_404"), ("snapshot", "ok"), ("gap_report", "ok")]
    assert {m for m, p in bridge.requests if p.endswith(("/snapshot", "/gap-report"))} == {"GET"}


# ---- writes ---------------------------------------------------------------------------------------
def test_event_state_and_admission_bodies() -> None:
    bridge = FakeBridge()
    c = client(bridge)
    c.append_event(RUN_ID, "STEP", {"name": "x"})
    c.set_state(RUN_ID, "AWAITING_REVIEW", "原因")
    c.set_state(RUN_ID, "FAILED")
    c.admit_running(RUN_ID, "poetry-" + RUN_ID, "df-1")
    assert bridge.events == [("STEP", {"name": "x"})]
    assert bridge.states == [("AWAITING_REVIEW", "原因"), ("FAILED", None)]
    assert bridge.admissions == [{"status": "RUNNING", "runtime_thread_id": "poetry-" + RUN_ID, "runtime_run_id": "df-1"}]


def test_an_event_post_is_never_replayed_after_an_ambiguous_failure() -> None:
    bridge = FakeBridge()
    bridge.fail_next("POST", r"/events$", [500])
    with pytest.raises(ControlError):
        client(bridge).append_event(RUN_ID, "STEP", {})
    assert len([r for r in bridge.requests if r[1].endswith("/events")]) == 1 and bridge.events == []   # 500 might have been applied
    bridge.fail_next("POST", r"/events$", [503])
    client(bridge).append_event(RUN_ID, "STEP", {})                                                      # 503 provably was not
    assert bridge.event_types() == ["STEP"]
    c = scripted(httpx.ConnectError("refused"), httpx.Response(200, json={"status": "OK"}))
    c.append_event(RUN_ID, "STEP", {})                                                                   # never reached the bridge


def test_state_writes_are_replay_safe_and_retried() -> None:
    bridge = FakeBridge()
    bridge.fail_next("PUT", r"/state$", [500, 502])
    client(bridge).set_state(RUN_ID, "FAILED", "x")
    assert bridge.states == [("FAILED", "x")]


def test_create_proposal_body_matches_what_the_bridge_expects() -> None:
    bridge = FakeBridge()
    proposal = {"schema_version": 1, "status": "DRAFT", "summary": "s", "changes": [], "unknowns": [], "human_review_question": "q?"}
    pid = client(bridge).create_proposal(run_id=RUN_ID, mandate_id=MANDATE_ID, work_id=WORK_ID,
                                         actor_role="RELEASE_MANAGER", proposal=proposal)
    body = bridge.proposals[f"worker:proposal:{RUN_ID}"]
    assert pid == proposal_id_for(RUN_ID) == "proposal_" + RUN_ID[4:]
    assert set(body) == {"proposal_id", "work_id", "run_id", "mandate_id", "actor_role", "idempotency_key", "proposal"}
    assert body["actor_role"] == "CONTENT_EDITOR"             # the bridge accepts only two roles
    assert body["idempotency_key"] == f"worker:proposal:{RUN_ID}" and 12 <= len(body["idempotency_key"]) <= 128
    assert body["proposal"] == proposal


def test_a_conflict_on_the_proposal_write_is_not_retried() -> None:
    bridge = FakeBridge()
    bridge.fail_next("POST", r"/internal/proposals$", [409, 409])
    with pytest.raises(ControlError) as info:
        client(bridge).create_proposal(run_id=RUN_ID, mandate_id=MANDATE_ID, work_id=WORK_ID,
                                       actor_role="CONTENT_EDITOR", proposal=minimal_output())
    assert not info.value.retryable and bridge.proposal_posts == 0


def test_role_mapping() -> None:
    assert [control_role(r) for r in ("CONTENT_EDITOR", "HISTORICAL_REVIEWER", "RELEASE_MANAGER", "PLATFORM_ADMIN")] == [
        "CONTENT_EDITOR", "HISTORICAL_REVIEWER", "CONTENT_EDITOR", "CONTENT_EDITOR"]


def test_ping() -> None:
    assert client(FakeBridge()).ping() is True
    assert scripted(httpx.Response(503)).ping() is False
