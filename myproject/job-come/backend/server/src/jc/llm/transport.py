"""One transport for every JC model call: `litellm.Router` built from `routing.yaml`.

Why this module exists
----------------------
JC had two ways to reach a model. The deterministic services went through
``LLMRouter``'s hand-written ``for endpoint in chain`` loop; the agent went
through DeerFlow, which named its own models in ``deerflow/config.yaml``. Two
loops, two model lists, and they had already drifted: ``jc-writer`` pointed at
deepseek-v4-flash while the ``writer`` chain led with gpt-6-1-sol.

This module is the single seam both paths now share. It owns exactly three
things, and deliberately nothing else:

1. **Building the router.** One ``litellm.Router`` per scenario, cached, with
   the chain from ``routing.yaml`` expressed as litellm ``fallbacks``.
2. **Validation as a failover trigger.** JC's notion of failure is wider than
   HTTP's: a 200 carrying unparseable JSON is a failure here and a success to
   litellm. See `validation_rule`.
3. **The audit boundary.** A chain that fails over fires several litellm
   events; the audit table wants one row. See `jc.llm.audit_hook`.

Failover order, not load balancing
----------------------------------
Each endpoint gets its own ``model_name`` (``{scenario}-{index}``). Sharing one
``model_name`` across the chain would make litellm *load balance* between them,
which is the opposite of a failover chain - the second model is a fallback, not
a peer.

The fallback map is one entry per position::

    [{"s-0": ["s-1", "s-2"]}, {"s-1": ["s-2"]}]

not a single flat ``{s-0: [s-1, s-2]}``. A flat map looks like it should let
litellm walk the whole chain, but litellm's fallback lookup keys strictly on
whichever model just failed (``get_fallback_model_group`` matches the current
``model_group``, not the original one). With only an ``s-0`` key, the chain
survives exactly one hop: if ``s-1`` also fails, litellm finds no ``s-1`` key
and raises - ``s-2`` is configured but unreachable. Confirmed against the real
exception message ("No fallback model group found for original model_group=
s-1"), not inferred from the litellm docs. The explicit per-position map's one
regression test asserts that all configured endpoints are attempted once when
all fail, preventing both unreachable fallbacks and duplicate audit attempts.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, NamedTuple

logger = logging.getLogger(__name__)

#: Marker in the message of the error raised when our own validation rejects a
#: 200 response. `error_code_for` turns it into a distinct audit reason code, so
#: "the model answered badly" never looks like "the gateway was down".
VALIDATION_ERROR_MARKER = "jc_invalid_response"


class NoUsableEndpoint(RuntimeError):
    """No endpoint in the scenario's chain has its API key configured."""


#: Models whose gateway endpoint rejects any *explicit* temperature except the
#: default (1) — and does it asymmetrically, which is what makes the table worth
#: keeping instead of trusting `drop_params`:
#:
#:   non-streaming + temperature!=1  ->  HTTP 500 "Only the default (1) value"
#:   STREAMING + any temperature!=1  ->  HTTP 200 and ZERO data chunks
#:
#: The streaming shape is the P0: an empty-but-successful stream reaches
#: langchain as "No generations found in stream", the agent's retry loop hits
#: the same poisoned endpoint three times, and the user sees a turn that opens
#: with 200 and never says anything. Measured against the gateway on 2026-11-18:
#: gpt-6-luna locks; glm-5.3-flash, gpt-6-sol, gpt-6-astra, gpt-6.1-sol and
#: deepseek-v4-pro all accept 0.1. Re-probe before adding or removing entries:
#: `curl "$JC_LLM_API_BASE/chat/completions"` with temperature 0.1,
#: stream:true, and count the `data:` chunks.
_TEMPERATURE_LOCKED_MODELS = frozenset({"gpt-6-luna"})


def is_temperature_locked(model: str) -> bool:
    """True when the gateway serves this model with temperature fixed at 1.

    Matched on the bare slug so `openai/gpt-6-luna` (the `.env` spelling) and a
    bare `gpt-6-luna` (what a gateway echoes back) behave the same.
    """
    return model.rsplit("/", 1)[-1] in _TEMPERATURE_LOCKED_MODELS


#: The same gateway family hides a second trap behind the first, and this one
#: sits exactly on the agent path: tools and an *active* reasoning mode are
#: mutually exclusive, and the streaming failure has the same silent shape —
#: HTTP 200 with zero SSE events. Measured against the live gateway on
#: 2026-11-18 (`gpt-6-luna`, stream:true, a one-line user message):
#:
#:   tools, reasoning left at gateway default  ->  200, 0 events
#:   tools + reasoning_effort=low              ->  200, 0 events
#:   tools + extra_body enable_thinking=false  ->  200, 0 events (flag ignored)
#:   tools + thinking: {type: disabled}        ->  200, 0 events (flag ignored)
#:   tools + reasoning_effort=none             ->  200, finish_reason=tool_calls
#:
#: The non-streaming twin says why: HTTP 500 "Function tools with
#: reasoning_effort are not supported for gpt-6-luna in /v1/chat/completions"
#: — the gateway counts its own default as an active reasoning mode, so the
#: request is rejected before any event is emitted. Only the top-level
#: `reasoning_effort: none` unlocks it; the `thinking` body flags other models
#: on this gateway accept do nothing here. glm-5.3-flash, gpt-6-sol and
#: deepseek-v4-pro stream tool calls with reasoning untouched. Re-probe before
#: adding or removing entries: post tools with stream:true and count the
#: `data:` lines.
_TOOLS_REQUIRE_REASONING_OFF = frozenset({"gpt-6-luna"})


