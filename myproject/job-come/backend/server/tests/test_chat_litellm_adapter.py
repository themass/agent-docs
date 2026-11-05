"""The agent's chat model: one chain for the harness and the services alike.

Why these tests look the way they do
------------------------------------
DeerFlow streams a turn from a ``threading.Thread`` through a *synchronous*
generator, so the methods that matter in production are ``_generate`` and
``_stream`` - not the async pair a LangChain adapter is usually exercised
through. Each is therefore driven on a worker thread here, because that is where
the ContextVars, the audit sink, and the validation rule all have to still work.

The gateway is faked at litellm's own boundary (see ``tests/conftest.py``) so the
real ``litellm.Router`` resolves the chain. A stubbed router would make the
failover order and the audit row the test's own invention.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from conftest import capture_audit_rows, fake_gateway, gateway_error, install_routing
from jc.llm.chat_litellm import ChatLiteLLMRouter

_SCENARIO = "coach"


def run_on_worker_thread(work: Any, sink: Any = None) -> Any:
    """Run `work` the way the harness does: on a plain thread, no event loop.

    A derived synchronous method would spin up its own loop here, which is why
    the adapter implements all four generation methods instead of letting
    LangChain fill two of them in.

    The audit sink is bound *inside* the thread, exactly as
    `deerflow_harness_client._audit_context` does it. A `threading.Thread` does
    not inherit the caller's ContextVars, so a sink bound outside would be
    invisible here - and the rows would be silently dropped, which is the
    failure mode this mirrors.
    """
    outcome: dict[str, Any] = {}

    def target() -> None:
        from jc.llm import audit_hook

        try:
            if sink is None:
                outcome["value"] = work()
            else:
                with audit_hook.audit_sink(sink):
                    outcome["value"] = work()
        except BaseException as exc:  # noqa: BLE001 - re-raised on the caller
            outcome["error"] = exc

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout=30)
    assert not thread.is_alive(), "harness call did not finish"
    if "error" in outcome:
        raise outcome["error"]
    return outcome["value"]


@pytest.fixture
def coach_chain(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    return install_routing(
        monkeypatch, tmp_path, _SCENARIO, ["openai/first", "openai/second"]
    )


def test_the_model_name_is_a_scenario_not_a_slug(coach_chain) -> None:
    """`config.yaml` names a scenario; the slug comes from `routing.yaml`.

    This is the whole reason the adapter exists. While the harness bound
    ChatOpenAI directly, the agent named its own models, and the two lists had
    already drifted - the same profile meant a different model depending on
    whether the request came from a service or from the agent.
    """
    model = ChatLiteLLMRouter(model=_SCENARIO)
    payload = model._request_kwargs([HumanMessage(content="hi")], None)

    # The alias addresses the chain, so the served slug is chosen per attempt.
    assert payload["model"] == f"{_SCENARIO}-0"
    assert payload["metadata"]["scenario"] == _SCENARIO
    assert payload["metadata"]["channel"] == "harness"


def test_a_harness_turn_fails_over_and_is_audited_once(coach_chain) -> None:
    """The sync path is the real one, and it must produce exactly one row."""
    model = ChatLiteLLMRouter(model=_SCENARIO)

    with capture_audit_rows() as rows:
        with fake_gateway({"first": gateway_error("server"), "second": "答案"}):
            result = run_on_worker_thread(
                lambda: model._generate([HumanMessage(content="你好")]), rows.append
            )

    assert result.generations[0].message.content == "答案"
    assert len(rows) == 1
    record = rows[0]
    assert record.channel == "harness"
    assert record.scenario == _SCENARIO
    assert record.status == "success"
    # Not the configured head of the chain.
    assert record.final_model == "second"
    assert [a.status for a in record.attempts] == ["failed", "success"]


def test_a_streamed_turn_is_audited_when_the_stream_opens(coach_chain) -> None:
    """The consumer owns the iterator, so the row cannot wait for the last token.

    The absence of token counts on a streamed row is deliberate, and is what
    separates it from a unary one in a cost report.
    """
    model = ChatLiteLLMRouter(model=_SCENARIO)

    def drain() -> list[str]:
        with fake_gateway({"first": "一字一句"}):
            return [chunk.text for chunk in model._stream([HumanMessage(content="hi")])]

    with capture_audit_rows() as rows:
        pieces = run_on_worker_thread(drain, rows.append)

    assert "".join(pieces) == "一字一句"
    assert len(rows) == 1
    assert rows[0].stream is True
    assert rows[0].status == "success"
    assert rows[0].attempts[-1].total_tokens is None


@pytest.mark.asyncio
async def test_an_async_stream_writes_its_own_audit_row(coach_chain) -> None:
    """Both stream methods exist because they flush the audit row differently.

    Without an explicit `_astream`, LangChain derives one by running the
    *synchronous* path in a worker thread. The answer still streams, so the
    difference is invisible to the user - but the row is then produced on a
    thread with no event loop, so it leaves through the harness sink instead of
    being written to the database. In an async caller, which installs no sink,
    that means the row is dropped and the agent's model usage simply stops
    appearing in the audit table.
    """
    model = ChatLiteLLMRouter(model=_SCENARIO)
    dropped_to_sink: list[Any] = []

    with capture_audit_rows() as rows:
        del rows[:]
        with fake_gateway({"first": "逐字输出"}):
            from jc.llm import audit_hook

            with audit_hook.audit_sink(dropped_to_sink.append):
                chunks = [
                    chunk.text
                    async for chunk in model.astream([HumanMessage(content="hi")])
                ]

    assert "".join(chunks) == "逐字输出"
    # Written through the async flush, not handed to the thread sink.
    assert [(r.channel, r.stream) for r in rows] == [("harness", True)]
    assert dropped_to_sink == []


@pytest.mark.asyncio
async def test_a_two_hundred_with_no_choices_is_treated_as_a_failure(
    coach_chain,
) -> None:
    """Returning an empty message would look like the model chose to say nothing."""
    # A dict mock_response is returned verbatim, so this is a 200 with no choices.
    with fake_gateway({"first": {"choices": []}}):
        with pytest.raises(ValueError, match="no choices"):
            await ChatLiteLLMRouter(model=_SCENARIO)._agenerate(
                [HumanMessage(content="hi")]
            )


def test_bind_tools_produces_openai_schema_the_agent_loop_can_call() -> None:
    """``BaseChatModel.bind_tools`` is ``NotImplementedError`` by design; every
    concrete adapter must say what wire format its provider expects.

    This regression guards the real V1 failure: every harness turn raised
    ``NotImplementedError`` at ``bind_tools`` because the override was missing
    entirely, so the agent could never offer a tool. litellm's completion API
    speaks OpenAI's function-calling schema regardless of which model ends up
    serving the request, so the bound tool list must come out in that shape and
    flow into ``_request_kwargs``'s existing ``tools`` passthrough unchanged.
    """
    model = ChatLiteLLMRouter(model=_SCENARIO)
    bound = model.bind_tools(
        [
            {
                "name": "jc_profile_get",
                "description": "Fetch the active profile.",
                "parameters": {"type": "object", "properties": {}},
            }
        ]
    )

    tools = bound.kwargs["tools"]
    assert tools == [
        {
            "type": "function",
            "function": {
                "name": "jc_profile_get",
                "description": "Fetch the active profile.",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]

    # The bound tools must reach litellm through the same passthrough other
    # kwargs use - no second wire path for tool-calling turns.
    payload = model._request_kwargs(
        [HumanMessage(content="hi")], None, tools=tools
    )
    assert payload["tools"] == tools


def test_bind_tools_rejects_a_tool_choice_name_as_a_forced_function_call() -> None:
    """A bare string ``tool_choice`` names a required tool, not a litellm mode."""
    model = ChatLiteLLMRouter(model=_SCENARIO)
    bound = model.bind_tools(
        [
            {
                "name": "jc_profile_get",
                "description": "Fetch the active profile.",
                "parameters": {"type": "object", "properties": {}},
            }
        ],
        tool_choice="jc_profile_get",
    )
    assert bound.kwargs["tool_choice"] == {
        "type": "function",
        "function": {"name": "jc_profile_get"},
    }


def test_tool_results_and_calls_survive_the_round_trip() -> None:
    """A dropped tool_call_id is rejected by most gateways, and silently so here."""
    from jc.llm.message_mapping import to_litellm_messages

    calls = [{"id": "c1", "type": "function",
              "function": {"name": "jc_profile_get", "arguments": "{}"}}]
    messages = to_litellm_messages([
        SystemMessage(content="be useful"),
        HumanMessage(content="改我的简历"),
        AIMessage(content="", additional_kwargs={"tool_calls": calls}),
        ToolMessage(content="{}", tool_call_id="c1"),
    ])

    assert [m["role"] for m in messages] == ["system", "user", "assistant", "tool"]
    # An assistant turn that only calls a tool has no text; "" is rejected by
    # some gateways where null is accepted.
    assert messages[2]["content"] is None
    assert messages[2]["tool_calls"] == calls
    assert messages[3]["tool_call_id"] == "c1"


def test_image_blocks_do_not_leak_into_assistant_text() -> None:
    """Base64 in the text stream is noise in a log and in a prompt alike."""
    from jc.llm.message_mapping import content_text

    blocks = [
        {"type": "text", "text": "看这张"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
    ]
    assert content_text(blocks) == "看这张"
    assert "AAAA" not in content_text(blocks)
