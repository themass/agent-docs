"""poetry-domain-mcp is the only process allowed to reach the Java Poetry API.

These tests pin the boundary properties the platform's design depends on:
what tools exist, what an LLM-controlled argument can and cannot do to the outgoing URL,
and who may use the BFF control bridge. No network or database is touched: the Java API is
replaced by an in-process httpx.MockTransport.
"""
from __future__ import annotations

import asyncio
import re
from uuid import uuid4

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError
from poetry_domain_mcp import server
from pydantic import ValidationError
from starlette.testclient import TestClient

BASE = "http://java.test"
CONTROL_TOKEN = "control-secret-for-tests"
MCP_TOKEN = "mcp-secret-for-tests"


def ids():
    """Ids exactly as agent-bff mints them (agent_bff/main.py): prefix + uuid4().hex."""
    return {
        "run": f"run_{uuid4().hex}",
        "mandate": f"mandate_{uuid4().hex}",
        "task": f"task_{uuid4().hex}",
        "proposal": f"proposal_{uuid4().hex}",
        "review": f"review_{uuid4().hex}",
    }


def tool_request(i=None):
    i = i or ids()
    return {
        "run_id": i["run"],
        "mandate_id": i["mandate"],
        "actor_role": "CONTENT_EDITOR",
        "idempotency_key": "k" * 16,
    }


@pytest.fixture
def domain(monkeypatch):
    """Fake Java API. `domain.calls` records every outgoing request; set `domain.reply`."""

    class Domain:
        def __init__(self):
            self.calls: list[httpx.Request] = []
            self.reply = lambda: httpx.Response(200, json={"status": "OK", "data": {}})

    d = Domain()

    def handler(request: httpx.Request) -> httpx.Response:
        d.calls.append(request)
        out = d.reply()
        if isinstance(out, Exception):
            raise out
        return out

    real = httpx.AsyncClient
    monkeypatch.setattr(
        server.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw)
    )
    monkeypatch.setenv("POETRY_API_BASE_URL", BASE)
    monkeypatch.setenv("POETRY_AGENT_INTERNAL_TOKEN", "agent-internal")
    monkeypatch.setenv("POETRY_AGENT_ACTOR_ROLE", "CONTENT_EDITOR")
    monkeypatch.setenv("POETRY_DOMAIN_CONTROL_TOKEN", CONTROL_TOKEN)
    monkeypatch.setenv("MCP_INTERNAL_TOKEN", MCP_TOKEN)
    return d


def call_tool(name, args):
    """Go through the SDK so argument validation runs exactly as for a real model call."""
    try:
        return asyncio.run(server.mcp.call_tool(name, args))
    except ToolError as exc:  # also covers UnexpectedToolError, which subclasses it
        # Rejecting a bad argument is a legitimate outcome. What matters, and what callers assert,
        # is whether a request reached the fake Java API (`domain.calls`).
        return exc


# --------------------------------------------------------------------------- tool surface


def test_exactly_five_tools_and_none_can_publish_verify_delete_or_run_sql():
    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert names == {
        "get_work_snapshot",
        "get_integrity_gap_report",
        "create_draft_proposal",
        "apply_approved_draft",
        "request_compile",
    }
    forbidden = re.compile(r"publish|retract|verify|delete|remove|sql|query|exec", re.IGNORECASE)
    assert [n for n in names if forbidden.search(n)] == []


# --------------------------------------------------------------------------- DRAFT-only


def draft(**over):
    i = ids()
    body = {
        **tool_request(i),
        "work_id": "work-chun-wang",
        "proposal": {"status": "DRAFT", "changes": []},
    }
    body.update(over)
    return body


def test_draft_proposal_must_be_draft():
    for status in ["PUBLISHED", "VERIFIED", "", None]:
        with pytest.raises(ValidationError):
            server.DraftProposalRequest.model_validate(
                draft(proposal={"status": status, "changes": []})
            )


@pytest.mark.parametrize(
    "operation", ["PUBLISH", "SET_VERIFIED", "DELETE_CONTENT", "RAW_SQL", "create_annotation", None]
)
def test_only_create_annotation_is_an_executable_operation(operation):
    proposal = {"status": "DRAFT", "changes": [{"draft_payload": {"operation": operation}}]}
    with pytest.raises(ValidationError):
        server.DraftProposalRequest.model_validate(draft(proposal=proposal))


def test_create_annotation_draft_is_accepted():
    proposal = {
        "status": "DRAFT",
        "changes": [{"draft_payload": {"operation": "CREATE_ANNOTATION"}}],
    }
    assert server.DraftProposalRequest.model_validate(draft(proposal=proposal))


def test_unknown_fields_are_rejected_so_an_agent_cannot_smuggle_authority():
    for field in ["publish", "verified", "sql", "actor_override"]:
        with pytest.raises(ValidationError):
            server.DraftProposalRequest.model_validate(draft(**{field: True}))