def tools_require_reasoning_off(model: str) -> bool:
    """True when the gateway refuses `tools` unless reasoning is explicitly off.

    Bare-slug matching, same as `is_temperature_locked`.
    """
    return model.rsplit("/", 1)[-1] in _TOOLS_REQUIRE_REASONING_OFF


@dataclass(frozen=True, slots=True)
class SkippedEndpoint:
    """An endpoint left out of the router because its API key is not set.

    Reported to the audit row rather than only logged. A chain whose head is
    unconfigured answers from its second model, which looks indistinguishable
    from a healthy primary in the audit table - so the one deployment mistake
    that silently doubles cost would be the one thing the log cannot show.
    """

    model: str
    provider: str | None
    api_key_env: str


class ScenarioTransport(NamedTuple):
    """Everything a caller needs to issue one scenario call."""

    router: Any
    primary: str
    skipped: tuple[SkippedEndpoint, ...]
    # Keep the resolved config separate from Router's mutable runtime model list.
    deployments: tuple[dict[str, Any], ...] = ()
    #: True when ANY endpoint in this chain rejects explicit temperature. Call
    #: sites must then omit `temperature` from the request itself: litellm merges
    #: call-level params over the deployment's, so a caller's 0.2 would ride the
    #: fallback hop and re-poison the locked model there. The cost is only that
    #: unlocked hops fall back to their measured deployment temperature.
    temperature_locked: bool = False
    #: True when ANY endpoint in this chain refuses `tools` while reasoning is
    #: on (see `_TOOLS_REQUIRE_REASONING_OFF`). A tools request on such a chain
    #: must send top-level `reasoning_effort: "none"` — chain-level for the same
    #: merge reason as temperature: a per-deployment setting would be overridden
    #: by a caller's `reasoning_effort`, re-poisoning the locked hop.
    reasoning_off_forced: bool = False


async def complete_deployment_once(
    deployment: dict[str, Any], kwargs: dict[str, Any],
) -> Any:
    """Public SDK call for an operation which owns stream consumption/failover.

    Reuse the scenario's resolved credentials/model/metadata, but never put a
    second Router fallback iterator inside the caller's own fallback loop.
    No private LiteLLM methods and no mutation of the cached shared Router.
    """
    import litellm

    params = {**deployment["litellm_params"], **kwargs}
    params["model"] = deployment["litellm_params"]["model"]
    params["num_retries"] = 0
    return await litellm.acompletion(**params)


# -- validation ---------------------------------------------------------------
#
# litellm's `post_call_rules` is a global list of plain functions that receive
# only the response text, so it cannot carry a per-call validator by itself.
# One registered rule reads the validator from a ContextVar, which the caller
# binds around its own call. The indirection buys the thing that matters: the
# rejection is raised *inside* litellm's call stack, so `Router` sees it as a
# failed attempt and moves to the next endpoint. A validator applied after
# `acompletion` returns cannot fail over at all - which is exactly the bug the
# six services that parsed JSON after the call were carrying.

#: Sentinel distinguishing "the validator returned None" from "it never ran".
#: The difference matters: litellm applies post-call rules only to response
#: shapes it recognises, so a skipped rule leaves no value behind, and a caller
#: that cannot tell the two apart hands back None as if it were a parsed result.
_NOT_VALIDATED = object()

_validator_var: ContextVar[Callable[[str], Any] | None] = ContextVar(
    "jc_llm_validator", default=None
)
_validated_var: ContextVar[Any] = ContextVar(
    "jc_llm_validated", default=_NOT_VALIDATED
)

#: ContextVars, not thread-locals: the rule runs on whichever thread litellm
#: dispatched the attempt to. Verified for the async path, the sync path, and
#: the sync path inside a worker thread (which is how the harness streams).


@contextmanager
def validation_scope(validator: Callable[[str], Any] | None) -> Any:
    """Bind a validator for the calls made inside this block."""
    token = _validator_var.set(validator)
    parsed = _validated_var.set(_NOT_VALIDATED)
    try:
        yield
    finally:
        _validator_var.reset(token)
        _validated_var.reset(parsed)


def take_validated() -> Any:
    """The value the validator returned, so callers need not parse twice."""
    value = _validated_var.get()
    return None if value is _NOT_VALIDATED else value


def has_validated() -> bool:
    """Whether the validation rule actually ran for the call just made."""
    return _validated_var.get() is not _NOT_VALIDATED


