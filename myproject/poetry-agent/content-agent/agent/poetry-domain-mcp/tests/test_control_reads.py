"""Read-only forwards added to the control bridge for Studio and agent-worker (A-contract §4).

Boundary properties pinned here: authentication comes first, every query value is validated and
re-encoded, snapshot/gap-report get the Java agent headers from the bridge (not from the caller), and
no human-write route exists on the bridge. Java is replaced by httpx.MockTransport; nothing touches a
network or database. Written for the final test pass, not run during development.
"""
from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from poetry_domain_mcp import server
from starlette.testclient import TestClient

BASE = "http://java.test"
CONTROL = "control-secret-for-tests"
H = {"X-Poetry-Domain-Control-Token": CONTROL}


@pytest.fixture
def java(monkeypatch):
    class Java:
        def __init__(self):
            self.calls: list[httpx.Request] = []

    j = Java()

    def handler(request: httpx.Request) -> httpx.Response:
        j.calls.append(request)
        return httpx.Response(200, json={"status": "OK", "data": {"items": []}})

    real = httpx.AsyncClient
    monkeypatch.setattr(server.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setenv("POETRY_API_BASE_URL", BASE)
    monkeypatch.setenv("POETRY_AGENT_INTERNAL_TOKEN", "agent-internal")
    monkeypatch.setenv("POETRY_AGENT_ACTOR_ROLE", "CONTENT_EDITOR")
    monkeypatch.setenv("POETRY_DOMAIN_CONTROL_TOKEN", CONTROL)
    monkeypatch.setenv("MCP_INTERNAL_TOKEN", "mcp-secret-for-tests")
    j.client = TestClient(server.build_app())
    return j


LIST_ROUTES = [
    ("/internal/tasks", "/api/poetry/v1/agent-orchestration/tasks"),
    ("/internal/proposals", "/api/poetry/v1/agent-orchestration/proposals"),
    ("/internal/works", "/api/poetry/v1/agent-orchestration/works"),
    ("/internal/sources", "/api/poetry/v1/agent-orchestration/sources"),
    ("/internal/works/work-chun-wang/coverage", "/api/poetry/v1/agent-orchestration/works/work-chun-wang/coverage"),
    ("/internal/works/work-chun-wang/studio-view", "/api/poetry/v1/agent-orchestration/works/work-chun-wang/studio-view"),
]


@pytest.mark.parametrize("path,java_path", LIST_ROUTES)
def test_reads_require_the_control_token_before_anything_else(java, path, java_path):
    assert java.client.get(path).status_code == 401
    assert java.client.get(path, headers={"X-Poetry-Domain-Control-Token": "wrong"}).status_code == 401
    assert java.calls == []


@pytest.mark.parametrize("path,java_path", LIST_ROUTES)
def test_authorised_reads_reach_the_matching_java_path_with_the_agent_token(java, path, java_path):
    assert java.client.get(path, headers=H).status_code == 200
    request = java.calls[0]
    assert request.url.path == java_path
    assert request.headers["X-Poetry-Agent-Internal-Token"] == "agent-internal"


@pytest.mark.parametrize("query", [
    "limit=abc", "limit=1000", "offset=-1", "status=draft", "status=A%0AB", "work_id=../admin",
    "unknown=1", "limit=1&limit=2", "task_type=X Y",
])
def test_bad_query_values_never_reach_java(java, query):
    assert java.client.get(f"/internal/tasks?{query}", headers=H).status_code == 400
    assert java.calls == []


def test_valid_filters_are_forwarded_encoded_and_sorted(java):
    java.client.get("/internal/tasks?status=RUNNING&work_id=work-chun-wang&limit=20", headers=H)
    assert str(java.calls[0].url.query, "ascii") == "limit=20&status=RUNNING&work_id=work-chun-wang"


@pytest.mark.parametrize("path", [
    "/internal/works/x%2F..%2Fadmin/coverage", "/internal/works/A_B/studio-view", "/internal/tasks/task_x%3Fa=1/runs",
    "/internal/proposals/proposal_x%2F..%2Faudit/items",
])
def test_malformed_path_ids_are_rejected_before_java(java, path):
    assert java.client.get(path, headers=H).status_code in {400, 404}
    assert java.calls == []


def test_the_list_and_create_proposal_routes_coexist_on_one_path(java):
    assert java.client.get("/internal/proposals", headers=H).status_code == 200
    created = java.client.post("/internal/proposals", headers=H, json={})
    assert created.status_code == 400  # reaches the create handler, which validates the body
    assert len(java.calls) == 1


def agent_read_query():
    return f"run_id=run_{uuid4().hex}&mandate_id=mandate_{uuid4().hex}"


@pytest.mark.parametrize("suffix,java_suffix", [("snapshot", "snapshot"), ("gap-report", "integrity-gap-report")])
def test_snapshot_and_gap_report_get_java_agent_headers_from_the_bridge(java, suffix, java_suffix):
    query = agent_read_query()
    assert java.client.get(f"/internal/works/work-chun-wang/{suffix}?{query}", headers=H).status_code == 200
    request = java.calls[0]
    assert request.url.path == f"/api/poetry/v1/works/work-chun-wang/{java_suffix}"
    assert request.headers["X-Poetry-Agent-Run-Id"].startswith("run_")
    assert request.headers["X-Poetry-Agent-Mandate-Id"].startswith("mandate_")
    key = request.headers["Idempotency-Key"]
    assert key.startswith("control:read:") and 0 < len(key) <= 128
    assert request.headers["X-Poetry-Agent-Role"] == "CONTENT_EDITOR"


@pytest.mark.parametrize("query", ["", "run_id=run_1", "mandate_id=mandate_1", "run_id=x&mandate_id=y", "run_id=run_a/../b&mandate_id=mandate_c"])
def test_snapshot_requires_valid_run_and_mandate_ids(java, query):
    assert java.client.get(f"/internal/works/work-chun-wang/snapshot?{query}", headers=H).status_code == 400
    assert java.calls == []


# Reads that legitimately mention human-only vocabulary. Anything not listed here must stay off the bridge,
# and a write method under any of these words is never allowed. Adding an entry is a deliberate act.
HUMAN_READ_ALLOWLIST = {"/internal/works/{work_id}/studio-view"}


def test_there_is_no_human_write_route_on_the_bridge():
    """The bridge must never expose locator / verification / citation writes.

    The first version of this test rejected any path containing ("studio", "locator", "verification",
    "citation") regardless of method, which also failed a GET-only studio *view* the agent needs to read.
    The property worth guarding is "no human write", so writes are checked unconditionally and reads are
    checked against an allowlist that has to be edited on purpose.
    """
    words = ("studio", "locator", "verification", "citation")
    routes = [r for r in server.build_app().app.routes if getattr(r, "path", "")]
    writes = [f"{sorted(getattr(r, 'methods', []) or [])} {r.path}" for r in routes
              if any(w in r.path for w in words)
              and (getattr(r, "methods", set()) or set()) - {"GET", "HEAD"}]
    assert not writes, f"human-write-looking routes on the bridge: {writes}"
    unlisted = [r.path for r in routes if any(w in r.path for w in words) and r.path not in HUMAN_READ_ALLOWLIST]
    assert not unlisted, f"new human-vocabulary read route, add it to HUMAN_READ_ALLOWLIST after review: {unlisted}"


# ------------------------------------------------------------ executable payload governance

def _draft(payload: dict) -> dict:
    return {"run_id": f"run_{uuid4().hex}", "mandate_id": f"mandate_{uuid4().hex}", "actor_role": "CONTENT_EDITOR",
            "idempotency_key": "k" * 16, "work_id": "work-chun-wang",
            "proposal": {"status": "DRAFT", "changes": [{"draft_payload": payload}]}}


GOOD = {"operation": "CREATE_ANNOTATION", "audience": "PRIMARY", "certainty": "LIKELY", "locator": None}


def test_a_well_formed_agent_annotation_passes_the_draft_only_validator():
    server.DraftProposalRequest.model_validate(_draft(GOOD))


@pytest.mark.parametrize("over", [
    {"locator": "卷二百二十五"}, {"certainty": "KNOWN"}, {"audience": "MIDDLE"}, {"audience": "GENERAL"}, {"certainty": "HIGH"},
])
def test_an_agent_annotation_cannot_carry_a_locator_known_certainty_or_a_foreign_vocabulary(over):
    with pytest.raises(ValueError):
        server.DraftProposalRequest.model_validate(_draft({**GOOD, **over}))


# ---- A-05: the review/apply split ----------------------------------------------------------------
REVIEW = "review-secret-for-tests"
HUMAN = {**H, "X-Poetry-Domain-Review-Token": REVIEW}


def test_the_worker_token_alone_cannot_review_or_apply(monkeypatch, java):
    """The worker holds the control token. If that were enough to review, it could approve its own output."""
    monkeypatch.setenv("POETRY_DOMAIN_REVIEW_TOKEN", REVIEW)
    client = TestClient(server.build_app())
    for path in ("/internal/proposals/proposal_abc/reviews", "/internal/proposals/proposal_abc/apply"):
        res = client.post(path, headers=H, json={})
        assert res.status_code == 401, path
        assert "review" in res.json()["error"], res.json()
    assert java.calls == [], "a rejected review must not reach Java"


def test_the_review_token_alone_is_not_enough_either(monkeypatch, java):
    """Two secrets: the human side still needs the bridge token to speak to the control bridge at all."""
    monkeypatch.setenv("POETRY_DOMAIN_REVIEW_TOKEN", REVIEW)
    client = TestClient(server.build_app())
    res = client.post("/internal/proposals/proposal_abc/reviews",
                      headers={"X-Poetry-Domain-Review-Token": REVIEW}, json={})
    assert res.status_code == 401


def test_a_wrong_review_token_is_refused(monkeypatch, java):
    monkeypatch.setenv("POETRY_DOMAIN_REVIEW_TOKEN", REVIEW)
    client = TestClient(server.build_app())
    res = client.post("/internal/proposals/proposal_abc/apply",
                      headers={**H, "X-Poetry-Domain-Review-Token": "not-the-review-secret"}, json={})
    assert res.status_code == 401


def test_an_unset_review_token_never_matches(monkeypatch, java):
    """Fail closed: an empty expected value must not turn an absent header into an authorization."""
    monkeypatch.delenv("POETRY_DOMAIN_REVIEW_TOKEN", raising=False)
    client = TestClient(server.build_app())
    for headers in (H, {**H, "X-Poetry-Domain-Review-Token": ""}):
        assert client.post("/internal/proposals/proposal_abc/reviews", headers=headers, json={}).status_code == 401


def test_creating_a_proposal_still_needs_only_the_control_token(monkeypatch, java):
    """The worker must keep its own job: it creates proposals, it just cannot decide them."""
    monkeypatch.setenv("POETRY_DOMAIN_REVIEW_TOKEN", REVIEW)
    client = TestClient(server.build_app())
    res = client.post("/internal/proposals", headers=H, json={})
    assert res.status_code != 401, res.text


def test_both_tokens_together_reach_java(monkeypatch, java):
    monkeypatch.setenv("POETRY_DOMAIN_REVIEW_TOKEN", REVIEW)
    client = TestClient(server.build_app())
    res = client.post("/internal/proposals/proposal_abc/apply",
                      headers=HUMAN, json={"work_id": "work_chunwang", "run_id": "run_abc",
                                           "mandate_id": "mandate_abc", "actor_role": "CONTENT_EDITOR",
                                           "idempotency_key": "bff:apply-proposal:proposal_abc:review_abc",
                                           "review_id": "review_abc"})
    assert res.status_code == 200, res.text
    assert len(java.calls) == 1
