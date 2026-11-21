"""The /mcp endpoint must actually serve a valid, authenticated client (review item A-01).

The earlier tests only asserted 401 for a missing/wrong token, so they passed while every request with a
*valid* token failed with HTTP 500 ("Task group is not initialized"): the outer Starlette app did not
run the lifespan of the mounted MCP app. These tests complete a real MCP handshake.

Two details matter:

* ``with TestClient(app)`` is what makes the lifespan run (as uvicorn does at startup). A bare
  ``TestClient(app)`` never starts it, so a test written that way would not exercise the fix.
* Each ``build_app()`` creates its own session manager, so building one per test is safe.

No network and no database. Written for the final test pass, not run during development.
"""
from __future__ import annotations

import json

import pytest
from poetry_domain_mcp import server
from starlette.testclient import TestClient

MCP_TOKEN = "mcp-secret-for-tests"
HEADERS = {
    "Authorization": f"Bearer {MCP_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}
READ_ONLY = ["get_integrity_gap_report", "get_work_snapshot"]
ALL_FIVE = ["apply_approved_draft", "create_draft_proposal", "get_integrity_gap_report",
            "get_work_snapshot", "request_compile"]
WRITE_TOOLS = ["apply_approved_draft", "create_draft_proposal", "request_compile"]


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("MCP_INTERNAL_TOKEN", MCP_TOKEN)
    monkeypatch.setenv("POETRY_DOMAIN_CONTROL_TOKEN", "control-secret-for-tests")
    monkeypatch.setenv("POETRY_AGENT_INTERNAL_TOKEN", "agent-internal")
    monkeypatch.setenv("POETRY_API_BASE_URL", "")  # tool calls must then fail explicitly, never fake success


def payload(response) -> dict:
    """The transport answers plain JSON or a one-event SSE stream; accept both."""
    text = response.text
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        data = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
        text = data[-1] if data else "{}"
    return json.loads(text)


def rpc(client, method, params=None, ident=1, session=None):
    message = {"jsonrpc": "2.0", "method": method}
    if ident is not None:
        message["id"] = ident
    if params is not None:
        message["params"] = params
    headers = dict(HEADERS)
    if session:
        headers["Mcp-Session-Id"] = session
    return client.post("/mcp", headers=headers, content=json.dumps(message))


def handshake(client):
    init = rpc(client, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                       "clientInfo": {"name": "test", "version": "0"}})
    session = init.headers.get("mcp-session-id")
    rpc(client, "notifications/initialized", None, ident=None, session=session)
    return init, session


def test_initialize_with_a_valid_token_succeeds(env):
    with TestClient(server.build_app(), raise_server_exceptions=False) as client:
        init, _ = handshake(client)
        assert init.status_code == 200, init.text[:200]
        assert payload(init)["result"]["serverInfo"]["name"] == "poetry-domain"


def served_tool_names(client, session):
    listed = rpc(client, "tools/list", {}, ident=2, session=session)
    assert listed.status_code == 200, listed.text[:200]
    return sorted(tool["name"] for tool in payload(listed)["result"]["tools"])


def test_by_default_only_the_two_read_tools_are_served(env):
    with TestClient(server.build_app(), raise_server_exceptions=False) as client:
        _, session = handshake(client)
        assert served_tool_names(client, session) == READ_ONLY


@pytest.mark.parametrize("tool", WRITE_TOOLS)
def test_a_write_tool_cannot_be_called_over_http_by_default(env, tool):
    """Server-side enforcement (A-12): the holder of the MCP token cannot reach a write tool at all."""
    with TestClient(server.build_app(), raise_server_exceptions=False) as client:
        _, session = handshake(client)
        body = payload(rpc(client, "tools/call", {"name": tool, "arguments": {}}, ident=9, session=session))
        assert "error" in body or body.get("result", {}).get("isError") is True


def test_the_full_library_still_has_five_tools_for_in_process_callers():
    import asyncio
    assert sorted(t.name for t in asyncio.run(server.mcp.list_tools())) == ALL_FIVE


def test_writes_can_be_exposed_only_by_naming_them(env, monkeypatch):
    monkeypatch.setenv("POETRY_MCP_EXPOSED_TOOLS", ",".join(ALL_FIVE))
    with TestClient(server.build_app(), raise_server_exceptions=False) as client:
        _, session = handshake(client)
        assert served_tool_names(client, session) == ALL_FIVE


@pytest.mark.parametrize("value", ["get_work_snapshot,publish", "typo_tool", ",,,"])
def test_an_unknown_tool_name_aborts_startup_instead_of_being_ignored(env, monkeypatch, value):
    monkeypatch.setenv("POETRY_MCP_EXPOSED_TOOLS", value)
    with pytest.raises(ValueError):
        server.build_app()


def test_a_tool_call_is_served_and_reports_an_unavailable_domain_api_instead_of_succeeding(env):
    with TestClient(server.build_app(), raise_server_exceptions=False) as client:
        _, session = handshake(client)
        call = rpc(client, "tools/call", {"name": "get_work_snapshot", "arguments": {
            "work_id": "work-chun-wang",
            "request": {"run_id": "run_" + "a" * 32, "mandate_id": "mandate_" + "b" * 32,
                        "actor_role": "CONTENT_EDITOR", "idempotency_key": "test-key-0001"}}}, ident=3, session=session)
        assert call.status_code == 200, call.text[:200]
        assert "DOMAIN_API_UNAVAILABLE" in json.dumps(payload(call), ensure_ascii=False)


@pytest.mark.parametrize("authorization", [None, "Bearer wrong-token", "Bearer ", "Basic abc", MCP_TOKEN])
def test_everything_but_the_exact_bearer_token_is_still_refused(env, authorization):
    headers = {k: v for k, v in HEADERS.items() if k != "Authorization"}
    if authorization is not None:
        headers["Authorization"] = authorization
    with TestClient(server.build_app(), raise_server_exceptions=False) as client:
        assert client.post("/mcp", headers=headers, content="{}").status_code == 401


def test_the_control_bridge_still_works_alongside_the_mounted_mcp_app(env):
    with TestClient(server.build_app(), raise_server_exceptions=False) as client:
        assert client.get("/internal/works").status_code == 401  # the bridge is up and authenticating
