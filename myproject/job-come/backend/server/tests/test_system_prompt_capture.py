"""The run's system prompt reaches `jc_agent_trace` from JC-owned middleware.

Why this file exists: the adapter used to read the prompt off the DeerFlow
client as `getattr(client, "rendered_system_prompt", None)`. The vendored
upstream defines no such attribute, so that call returned `None` on every run
for the entire life of the feature — `system_prompt_rendered` never fired and
every session's ledger started at `user_message` instead of seq 0
`system_prompt`. Nothing failed loudly, which is exactly why it survived.

These tests pin the two halves of the replacement:
  * `JCProductRulesMiddleware.wrap_model_call` records `request.system_message`
    (the text after the whole middleware chain, i.e. what the model actually
    receives) under this run's `jc_session_id`.
  * `_stream_producer` reads it from the registry and emits it as the synthetic
    `system_prompt_rendered` event, retrying across events because the prompt
    does not exist until the first model call inside the generator.
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any

import pytest
from langchain_core.messages import SystemMessage

from jc.adapters.deerflow_harness_client import _stream_producer
from jc.agent import system_prompt_capture
from jc.deerflow_middleware import JCProductRulesMiddleware


@pytest.fixture(autouse=True)
def _clean_registry():
    yield
    system_prompt_capture.discard("agsn_capture")


class _Runtime:
    def __init__(self, session_id: str | None) -> None:
        self.context = {
            "authz_attributes": {"jc_session_id": session_id} if session_id else {}
        }


class _Request:
    def __init__(self, content: Any, session_id: str | None = "agsn_capture") -> None:
        self.system_message = SystemMessage(content=content) if content is not None else None
        self.runtime = _Runtime(session_id)


def test_middleware_records_the_system_message_for_this_session() -> None:
    mw = JCProductRulesMiddleware()
    mw.wrap_model_call(_Request("你是舟卡。"), lambda req: "response")
    assert system_prompt_capture.take("agsn_capture") == "你是舟卡。"


def test_middleware_keeps_the_first_capture_across_tool_round_trips() -> None:
    """One run makes several model calls; they all carry the same prompt, and
    seq 0 must stay the prompt the run *started* with."""
    mw = JCProductRulesMiddleware()
    mw.wrap_model_call(_Request("第一次渲染"), lambda req: None)
    mw.wrap_model_call(_Request("工具返回后的第二次调用"), lambda req: None)
    assert system_prompt_capture.take("agsn_capture") == "第一次渲染"


def test_middleware_flattens_multi_part_text_content() -> None:
    mw = JCProductRulesMiddleware()
    mw.wrap_model_call(
        _Request(
            [
                {"type": "text", "text": "产品规则"},
                {"type": "cache_control", "value": "ignored"},
                {"type": "text", "text": "会话上下文"},
            ]
        ),
        lambda req: None,
    )
    assert system_prompt_capture.take("agsn_capture") == "产品规则\n会话上下文"


def test_a_run_without_a_session_id_is_not_recorded_under_a_blank_key() -> None:
    """Identity comes from this run's `authz_attributes`; without one there is
    no safe key to file the prompt under, and guessing would let one session's
    prompt be written into another's trace."""
    mw = JCProductRulesMiddleware()
    mw.wrap_model_call(_Request("无会话", session_id=None), lambda req: None)
    assert system_prompt_capture.take(None) is None
    assert system_prompt_capture.take("") is None


def test_capture_failure_does_not_break_the_model_call() -> None:
    """This is observability on the hot path of every model call."""
    mw = JCProductRulesMiddleware()

    class _Exploding:
        @property
        def system_message(self) -> Any:
            raise RuntimeError("boom")

        runtime = _Runtime("agsn_capture")

    assert mw.wrap_model_call(_Exploding(), lambda req: "still-ran") == "still-ran"