def test_actor_role_cannot_be_escalated_by_the_model():
    for role in ["PLATFORM_ADMIN", "RELEASE_MANAGER", "ROOT", ""]:
        with pytest.raises(ValidationError):
            server.ToolRequest.model_validate({**tool_request(), "actor_role": role})


def test_real_minted_ids_are_accepted_by_every_model():
    """Guards against over-tightening: these are the shapes agent-bff actually produces."""
    i = ids()
    server.ToolRequest.model_validate(tool_request(i))
    server.ApplyApprovedDraftRequest.model_validate(
        {**tool_request(i), "proposal_id": i["proposal"], "review_id": i["review"]}
    )
    server.DraftProposalRequest.model_validate(draft(proposal_id=i["proposal"]))
    server.CompileRequest.model_validate(
        {**tool_request(i), "work_id": "work-chun-wang", "script_version": "1.0.0"}
    )
    server.ProposalReviewForwardRequest.model_validate(
        {
            **tool_request(i),
            "work_id": "work-chun-wang",
            "review_id": i["review"],
            "reviewer_id": "editor-1",
            "decision": "APPROVE",
        }
    )


# --------------------------------------------------------------------------- URL integrity

TRAVERSAL = ["x/../../admin", "x?y=1", "x#frag", "../x", "x/y", "x y", "x\n", "", "x%2f..%2f"]


@pytest.mark.parametrize("work_id", TRAVERSAL)
@pytest.mark.parametrize("tool", ["get_work_snapshot", "get_integrity_gap_report"])
def test_read_tools_never_let_work_id_change_the_outgoing_path(domain, tool, work_id):
    call_tool(tool, {"work_id": work_id, "request": tool_request()})
    assert domain.calls == [], f"{tool}({work_id!r}) reached Java as {domain.calls[0].url}"


@pytest.mark.parametrize("tool,suffix", [
    ("get_work_snapshot", "snapshot"),
    ("get_integrity_gap_report", "integrity-gap-report"),
])
def test_read_tools_send_one_get_to_the_expected_url_with_no_body(domain, tool, suffix):
    call_tool(tool, {"work_id": "work-chun-wang", "request": tool_request()})
    assert len(domain.calls) == 1
    sent = domain.calls[0]
    assert sent.method == "GET"
    assert str(sent.url) == f"{BASE}/api/poetry/v1/works/work-chun-wang/{suffix}"
    assert sent.content == b""


@pytest.mark.parametrize("bad", [
    "proposal_x/../../../audit", "proposal_x?admin=1", "proposal_x#f", "proposal_x y", "proposal_",
])
def test_apply_never_lets_proposal_id_change_the_outgoing_path(domain, bad):
    i = ids()
    call_tool(
        "apply_approved_draft",
        {"request": {**tool_request(i), "proposal_id": bad, "review_id": i["review"]}},
    )
    assert domain.calls == [], f"proposal_id {bad!r} reached Java as {domain.calls[0].url}"


@pytest.mark.parametrize("bad", ["review_x/../y", "review_x?z=1", "review_"])
def test_review_id_is_anchored_too(bad):
    i = ids()
    with pytest.raises(ValidationError):
        server.ApplyApprovedDraftRequest.model_validate(
            {**tool_request(i), "proposal_id": i["proposal"], "review_id": bad}
        )


# --------------------------------------------------------------------------- call_domain


def test_without_a_java_api_the_result_is_an_explicit_failure_never_a_fake_success(monkeypatch):
    monkeypatch.delenv("POETRY_API_BASE_URL", raising=False)
    out = asyncio.run(server.call_domain("GET", "/x"))
    assert out["status"] == "DOMAIN_API_UNAVAILABLE"
    assert out["data"] == {}


def test_authority_comes_from_deployment_environment_not_from_the_payload(domain):
    asyncio.run(
        server.call_domain(
            "POST", "/x", {**tool_request(), "actor_role": "HISTORICAL_REVIEWER", "x": 1}
        )
    )
    headers = domain.calls[0].headers
    assert headers["X-Poetry-Agent-Role"] == "CONTENT_EDITOR"
    assert headers["X-Poetry-Agent-Internal-Token"] == "agent-internal"


def test_run_mandate_and_idempotency_are_forwarded_as_headers_on_get(domain):
    i = ids()
    asyncio.run(server.call_domain("GET", "/x", tool_request(i)))
    sent = domain.calls[0]
    assert sent.headers["X-Poetry-Agent-Run-Id"] == i["run"]
    assert sent.headers["X-Poetry-Agent-Mandate-Id"] == i["mandate"]
    assert sent.headers["Idempotency-Key"] == "k" * 16
    assert sent.content == b"" and sent.url.query == b""


def test_a_rejected_request_is_reported_as_rejected_with_its_http_status(domain):
    domain.reply = lambda: httpx.Response(409, json={"error": "conflict"})
    out = asyncio.run(server.call_domain("POST", "/x", {}))
    assert out["status"] == "DOMAIN_API_REJECTED"
    assert out["http_status"] == 409
    assert out["data"] == {"error": "conflict"}


