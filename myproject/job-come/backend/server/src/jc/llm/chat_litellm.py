"""LangChain chat model backed by JC's scenario router and litellm.Router.

Why this exists
---------------
DeerFlow resolves ``models[].use`` through ``resolve_class(..., BaseChatModel)``,
so before this adapter the harness bound ``langchain_openai:ChatOpenAI`` and
named its own models in ``backend/agent/deerflow/config.yaml``. That produced a
second place where models are configured, and the two copies had already
diverged: ``jc-writer`` pointed at ``deepseek-v4-flash`` while the ``writer``
chain in ``routing.yaml`` led with ``gpt-6-1-sol``. Same name, different model,
depending on whether the request came from a service or from the agent.

This class removes the second copy. ``config.yaml`` now names a **scenario**,
and the chain behind it is read from ``routing.yaml`` at call time.

Failover is not reimplemented here either: the ``litellm.Router`` comes from
``jc.llm.transport``, the same one the deterministic services call through. So
there is one chain walk in the process, not one per entry point.

All four generation methods are implemented on purpose. LangChain's base class
can derive the missing ones, but each derivation loses something that matters
here: a derived ``_astream`` delivers the whole answer as a single chunk (no
token-by-token typing in the 舟卡 panel), and a derived sync method would run the
async one on a fresh event loop - while the harness streams its turn from a
worker thread, which is exactly where the sync pair is needed.

Auditing is **not** done inside these methods beyond declaring the boundary: the
observer lives in ``jc.llm.audit_hook``, so this class stays a transport.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from typing import Any

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field

logger = logging.getLogger(__name__)

#: Scenario used when ``config.yaml`` names none. ``coach`` is the agent-facing
#: chain in ``routing.yaml``; it existed but was unreachable while DeerFlow bound
#: ChatOpenAI directly, which is why it previously looked like dead config.
_DEFAULT_SCENARIO = "coach"


class ChatLiteLLMRouter(BaseChatModel):
    """Chat model whose endpoint chain comes from ``routing.yaml``.

    ``model`` is a *scenario name* (``coach`` / ``writer`` / ``flash`` ...), not a
    model slug. The slug is resolved per attempt from the routing chain.
    """

    model: str = Field(default=_DEFAULT_SCENARIO)
    temperature: float | None = None
    max_tokens: int | None = None
    #: Accepted and ignored: DeerFlow passes these from ``config.yaml`` for UI and
    #: summarization math. Declared so pydantic does not reject them.
    context_window: int | None = None
    streaming: bool = True
    #: Reasoning/thinking passthrough. DeerFlow's model factory resolves these
    #: from ``config.yaml``'s ``reasoning:`` / ``when_thinking_enabled`` contract
    #: and passes them as constructor kwargs (see ``models/factory.py``). They
    #: are forwarded verbatim to litellm's completion payload in
    #: ``_request_kwargs`` below — litellm normalizes ``reasoning_effort`` and
    #: ``extra_body`` per-provider (OpenAI o-series, Anthropic extended
    #: thinking, etc). Without this field + passthrough, DeerFlow can compute
    #: a reasoning request but this transport silently drops it.
    reasoning_effort: str | None = None
    extra_body: dict[str, Any] | None = None

    model_config = {"extra": "allow", "populate_by_name": True}

    @property
    def _llm_type(self) -> str:
        return "jc-litellm-router"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"scenario": self.model}

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: dict[str, Any] | str | bool | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        """Bind tool schemas so the harness's agent loop can call them.

        ``BaseChatModel.bind_tools`` is deliberately ``NotImplementedError`` in
        langchain-core: every concrete chat model must say what wire format its
        provider expects. litellm's ``completion``/``acompletion`` speak the OpenAI
        function-calling schema regardless of which backend model ends up serving
        the request (that normalization is litellm's job, not ours), so this mirrors
        ``BaseChatOpenAI.bind_tools`` — convert each tool with
        ``convert_to_openai_tool`` and forward the list through ``_request_kwargs``'s
        existing ``tools`` passthrough (see above). No new wire path, just the
        missing adapter method the agent loop calls before every turn that offers
        tools.
        """
        formatted_tools = [convert_to_openai_tool(tool) for tool in tools]
        if tool_choice is not None:
            is_mode_keyword = isinstance(tool_choice, str) and tool_choice in (
                "auto",
                "none",
                "any",
                "required",
            )
            if isinstance(tool_choice, str) and not is_mode_keyword:
                tool_choice = {"type": "function", "function": {"name": tool_choice}}
            elif tool_choice is True:
                tool_choice = "required"
            kwargs["tool_choice"] = tool_choice
        return super().bind(tools=formatted_tools, **kwargs)

    def _audit_caller(self) -> str:
        """Which code path this call belongs to, for the audit row.

        Falls back to the model profile name because the harness may invoke a
        subagent whose skill is not in the ambient context.
        """
        from jc.llm.call_context import llm_context

        hint = llm_context("harness").skill_hint
        return hint or f"harness:{self.model}"

    # -- transport -------------------------------------------------------

    def _transport(self) -> Any:
        """The shared `litellm.Router` for this scenario.

        Built by `jc.llm.transport`, which the deterministic services use too -
        that shared construction is the whole point. `routing.yaml` stays the one
        place a model is named, instead of the harness carrying a second,
        silently diverging copy.
        """
        from jc.llm.transport import router_for

        return router_for(self.model)

    def _request_kwargs(
        self, messages: Sequence[BaseMessage], stop: list[str] | None, **kwargs: Any
    ) -> dict[str, Any]:
        from jc.llm.message_mapping import to_litellm_messages

        payload: dict[str, Any] = {
            "model": self._transport().primary,
            "messages": to_litellm_messages(messages),
            "drop_params": True,
            # Read back by the audit callback, which otherwise cannot tell which
            # scenario or code path a raw litellm call belongs to.
            "metadata": {
                "scenario": self.model,
                "caller": self._audit_caller(),
                "channel": "harness",
                "trace_id": _current_trace_id(),
            },
        }
        if stop:
            payload["stop"] = stop
        max_tokens = kwargs.pop("max_tokens", None) or self.max_tokens
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        for passthrough in ("tools", "tool_choice", "response_format"):
            if passthrough in kwargs and kwargs[passthrough] is not None:
                payload[passthrough] = kwargs.pop(passthrough)
        # Reasoning/thinking: prefer a per-call override (kwargs, e.g. from
        # DeerFlow's when_thinking_enabled template) over the instance default
        # set from config.yaml at model construction time.
        reasoning_effort = kwargs.pop("reasoning_effort", None) or self.reasoning_effort
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
        extra_body = kwargs.pop("extra_body", None) or self.extra_body
        if extra_body:
            payload["extra_body"] = extra_body
        return payload

    # -- generation ------------------------------------------------------

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        import time

        from jc.llm import audit_hook

        transport = self._transport()
        payload = self._request_kwargs(messages, stop, **kwargs)
        caller = self._audit_caller()
        async with audit_hook.llm_call_scope(self.model, caller, "harness"):
            audit_hook.report_skipped(transport.skipped)
            audit_hook.report_prompt(payload["messages"], trace_id=_current_trace_id())
            started = time.monotonic()
            response = await transport.router.acompletion(**payload)
            audit_hook.report_success(
                response, latency_ms=int((time.monotonic() - started) * 1000)
            )
        return _to_chat_result(response)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        import time

        from jc.llm import audit_hook

        transport = self._transport()
        payload = self._request_kwargs(messages, stop, **kwargs)
        caller = self._audit_caller()
        # The synchronous scope, because the harness streams its turn from a
        # worker thread where there is no running loop to await a flush on.
        with audit_hook.sync_call_scope(self.model, caller, "harness"):
            audit_hook.report_skipped(transport.skipped)
            audit_hook.report_prompt(payload["messages"], trace_id=_current_trace_id())
            started = time.monotonic()
            response = transport.router.completion(**payload)
            audit_hook.report_success(
                response, latency_ms=int((time.monotonic() - started) * 1000)
            )
        return _to_chat_result(response)

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        from jc.llm import audit_hook

        transport = self._transport()
        payload = self._request_kwargs(messages, stop, **kwargs)
        payload["stream"] = True
        caller = self._audit_caller()
        # The scope closes when the stream *opens*, not when it drains: the
        # consumer owns the iterator, so there is no point here at which the
        # final text is known.
        async with audit_hook.llm_call_scope(
            self.model, caller, "harness", stream=True
        ):
            audit_hook.report_skipped(transport.skipped)
            audit_hook.report_prompt(payload["messages"], trace_id=_current_trace_id())
            stream = await transport.router.acompletion(**payload)
            audit_hook.report_stream_opened(stream)
        async for chunk in stream:
            piece = _chunk_to_generation(chunk)
            if piece is None:
                continue
            if run_manager is not None:
                await run_manager.on_llm_new_token(piece.text, chunk=piece)
            yield piece

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        from jc.llm import audit_hook

        transport = self._transport()
        payload = self._request_kwargs(messages, stop, **kwargs)
        payload["stream"] = True
        caller = self._audit_caller()
        with audit_hook.sync_call_scope(self.model, caller, "harness", stream=True):
            audit_hook.report_skipped(transport.skipped)
            audit_hook.report_prompt(payload["messages"], trace_id=_current_trace_id())
            stream = transport.router.completion(**payload)
            audit_hook.report_stream_opened(stream)
        for chunk in stream:
            piece = _chunk_to_generation(chunk)
            if piece is None:
                continue
            if run_manager is not None:
                run_manager.on_llm_new_token(piece.text, chunk=piece)
            yield piece


def _current_trace_id() -> str | None:
    try:
        from agentkit.common.trace import get_trace_id

        return get_trace_id()
    except Exception:  # noqa: BLE001
        return None


def _to_chat_result(response: Any) -> ChatResult:
    from jc.llm.message_mapping import content_text, tool_calls_from

    choices = getattr(response, "choices", None) or []
    if not choices:
        # HTTP 200 with no choices. Returning an empty message would look like
        # the model chose to say nothing; raising lets the fallback chain and the
        # audit log both see this as the failure it is.
        raise ValueError("LLM response contained no choices")
    message = getattr(choices[0], "message", None)
    text = content_text(getattr(message, "content", None))
    additional: dict[str, Any] = {}
    tool_calls = tool_calls_from(message)
    if tool_calls:
        additional["tool_calls"] = tool_calls
    reasoning = getattr(message, "reasoning_content", None) or getattr(
        message, "reasoning", None
    )
    if isinstance(reasoning, str) and reasoning:
        additional["reasoning_content"] = reasoning

    usage = getattr(response, "usage", None)
    response_metadata: dict[str, Any] = {
        # The model that actually served the request, which under failover is not
        # the first one in the chain. Surfaced here so callers and the audit
        # callback agree on what ran.
        "model_name": getattr(response, "model", None),
        "finish_reason": getattr(choices[0], "finish_reason", None),
    }
    ai = AIMessage(
        content=text,
        additional_kwargs=additional,
        response_metadata=response_metadata,
        usage_metadata=_usage_metadata(usage),
    )
    return ChatResult(generations=[ChatGeneration(message=ai)])


def _usage_metadata(usage: Any) -> dict[str, int] | None:
    if usage is None:
        return None
    prompt = getattr(usage, "prompt_tokens", None)
    completion = getattr(usage, "completion_tokens", None)
    total = getattr(usage, "total_tokens", None)
    if prompt is None and completion is None and total is None:
        return None
    return {
        "input_tokens": int(prompt or 0),
        "output_tokens": int(completion or 0),
        "total_tokens": int(total or (prompt or 0) + (completion or 0)),
    }


def _chunk_to_generation(chunk: Any) -> ChatGenerationChunk | None:
    from jc.llm.message_mapping import content_text

    choices = getattr(chunk, "choices", None) or []
    if not choices:
        return None
    delta = getattr(choices[0], "delta", None)
    if delta is None:
        return None
    text = content_text(getattr(delta, "content", None))
    raw_tool_calls = getattr(delta, "tool_calls", None)
    if not text and not raw_tool_calls:
        return None
    additional: dict[str, Any] = {}
    if raw_tool_calls:
        additional["tool_calls"] = [
            _tool_call_chunk(entry) for entry in raw_tool_calls
        ]
    return ChatGenerationChunk(
        message=AIMessageChunk(content=text, additional_kwargs=additional)
    )


def _tool_call_chunk(entry: Any) -> dict[str, Any]:
    function = getattr(entry, "function", None)
    return {
        "index": getattr(entry, "index", 0),
        "id": getattr(entry, "id", None),
        "type": "function",
        "function": {
            "name": getattr(function, "name", None),
            "arguments": getattr(function, "arguments", None) or "",
        },
    }