@pytest.mark.asyncio
async def test_middleware_is_per_session_under_concurrency() -> None:
    """Two users' turns running at once must not swap prompts.

    The registry is keyed by the session id taken from each call's own
    `runtime.context`, which is the per-run LangGraph context — not process
    state — so this holds by construction. The test pins it because the
    process-global alternative is what ADR-004 was written about.
    """
    mw = JCProductRulesMiddleware()
    barrier = threading.Barrier(2)

    def _call(session_id: str, prompt: str) -> None:
        req = _Request(prompt, session_id=session_id)
        barrier.wait(timeout=5)
        mw.wrap_model_call(req, lambda r: None)

    a = threading.Thread(target=_call, args=("agsn_a", "A 的提示"))
    b = threading.Thread(target=_call, args=("agsn_b", "B 的提示"))
    a.start()
    b.start()
    a.join(timeout=5)
    b.join(timeout=5)

    assert system_prompt_capture.take("agsn_a") == "A 的提示"
    assert system_prompt_capture.take("agsn_b") == "B 的提示"


class _ScriptedClient:
    """A `client.stream(...)` that renders its prompt on the first item pulled.

    Mirrors the real timing: `DeerFlowClient.stream` is a generator, so no
    model call (and therefore no prompt capture) has happened until the
    consumer pulls. A capture read taken once, right after the first event,
    can therefore miss it.
    """

    def __init__(self, *, capture_on_event: int, session_id: str) -> None:
        self._capture_on_event = capture_on_event
        self._session_id = session_id

    def stream(self, message: str, *, thread_id: str, **kwargs: Any):
        class _End:
            type = "end"
            data: dict[str, Any] = {}

        class _Noop:
            type = "messages-tuple"
            data: dict[str, Any] = {"type": "ai", "content": ""}

        for index in range(3):
            if index == self._capture_on_event:
                system_prompt_capture.record(self._session_id, "渲染后的系统提示")
            yield _Noop()
        yield _End()


async def _drain(client: Any, session_id: str) -> list[dict[str, Any]]:
    from agentkit.adapters.deerflow.client import AgentRunMetadata

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
    metadata = AgentRunMetadata(
        trace_id="",
        user_id="usr_1",
        profile_id=None,
        session_id=session_id,
        skill_hint="resume-coach",
        extra={},
    )
    worker = threading.Thread(
        target=_stream_producer,
        args=(client, "帮我改简历"),
        kwargs={
            "thread_id": "thread_1",
            "stream_kwargs": {},
            "loop": loop,
            "queue": queue,
            "metadata": metadata,
        },
        daemon=True,
    )
    worker.start()
    events: list[dict[str, Any]] = []
    while True:
        kind, payload = await queue.get()
        if kind == "done":
            break
        if kind == "event":
            events.append(payload)
    return events


@pytest.mark.asyncio
async def test_producer_emits_the_prompt_even_when_it_lands_after_the_first_event() -> None:
    events = await _drain(
        _ScriptedClient(capture_on_event=2, session_id="agsn_late"), "agsn_late"
    )
    prompts = [e for e in events if e.get("type") == "system_prompt_rendered"]
    assert len(prompts) == 1
    assert prompts[0]["content"] == "渲染后的系统提示"
    system_prompt_capture.discard("agsn_late")


@pytest.mark.asyncio
async def test_producer_emits_the_prompt_at_most_once_per_run() -> None:
    events = await _drain(
        _ScriptedClient(capture_on_event=0, session_id="agsn_once"), "agsn_once"
    )
    assert len([e for e in events if e.get("type") == "system_prompt_rendered"]) == 1
    system_prompt_capture.discard("agsn_once")


@pytest.mark.asyncio
async def test_a_run_that_never_captures_leaves_nothing_behind_for_the_next_run() -> None:
    """A crashed or prompt-less run must not hand its registry entry to the
    session's next run, which would file it as that run's seq 0."""
    system_prompt_capture.record("agsn_stale", "上一轮残留的提示")

    class _Empty:
        def stream(self, message: str, *, thread_id: str, **kwargs: Any):
            raise RuntimeError("died before the first event")

    events = await _drain(_Empty(), "agsn_stale")
    assert all(e.get("type") != "system_prompt_rendered" for e in events)
    assert system_prompt_capture.take("agsn_stale") is None