def test_a_transport_failure_is_unavailable_not_success(domain):
    domain.reply = lambda: httpx.ConnectError("boom")
    out = asyncio.run(server.call_domain("GET", "/x"))
    assert out["status"] == "DOMAIN_API_UNAVAILABLE"
    assert out["next_action"] == "REPLAN"


def test_non_json_and_non_dict_bodies_are_wrapped_not_trusted(domain):
    domain.reply = lambda: httpx.Response(200, text="<html>oops</html>")
    assert asyncio.run(server.call_domain("GET", "/x"))["raw"].startswith("<html>")
    domain.reply = lambda: httpx.Response(200, json=[1, 2])
    assert asyncio.run(server.call_domain("GET", "/x"))["data"] == [1, 2]


# --------------------------------------------------------------------------- control bridge


@pytest.fixture
def client(domain):
    return TestClient(server.build_app())


def control_headers(token=CONTROL_TOKEN):
    return {"X-Poetry-Domain-Control-Token": token}


CONTROL_ROUTES = [
    ("GET", "/internal/tasks/task_abc"),
    ("GET", "/internal/runs/run_abc"),
    ("GET", "/internal/runs/run_abc/events"),
    ("GET", "/internal/proposals/proposal_abc"),
    ("POST", "/internal/tasks"),
    ("POST", "/internal/proposals"),
    ("PUT", "/internal/runs/run_abc/state"),
]


@pytest.mark.parametrize("method,path", CONTROL_ROUTES)
def test_control_routes_reject_a_missing_or_wrong_token(client, domain, method, path):
    assert client.request(method, path, json={}).status_code == 401
    assert client.request(method, path, json={}, headers=control_headers("wrong")).status_code == 401
    assert domain.calls == []


@pytest.mark.parametrize("method,path", CONTROL_ROUTES)
def test_an_unset_control_token_never_authorizes_an_empty_header(
    client, domain, monkeypatch, method, path
):
    monkeypatch.delenv("POETRY_DOMAIN_CONTROL_TOKEN", raising=False)
    for headers in ({}, {"X-Poetry-Domain-Control-Token": ""}):
        assert client.request(method, path, json={}, headers=headers).status_code == 401
    assert domain.calls == []


def test_control_response_maps_java_failures_to_honest_status_codes(client, domain):
    domain.reply = lambda: httpx.Response(409, json={"error": "stale"})
    r = client.get("/internal/runs/run_abc", headers=control_headers())
    assert r.status_code == 409 and r.json()["status"] == "DOMAIN_API_REJECTED"

    domain.reply = lambda: httpx.ConnectError("down")
    r = client.get("/internal/runs/run_abc", headers=control_headers())
    assert r.status_code == 503 and r.json()["status"] == "DOMAIN_API_UNAVAILABLE"


@pytest.mark.parametrize("after", ["abc", "-1", "1.5", "1;DROP", "²", "١٢٣", ""])
def test_after_event_id_must_be_plain_ascii_digits(client, domain, after):
    r = client.get(
        "/internal/runs/run_abc/events", params={"after_event_id": after}, headers=control_headers()
    )
    assert r.status_code == 400, f"{after!r} was forwarded to Java"
    assert domain.calls == []


def test_after_event_id_defaults_to_zero_and_accepts_digits(client, domain):
    assert client.get("/internal/runs/run_abc/events", headers=control_headers()).status_code == 200
    assert domain.calls[-1].url.query == b"after_event_id=0"
    client.get(
        "/internal/runs/run_abc/events", params={"after_event_id": "42"}, headers=control_headers()
    )
    assert domain.calls[-1].url.query == b"after_event_id=42"


@pytest.mark.parametrize("segment", ["..", "a b", "a%3Fb"])
def test_control_path_ids_cannot_alter_the_forwarded_path(client, domain, segment):
    for path in (
        f"/internal/tasks/{segment}",
        f"/internal/runs/{segment}",
        f"/internal/proposals/{segment}",
    ):
        r = client.get(path, headers=control_headers())
        assert r.status_code in (400, 404), f"{path} -> {r.status_code}"
    assert domain.calls == []


def test_bad_control_bodies_are_400_and_never_forwarded(client, domain):
    r = client.post("/internal/tasks", json={"task_id": "nope"}, headers=control_headers())
    assert r.status_code == 400
    assert domain.calls == []


# --------------------------------------------------------------------------- /mcp auth


def test_mcp_endpoint_requires_the_deployment_bearer_token(domain):
    app = TestClient(server.build_app())
    assert app.post("/mcp", json={}).status_code == 401
    assert app.post("/mcp", json={}, headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_mcp_endpoint_is_closed_when_no_token_is_configured(domain, monkeypatch):
    monkeypatch.delenv("MCP_INTERNAL_TOKEN", raising=False)
    app = TestClient(server.build_app())
    assert app.post("/mcp", json={}, headers={"Authorization": "Bearer "}).status_code == 401
    assert app.post("/mcp", json={}).status_code == 401
