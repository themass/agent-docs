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


def test_tool_allowlist_blocks_host_tools_and_subagents() -> None:
    from types import SimpleNamespace

    from jc.agent.tool_catalog import SKILL_TOOLS

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
        client._available_skills = {"coach-mock"}
        tools = client._get_tools(subagent_enabled=True)
    assert {tool.name for tool in tools} == {permitted, "write_todos"}
    assert seen["subagent_enabled"] is False


def test_map_raw_event_write_todos_carries_todos_in_args() -> None:
    """``write_todos`` tool calls must keep their ``todos`` arg so the frontend's
    generic ``tool_start`` -> ``plan`` mapping (turn-model.ts: ``item.name ===
    "write_todos"`` -> extract ``args.todos``) can render the plan UI without any
    dedicated backend event type.
    """
    from types import SimpleNamespace

    from jc.adapters.deerflow_harness_client import _map_raw_event

    todos = [
        {"content": "Read profile", "status": "pending", "id": "1"},
        {"content": "Draft resume section", "status": "pending", "id": "2"},
    ]
    event = SimpleNamespace(
        type="messages-tuple",
        data={
            "type": "ai",
            "content": "",
            "tool_calls": [{"id": "call_1", "name": "write_todos", "args": {"todos": todos}}],
        },
    )
    out = _map_raw_event(event, seen_tool_ids=set())
    tool_start_events = [e for e in out if e["type"] == "tool_start"]
    assert len(tool_start_events) == 1
    assert tool_start_events[0]["name"] == "write_todos"
    assert tool_start_events[0]["args"] == {"todos": todos}


def test_map_raw_event_emits_thinking_before_token() -> None:
    """Reasoning content from the model (``reasoning_content`` or ``thinking``)
    must surface as a dedicated ``thinking`` event ahead of the ``token`` event
    for the same AI message chunk, so the UI can render it as a collapsible
    block above the streamed answer.
    """
    from types import SimpleNamespace

    from jc.adapters.deerflow_harness_client import _map_raw_event

    event = SimpleNamespace(
        type="messages-tuple",
        data={
            "type": "ai",
            "reasoning_content": "Comparing 9.11 and 9.9 digit by digit...",
            "content": "9.9",
            "tool_calls": [],
        },
    )
    out = _map_raw_event(event, seen_tool_ids=set())
    # `full_content` carries the same text, untruncated, for `jc_agent_trace`
    # (see that event's docstring in `_map_raw_event`) -- UI-facing `content`
    # stays the short/possibly-cut field this test is really about.
    assert out[0] == {
        "type": "thinking",
        "content": "Comparing 9.11 and 9.9 digit by digit...",
        "full_content": "Comparing 9.11 and 9.9 digit by digit...",
    }
    assert out[1] == {"type": "token", "content": "9.9"}


def test_strip_dead_prompt_sections_removes_citations_and_working_directory() -> None:
    """JC binds no `web_search`, `read_file`, `write_file`, `bash`, or
    `present_files` tool (`_jc_deerflow_client_class._get_tools` filters every
    model-facing tool down to the per-skill allowlist), so the generic
    lead-agent template's `<citations>` (web_search citation formatting) and
    `<working_directory>` (`/mnt/user-data/...` file contract) sections are
    instructions about tools the model never has. They must not reach the
    model, and must not reach `jc_agent_trace` either.
    """
    from jc.adapters.deerflow_harness_client import _strip_dead_prompt_sections

    rendered = (
        "<role>\nYou are 舟卡.\n</role>\n\n"
        "<thinking_style>\n- think first\n</thinking_style>\n\n"
        "<working_directory existed=\"true\">\n"
        "- Current uploads: /mnt/user-data/uploads\n"
        "- Output files: /mnt/user-data/outputs\n"
        "</working_directory>\n\n"
        "<response_style>\n- Clear and concise\n</response_style>\n\n"
        "<citations>\n**CRITICAL: Always include citations**\n...\n</citations>\n\n"
        "<skill_system>\nskills live here\n</skill_system>"
    )

    cleaned = _strip_dead_prompt_sections(rendered)

    assert "<working_directory" not in cleaned
    assert "</working_directory>" not in cleaned
    assert "<citations>" not in cleaned
    assert "</citations>" not in cleaned
    # Sections for tools JC does bind must survive untouched.
    assert "<role>" in cleaned
    assert "<thinking_style>" in cleaned
    assert "<response_style>" in cleaned
    assert "<skill_system>" in cleaned
    # No triple-plus blank lines left behind where a section was cut.
    assert "\n\n\n" not in cleaned