def validation_rule(text: str | None) -> Any:
    """The single `post_call_rules` entry. Public for direct testing."""
    validator = _validator_var.get()
    if validator is None or text is None:
        return True
    try:
        _validated_var.set(validator(text))
    except Exception as exc:  # noqa: BLE001
        # Returning a decision dict (not raising) is litellm's contract here; it
        # converts this into APIResponseValidationError inside the call stack.
        return {"decision": False, "message": f"{VALIDATION_ERROR_MARKER}: {exc}"}
    return True


_rule_registered = False


def register_validation_rule() -> None:
    """Install the validation rule on litellm once per process."""
    global _rule_registered
    if _rule_registered:
        return
    import litellm

    rules = list(litellm.post_call_rules or [])
    if validation_rule not in rules:
        rules.append(validation_rule)
        litellm.post_call_rules = rules
    _rule_registered = True


# -- router construction ------------------------------------------------------

_router_cache: dict[str, ScenarioTransport] = {}


def clear_router_cache() -> None:
    """Drop cached routers. For tests and for config reloads."""
    _router_cache.clear()


def router_for(scenario: str) -> ScenarioTransport:
    """The `litellm.Router` for a scenario, plus the alias to address.

    Cached per scenario: a Router owns connection pools and cooldown state, and
    rebuilding it per call would discard the cooldown knowledge that keeps a
    failing endpoint out of the way.
    """
    cached = _router_cache.get(scenario)
    if cached is not None:
        return cached

    from litellm import Router

    from jc.llm.router import get_llm_router

    register_validation_rule()

    jc_router = get_llm_router()
    chain = jc_router.chain_for(scenario)

    model_list: list[dict[str, Any]] = []
    aliases: list[str] = []
    skipped: list[SkippedEndpoint] = []
    for index, endpoint in enumerate(chain):
        api_base, api_key = jc_router.credentials_for(endpoint)
        if not api_key:
            # Not configured in this deployment. Kept out of the router so a
            # missing key never enters the failure-rate numbers - an attempt
            # that was never made is not an endpoint that failed - but still
            # surfaced on the audit row, because a chain quietly serving from
            # its second model is a deployment fault someone has to see.
            logger.warning(
                "LLM scenario %s: skipping %s (missing %s)",
                scenario,
                endpoint.model,
                endpoint.api_key_env,
            )
            skipped.append(
                SkippedEndpoint(
                    model=endpoint.model,
                    provider=endpoint.provider,
                    api_key_env=endpoint.api_key_env,
                )
            )
            continue
        alias = f"{scenario}-{index}"
        model_list.append(
            {
                "model_name": alias,
                "litellm_params": {
                    "model": endpoint.model,
                    "api_base": api_base,
                    "api_key": api_key,
                    "timeout": endpoint.timeout_sec,
                    # See `_TEMPERATURE_LOCKED_MODELS`: for a locked model the
                    # gateway's own default (1) is the only accepted value, so
                    # the correct parameter is no parameter.
                    **(
                        {}
                        if is_temperature_locked(endpoint.model)
                        else {"temperature": endpoint.temperature}
                    ),
                    **(
                        {"reasoning_effort": endpoint.reasoning_effort}
                        if getattr(endpoint, "reasoning_effort", None) is not None
                        else {}
                    ),
                    **(
                        {"max_tokens": endpoint.max_tokens}
                        if getattr(endpoint, "max_tokens", None) is not None
                        else {}
                    ),
                    **(
                        {"extra_body": endpoint.extra_body}
                        if getattr(endpoint, "extra_body", None) is not None
                        else {}
                    ),
                },
                "model_info": {"jc_provider": endpoint.provider or ""},
            }
        )
        aliases.append(alias)

    if not model_list:
        raise NoUsableEndpoint(
            f"No usable endpoint for scenario {scenario}: every entry is missing "
            "its API key environment variable"
        )

    primary = aliases[0]
    # One entry per position, not a single flat {primary: rest} map. litellm's
    # fallback lookup (`get_fallback_model_group`) keys strictly on the model
    # that just failed, not the original primary - so a flat map only ever
    # covers the first hop. When the *second* endpoint also fails, litellm
    # looks for a "writer-1" key, finds none, and raises instead of trying
    # "writer-2". Transport tests assert the complete chain is reached once
    # without duplicate attempts under the pinned LiteLLM version.
    fallbacks = (
        [{aliases[i]: aliases[i + 1 :]} for i in range(len(aliases) - 1)]
        if len(aliases) > 1
        else None
    )
    from copy import deepcopy

    deployments = tuple(deepcopy(model_list))
    router = Router(
        model_list=model_list,
        fallbacks=fallbacks,
        # The chain *is* the retry policy. litellm retrying the same endpoint
        # would multiply latency on a scenario whose point is to move on.
        num_retries=0,
    )
    transport = ScenarioTransport(
        router,
        primary,
        tuple(skipped),
        deployments,
        any(is_temperature_locked(e.model) for e in chain),
        any(tools_require_reasoning_off(e.model) for e in chain),
    )
    _router_cache[scenario] = transport
    return transport
