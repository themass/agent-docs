"""DeerFlow harness adapter — JC non-interactive defaults."""

from __future__ import annotations

from unittest.mock import patch

from langchain_core.runnables import RunnableConfig

from jc.adapters.deerflow_harness_client import _jc_deerflow_client_class


def test_jc_client_sets_non_interactive() -> None:
    class FakeDeerFlowClient:
        def _get_runnable_config(self, thread_id: str, **overrides):  # noqa: ANN001
            return RunnableConfig(configurable={"thread_id": thread_id})

    import deerflow.client

    with patch.object(deerflow.client, "DeerFlowClient", FakeDeerFlowClient):
        client_cls = _jc_deerflow_client_class()
        client = client_cls.__new__(client_cls)
        runnable = client._get_runnable_config("thr_test")
        assert runnable["configurable"]["non_interactive"] is True


def test_mcp_environment_replaces_previous_identity(monkeypatch) -> None:
    import os
    from types import SimpleNamespace

    from jc.adapters.deerflow_harness_client import _apply_mcp_env

    names = [
        "JC_MCP_USER_ID", "JC_MCP_PROFILE_ID", "JC_MCP_SESSION_ID",
        "JC_AGENT_SKILL", "JC_MCP_JOB_ID", "JC_MCP_MOCK_SESSION_ID",
        "JC_AGENT_REPLY_LOCALE",
    ]
    for name in names:
        monkeypatch.setenv(name, "previous-tenant")
    _apply_mcp_env(SimpleNamespace(
        user_id="user-new", profile_id="profile-new", session_id="session-new",
        skill_hint="coach-mock", extra={},
    ))
    assert os.environ["JC_MCP_USER_ID"] == "user-new"
    assert os.environ["JC_MCP_PROFILE_ID"] == "profile-new"
    assert os.environ["JC_MCP_SESSION_ID"] == "session-new"
    assert os.environ["JC_AGENT_SKILL"] == "coach-mock"
    for name in names[4:]:
        assert name not in os.environ


def test_tool_allowlist_blocks_host_tools_and_subagents() -> None:
    from types import SimpleNamespace

    from jc.mcp.registry import SKILL_TOOLS

    seen = {}
    permitted = SKILL_TOOLS["coach-mock"][0]
    class FakeDeerFlowClient:
        def _get_tools(self, **kwargs):
            seen.update(kwargs)
            return [SimpleNamespace(name=n) for n in [
                permitted, "bash", "read_file", "web_search", "write_todos",
                "jc_unregistered_tool",
            ]]

    import deerflow.client

    with patch.object(deerflow.client, "DeerFlowClient", FakeDeerFlowClient):
        client_cls = _jc_deerflow_client_class()
        client = client_cls.__new__(client_cls)
        client._jc_skill = "coach-mock"
        tools = client._get_tools(subagent_enabled=True)
    assert {tool.name for tool in tools} == {permitted, "write_todos"}
    assert seen["subagent_enabled"] is False