def test_strip_dead_prompt_sections_is_a_noop_without_the_tags() -> None:
    """A future DeerFlow template revision that drops or renames these tags
    must degrade to a no-op, not raise — this function only deletes exact
    tag pairs it finds, it never asserts their presence."""
    from jc.adapters.deerflow_harness_client import _strip_dead_prompt_sections

    rendered = "<role>\nYou are 舟卡.\n</role>\n\n<skill_system>\nskills\n</skill_system>"
    assert _strip_dead_prompt_sections(rendered) == rendered


def test_stream_producer_queues_a_formatted_traceback_on_failure() -> None:
    """The worker must format the traceback while its frame is still alive.

    Handing the bare exception across the queue (the old behaviour) left the
    consumer with `str(exc)` — which for most LangGraph/litellm failures is
    short and context-free — and the traceback only in stdout. `stage` and
    `open_tools` are captured too, because they answer "did this die before
    the model, mid-tool, or on the final answer" without reading the trace.
    """
    import asyncio
    import threading

    from agentkit.adapters.deerflow.client import AgentRunMetadata

    from jc.adapters.deerflow_harness_client import _HarnessFailure, _stream_producer

    class _FailsAfterATool:
        def stream(self, message, *, thread_id, **kwargs):
            class _ToolCall:
                type = "messages-tuple"
                data = {
                    "type": "ai",
                    "content": "",
                    "tool_calls": [
                        {"id": "call_1", "name": "jc_profile_get", "args": {}}
                    ],
                }

            yield _ToolCall()
            raise RuntimeError("final answer turn exploded")

    async def _run() -> _HarnessFailure:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()
        worker = threading.Thread(
            target=_stream_producer,
            args=(_FailsAfterATool(), "帮我改简历"),
            kwargs={
                "thread_id": "thread_1",
                "stream_kwargs": {},
                "loop": loop,
                "queue": queue,
                "metadata": AgentRunMetadata(
                    trace_id="",
                    user_id="usr_1",
                    profile_id=None,
                    session_id="agsn_fail",
                    skill_hint="resume-coach",
                    extra={},
                ),
            },
            daemon=True,
        )
        worker.start()
        failure = None
        while True:
            kind, payload = await queue.get()
            if kind == "error":
                failure = payload
            if kind == "done":
                break
        assert failure is not None
        return failure

    failure = asyncio.run(_run())
    assert isinstance(failure, _HarnessFailure)
    assert failure.qualified_type == "RuntimeError"
    assert failure.message == "final answer turn exploded"
    assert "final answer turn exploded" in failure.traceback_text
    # The raise site, not just the exception line.
    assert "_FailsAfterATool" in failure.traceback_text or "stream" in failure.traceback_text
    assert failure.stage == "stream"
    # The tool had started and not returned when the run died.
    assert failure.open_tools == ("jc_profile_get",)

    payload = failure.trace_payload()
    assert payload["exception_type"] == "RuntimeError"
    assert payload["stage"] == "stream"
    assert payload["open_tools"] == ["jc_profile_get"]
    assert "Traceback" in payload["traceback"]


def test_harness_failure_keeps_the_tail_of_an_oversized_traceback() -> None:
    """MySQL TEXT has a hard limit and the raise site is at the *end* of a
    traceback, so the cut must drop the head, not the tail."""
    from jc.adapters.deerflow_harness_client import _TRACEBACK_CAP, _HarnessFailure

    failure = _HarnessFailure(
        exc=RuntimeError("x"),
        exc_type="RuntimeError",
        exc_module="builtins",
        message="x",
        traceback_text=("HEAD" * 20_000) + "THE-ACTUAL-RAISE-SITE",
        open_tools=(),
        stage="stream",
    )
    stored = failure.trace_payload()["traceback"]
    assert len(stored) == _TRACEBACK_CAP
    assert stored.endswith("THE-ACTUAL-RAISE-SITE")


def test_harness_failure_falls_back_to_the_type_when_the_message_is_empty() -> None:
    """Several litellm/LangGraph exceptions stringify to "", which is what made
    the old `str(exc)` error event useless to both the user and the operator."""
    from jc.adapters.deerflow_harness_client import _HarnessFailure

    failure = _HarnessFailure(
        exc=RuntimeError(),
        exc_type="APIError",
        exc_module="litellm.exceptions",
        message="",
        traceback_text="T",
        open_tools=(),
        stage="startup",
    )
    assert failure.qualified_type == "litellm.exceptions.APIError"
    assert failure.user_message() == "litellm.exceptions.APIError"
