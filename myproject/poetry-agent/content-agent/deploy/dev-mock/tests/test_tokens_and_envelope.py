"""令牌隔离与响应信封形状。"""
from __future__ import annotations

from fastapi.testclient import TestClient
from mock_domain_api import create_app
from mock_test_helpers import (
    AGENT,
    ORCH_HEADERS,
    REVIEWER,
    STUDIO,
    STUDIO_HEADERS,
    WORK,
    agent_headers,
)

API = "/api/poetry/v1"


def test_agent_surface_requires_agent_token(client):
    for headers in ({}, {"X-Poetry-Agent-Internal-Token": "wrong"}, STUDIO_HEADERS):
        r = client.get(f"{API}/agent-orchestration/works", headers=headers)
        assert r.status_code == 403
        assert r.json()["status"] == "REJECTED"


def test_studio_token_does_not_open_agent_snapshot(client):
    h = agent_headers()
    h["X-Poetry-Agent-Internal-Token"] = STUDIO
    assert client.get(f"{API}/works/{WORK}/snapshot", headers=h).status_code == 403


def test_agent_token_does_not_open_studio(client):
    body = {**REVIEWER, "decisions": [{"item_index": 0, "decision": "APPROVE"}]}
    for headers in ({}, {"X-Poetry-Studio-Reviewer-Token": AGENT}, ORCH_HEADERS):
        r = client.put(f"{API}/studio/proposals/p/items", headers=headers, json=body)
        assert r.status_code == 401
        assert r.json()["status"] == "REJECTED"


def test_unconfigured_tokens():
    app = create_app(agent_token="", reviewer_token="")
    with TestClient(app) as c:
        r = c.get(f"{API}/agent-orchestration/works", headers={"X-Poetry-Agent-Internal-Token": "x"})
        assert r.status_code == 403 and "disabled" in r.json()["data"]["reason"]
        r = c.put(f"{API}/studio/proposals/p/items", headers={"X-Poetry-Studio-Reviewer-Token": "x"}, json={})
        assert r.status_code == 503


def test_agent_snapshot_requires_run_mandate_key_and_role(client):
    base = agent_headers()
    for drop in ("X-Poetry-Agent-Run-Id", "X-Poetry-Agent-Mandate-Id", "Idempotency-Key"):
        h = {k: v for k, v in base.items() if k != drop}
        assert client.get(f"{API}/works/{WORK}/snapshot", headers=h).status_code == 403
    assert client.get(f"{API}/works/{WORK}/snapshot", headers=agent_headers(role="RELEASE_MANAGER")).status_code == 403
    assert client.get(f"{API}/works/{WORK}/snapshot", headers=agent_headers(key="k" * 129)).status_code == 403


def test_new_read_routes_do_not_need_run_headers(client):
    assert client.get(f"{API}/agent-orchestration/works", headers=ORCH_HEADERS).status_code == 200


def test_default_naming_is_snake_like_real_java(client):
    snap = client.get(f"{API}/works/{WORK}/snapshot", headers=agent_headers()).json()
    assert set(snap) == {"status", "data", "audit_refs", "next_action"}
    assert "work_info" in snap["data"] and "entity_type" in snap["data"]["work"]
    assert "dynasty_id" in snap["data"]["work_info"]
    gaps = client.get(f"{API}/works/{WORK}/integrity-gap-report", headers=agent_headers()).json()["data"]
    assert {"work_id", "audit_checks", "audit_non_zero"} <= set(gaps)
    assert {"code", "severity", "message", "target_ref"} == set(gaps["gaps"][0])
    new = client.get(f"{API}/agent-orchestration/works", headers=ORCH_HEADERS).json()
    assert set(new) == {"status", "data", "audit_refs", "next_action"}


def test_env_default_naming_is_snake(monkeypatch):
    from mock_domain_api import create_app_from_env

    monkeypatch.delenv("MOCK_JSON_NAMING", raising=False)
    assert create_app_from_env().state.mock.naming == "snake"
    monkeypatch.setenv("MOCK_JSON_NAMING", "camel")
    assert create_app_from_env().state.mock.naming == "camel"
    monkeypatch.setenv("MOCK_JSON_NAMING", "bogus")
    assert create_app_from_env().state.mock.naming == "snake"


def test_camel_option_simulates_a_broken_host_for_legacy_records_only(camel_client):
    c = camel_client
    snap = c.get(f"{API}/works/{WORK}/snapshot", headers=agent_headers()).json()
    assert set(snap) == {"status", "data", "auditRefs", "nextAction"}
    assert "workInfo" in snap["data"] and "entityType" in snap["data"]["work"]
    gaps = c.get(f"{API}/works/{WORK}/integrity-gap-report", headers=agent_headers()).json()["data"]
    assert {"workId", "auditChecks", "auditNonZero"} <= set(gaps)
    # Map 形态的旧端点和新端点键名恒为 snake_case,包括信封
    new = c.get(f"{API}/agent-orchestration/works", headers=ORCH_HEADERS).json()
    assert set(new) == {"status", "data", "audit_refs", "next_action"}
    assert c.get(f"{API}/agent-orchestration/tasks/nope", headers=ORCH_HEADERS).status_code == 400


def test_requests_accept_snake_and_camel_bodies(client):
    snake = {"work_id": WORK, "proposal": {"schema_version": 1, "status": "DRAFT", "summary": "s",
                                           "human_review_question": "q",
                                           "changes": [{"change_type": "GAP_REPORT", "classification": "DRAFT",
                                                        "body": "g"}]}}
    camel = {"workId": WORK, "proposal": snake["proposal"]}
    assert client.post(f"{API}/draft/proposals", headers=agent_headers(key="body-snake-0001"), json=snake).status_code == 200
    assert client.post(f"{API}/draft/proposals", headers=agent_headers(key="body-camel-0001"), json=camel).status_code == 200


def test_error_shapes(client):
    r = client.get(f"{API}/works/nope-x/snapshot", headers=agent_headers())
    assert r.status_code == 400
    assert r.json() == {"status": "REJECTED", "data": {"reason": "work not found"},
                        "audit_refs": [], "next_action": "REPLAN"}
    r = client.post(f"{API}/draft/proposals/proposal_x/apply", headers=agent_headers(), json={"review_id": "r"})
    assert r.status_code == 400  # 提案不存在是 Rejected,不是 404


def test_malformed_body_is_spring_style_400(client):
    r = client.post(f"{API}/draft/proposals", headers={**agent_headers(), "Content-Type": "application/json"},
                    content="{bad")
    assert r.status_code == 400
    assert r.json() == {"status": 400, "error": "Bad Request"}


def test_gap_report_matches_java_logic(client):
    codes = [g["code"] for g in client.get(f"{API}/works/{WORK}/integrity-gap-report",
                                           headers=agent_headers()).json()["data"]["gaps"]]
    assert codes == ["CLAIM_VERIFIED_CITATION_MISSING", "TEXT_SOURCE_NOT_VERIFIED", "ANNOTATION_COVERAGE_LOW"]
    empty = client.get(f"{API}/works/work-demo-empty/integrity-gap-report", headers=agent_headers()).json()["data"]
    assert [g["code"] for g in empty["gaps"]] == (
        ["TEXT_VERSION_MISSING", "TEXT_LINES_MISSING"] + ["BACKGROUND_LAYER_MISSING"] * 4
        + ["ANNOTATION_COVERAGE_LOW"])
    assert empty["audit_checks"] == 106
