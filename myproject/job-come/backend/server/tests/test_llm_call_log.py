"""The LLM audit log records what actually happened, and never breaks a call.

These run against a real `litellm.Router` with only the gateway call faked; see
`tests/conftest.py` for why the seam is there and not at the litellm module.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from conftest import (
    capture_audit_rows,
    fake_gateway,
    gateway_error,
    install_routing,
    settle_callbacks,
)
from jc.llm import call_log as llm_log_service
from jc.llm.call_context import bind_llm_context, clear_llm_context, llm_context
from jc.llm.call_log import (
    AttemptRecord,
    CallRecord,
    LLMLogContext,
    error_code_for,
    prompt_text_from_messages,
    reasoning_from_response,
    usage_from_response,
)
from jc.llm.router import LLMRouter


@pytest.fixture(autouse=True)
def _clean_context() -> Any:
    clear_llm_context()
    yield
    clear_llm_context()


def _chain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, models: list[str]
) -> LLMRouter:
    return install_routing(monkeypatch, tmp_path, "test", models)


# --- failover attribution -------------------------------------------------


@pytest.mark.asyncio
async def test_final_model_is_the_one_that_actually_answered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    router = _chain(monkeypatch, tmp_path, ["openai/first", "openai/second"])

    with capture_audit_rows() as captured:
        with fake_gateway({"first": gateway_error("server"), "second": "ok"}):
            await router.acompletion("test", messages=[{"role": "user", "content": "hi"}])
        await settle_callbacks()

    # One row for the logical call, not one per physical attempt: a chain that
    # recovers must not be counted as two calls in a cost report.
    assert len(captured) == 1
    record = captured[0]
    # The whole point of the log: not the configured head of the chain.
    assert record.final_model == "second"
    assert record.status == "success"
    assert [(a.attempt_index, a.status) for a in record.attempts] == [
        (0, "failed"),
        (1, "success"),
    ]
    assert record.attempts[0].model == "first"
    # A transport error is not a content problem.
    assert record.attempts[0].validator_failed is False


@pytest.mark.asyncio
async def test_validator_failure_is_recorded_as_a_content_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """HTTP 200 with unusable JSON: litellm calls this success, JC does not.

    The distinction has to survive into the row, because the two have opposite
    remedies: an unreachable gateway is an ops problem, a model that cannot hold
    a JSON contract is a routing problem.
    """
    router = _chain(monkeypatch, tmp_path, ["openai/first", "openai/second"])

    def parse(response: Any) -> dict[str, bool]:
        if "ok" not in router.content_from_response(response):
            raise ValueError("unusable response")
        return {"ok": True}

    with capture_audit_rows() as captured:
        with fake_gateway({"first": "not json at all", "second": '{"ok": true}'}):
            result = await router.acompletion(
                "test", messages=[], response_validator=parse
            )
        await settle_callbacks()

    assert result == {"ok": True}
    attempts = captured[0].attempts
    assert attempts[0].status == "failed"
    assert attempts[0].validator_failed is True
    # Not grouped with transport errors, even though litellm wraps it as one.
    assert attempts[0].error_code == "invalid_response"
    assert attempts[1].status == "success"
    assert attempts[1].validator_failed is False


@pytest.mark.asyncio
async def test_total_failure_is_recorded_before_the_error_propagates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    router = _chain(monkeypatch, tmp_path, ["openai/first", "openai/second"])

    with capture_audit_rows() as captured:
        with fake_gateway(
            {"first": gateway_error("timeout"), "second": gateway_error("timeout")}
        ) as called:
            with pytest.raises(Exception, match="timed out"):
                await router.acompletion("test", messages=[])
        await settle_callbacks()

    # Each endpoint tried exactly once. A nested fallback map would call the
    # last one twice, double counting a failure and the latency with it.
    assert called == ["openai/first", "openai/second"]
    assert captured[0].status == "failed"
    assert captured[0].final_model is None
    assert captured[0].error_code == "timeout"
    assert len(captured[0].attempts) == 2


@pytest.mark.asyncio
async def test_a_long_chain_reaches_every_endpoint_even_past_the_second_hop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Every configured endpoint is reached once when the whole chain fails.

    Keep the assertion against the installed LiteLLM behavior: a per-position
    fallback map must reach the final configured endpoint without duplicating it.
    """
    router = _chain(monkeypatch, tmp_path, ["openai/a", "openai/b", "openai/c"])
    down = {name: gateway_error("timeout") for name in ("a", "b", "c")}

    with capture_audit_rows() as captured:
        with fake_gateway(down) as called:
            with pytest.raises(Exception, match="timed out"):
                await router.acompletion("test", messages=[])
        await settle_callbacks()

    assert called == ["openai/a", "openai/b", "openai/c"]
    assert [a.model for a in captured[0].attempts] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_missing_api_key_is_a_skipped_attempt_not_a_silent_gap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An unconfigured head of the chain is a deployment fault, so it is visible.

    Without the row the scenario simply answers from its second model, which in
    the audit table is indistinguishable from a healthy primary - so the one
    mistake that silently changes which model serves every request, and what it
    costs, would be the one thing the log cannot show.
    """
    monkeypatch.delenv("JC_LLM_API_KEY", raising=False)
    monkeypatch.setenv("JC_LLM_B_BASE", "https://gateway-b.invalid/v1")
    monkeypatch.setenv("JC_LLM_B_KEY", "k")

    config = tmp_path / "routing.yaml"
    config.write_text(
        """
providers:
  b:
    api_base_env: JC_LLM_B_BASE
    api_key_env: JC_LLM_B_KEY
scenarios:
  test:
    - model: openai/first
    - model: openai/second
      provider: b
""",
        encoding="utf-8",
    )
    router = LLMRouter(config)
    monkeypatch.setattr("jc.llm.router.get_llm_router", lambda: router)
    monkeypatch.setattr("jc.llm.router._env_from_settings", lambda name: None)

    with capture_audit_rows() as captured:
        with fake_gateway({"second": "ok"}) as called:
            await router.acompletion("test", messages=[])
        await settle_callbacks()

    # Never dialled: a missing key must not enter the failure-rate numbers.
    assert called == ["openai/second"]
    attempts = captured[0].attempts
    assert attempts[0].status == "skipped"
    assert attempts[0].model == "openai/first"
    assert attempts[0].error_code == "missing_api_key"
    assert attempts[0].api_base_env == "JC_LLM_API_KEY"
    assert attempts[1].status == "success"
    assert captured[0].final_model == "second"
    # The call still succeeded; a skipped endpoint is not a failed call.
    assert captured[0].status == "success"


@pytest.mark.asyncio
async def test_a_chain_with_no_configured_key_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Nothing to call is a configuration error, not an empty answer."""
    from jc.llm.transport import NoUsableEndpoint

    monkeypatch.delenv("JC_LLM_API_KEY", raising=False)
    config = tmp_path / "routing.yaml"
    config.write_text("scenarios:\n  test:\n    - model: openai/only\n", encoding="utf-8")
    router = LLMRouter(config)
    monkeypatch.setattr("jc.llm.router.get_llm_router", lambda: router)
    monkeypatch.setattr("jc.llm.router._env_from_settings", lambda name: None)

    with pytest.raises(NoUsableEndpoint, match="No usable endpoint"):
        await router.acompletion("test", messages=[])


@pytest.mark.asyncio
async def test_a_late_failure_event_cannot_overwrite_a_recorded_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Success is reported by the caller; failures arrive from litellm's callbacks.

    Those are two clocks. The failure of an earlier hop is normally delivered
    before the next hop is attempted, but litellm also dispatches callbacks
    through copied contexts onto other threads, so an event can land after the
    caller has already recorded the answer. Letting it through would file a
    recovered chain as an outage - the exact misreading this log exists to
    prevent, and the one that is invisible in production because the row looks
    perfectly well-formed.
    """
    from jc.llm import audit_hook

    _chain(monkeypatch, tmp_path, ["openai/only"])

    with capture_audit_rows() as captured:
        async with audit_hook.llm_call_scope("test", "unit", "router"):
            audit_hook.report_success(
                SimpleNamespace(model="openai/only", choices=[], usage=None)
            )
            # The straggler, delivered after the answer was already recorded.
            audit_hook.JCAuditLogger().log_failure_event(
                {"model": "openai/only", "exception": TimeoutError("timed out")},
                None,
                None,
                None,
            )

    record = captured[0]
    assert record.status == "success"
    assert record.final_model == "openai/only"
    assert record.error_code is None
    assert record.error_message is None
    # The attempt itself is still kept: it did happen, and its cost is real.
    assert [a.status for a in record.attempts] == ["success", "failed"]


# --- cost and token capture ------------------------------------------------


@pytest.mark.asyncio
async def test_token_usage_is_attributed_to_the_attempt_that_answered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Usage belongs to the attempt that produced it, not to the chain head."""
    router = _chain(monkeypatch, tmp_path, ["openai/first", "openai/second"])
    monkeypatch.setattr("jc.llm.audit_hook.cost_micro_usd", lambda response: 1234)

    with capture_audit_rows() as captured:
        with fake_gateway({"first": gateway_error("server"), "second": "ok"}):
            await router.acompletion("test", messages=[])
        await settle_callbacks()

    record = captured[0]
    # The failed attempt never produced a response, so it has no usage to claim.
    assert record.attempts[0].total_tokens is None
    assert record.attempts[0].cost_micro_usd is None
    assert record.attempts[1].total_tokens is not None
    assert record.attempts[1].total_tokens > 0
    assert record.attempts[1].cost_micro_usd == 1234


def test_usage_from_response_reads_both_reasoning_shapes() -> None:
    nested = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=3,
            completion_tokens=4,
            total_tokens=7,
            completion_tokens_details=SimpleNamespace(reasoning_tokens=2),
        )
    )
    assert usage_from_response(nested)["reasoning_tokens"] == 2

    flat = {"usage": {"prompt_tokens": 1, "completion_tokens": 1, "reasoning_tokens": 9}}
    assert usage_from_response(flat)["reasoning_tokens"] == 9

    # A missing count stays unknown rather than becoming a misleading zero.
    assert usage_from_response(SimpleNamespace(usage=SimpleNamespace()))["total_tokens"] is None
    assert usage_from_response(SimpleNamespace()) == {}


def test_reasoning_text_is_read_from_either_field_name() -> None:
    a = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(reasoning_content="why"))])
    assert reasoning_from_response(a) == "why"
    b = {"choices": [{"message": {"reasoning": "because"}}]}
    assert reasoning_from_response(b) == "because"
    assert reasoning_from_response(SimpleNamespace(choices=[])) is None


# --- payload handling -----------------------------------------------------


def test_prompt_flattening_drops_image_bytes() -> None:
    messages = [
        {"role": "system", "content": "be good"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "read this"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
            ],
        },
    ]
    text = prompt_text_from_messages(messages)
    assert "be good" in text
    assert "read this" in text
    # Megabytes of base64 would make the audit table unreadable and unusable.
    assert "AAAA" not in text
    assert "<image omitted>" in text


def test_payload_is_omitted_when_logging_content_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = CallRecord(
        scenario="writer",
        context=LLMLogContext(caller="test"),
        prompt_text="personal resume text",
        response_text="rewritten resume",
        attempts=[AttemptRecord(attempt_index=0, model="m", status="success")],
    )
    monkeypatch.setattr(llm_log_service.settings, "jc_llm_log_payload", False)
    call, attempts = llm_log_service._rows_from(record)
    assert call.prompt_text is None
    assert call.response_text is None
    # Metrics survive the content being withheld.
    assert call.status == "failed"
    assert call.attempt_count == 1
    assert len(attempts) == 1


def test_oversized_payload_is_truncated_and_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_log_service.settings, "jc_llm_log_payload", True)
    monkeypatch.setattr(llm_log_service.settings, "jc_llm_log_payload_max_chars", 100)
    record = CallRecord(
        scenario="writer",
        context=LLMLogContext(caller="test"),
        prompt_text="x" * 5000,
    )
    call, _ = llm_log_service._rows_from(record)
    assert call.payload_truncated is True
    assert "truncated" in (call.prompt_text or "")
    assert len(call.prompt_text or "") < 500


def test_error_messages_are_bounded() -> None:
    assert llm_log_service.truncate_error(None) is None
    long = llm_log_service.truncate_error("boom " * 1000) or ""
    # error_message is a VARCHAR(1024); an over-long value would fail the insert.
    assert len(long) <= 1024


# --- failure isolation ----------------------------------------------------


@pytest.mark.asyncio
async def test_a_broken_audit_log_does_not_break_the_users_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    router = _chain(monkeypatch, tmp_path, ["openai/only"])

    class ExplodingSession:
        def __call__(self) -> Any:
            raise RuntimeError("database is gone")

    monkeypatch.setattr("jc.db.session.AsyncSessionLocal", ExplodingSession())
    monkeypatch.setattr(llm_log_service.settings, "jc_llm_log_enabled", True)

    with fake_gateway({"only": "the answer"}):
        response = await router.acompletion("test", messages=[])
    assert router.content_from_response(response) == "the answer"


@pytest.mark.asyncio
async def test_logging_can_be_switched_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_log_service.settings, "jc_llm_log_enabled", False)

    def explode() -> Any:
        raise AssertionError("must not touch the database when logging is off")

    monkeypatch.setattr("jc.db.session.AsyncSessionLocal", explode)
    record = CallRecord(scenario="writer", context=LLMLogContext(caller="test"))
    assert await llm_log_service.record_call(record) is None


# --- ambient context ------------------------------------------------------


def test_ambient_context_merges_without_callers_knowing_each_other() -> None:
    bind_llm_context(user_id="usr_1", actor_kind="user")
    bind_llm_context(profile_id="prof_1")
    context = llm_context("resume_elevator", job_id="job_1")
    assert (context.caller, context.user_id, context.profile_id, context.job_id) == (
        "resume_elevator",
        "usr_1",
        "prof_1",
        "job_1",
    )


def test_unknown_context_field_is_rejected_at_the_call_site() -> None:
    # A typo'd key would otherwise produce rows that silently lack identity.
    with pytest.raises(ValueError, match="Unknown LLM context field"):
        bind_llm_context(userid="usr_1")
    with pytest.raises(ValueError, match="Unknown LLM context field"):
        llm_context("x", resume_id="r_1")


@pytest.mark.asyncio
async def test_call_sites_without_a_context_still_produce_a_usable_row(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    router = _chain(monkeypatch, tmp_path, ["openai/only"])

    with capture_audit_rows() as captured:
        with fake_gateway({"only": "ok"}):
            await router.acompletion("test", messages=[])
        await settle_callbacks()

    # caller is NOT NULL in the schema, so the fallback must be a real value.
    assert captured[0].context.caller == "unknown"


# --- error classification -------------------------------------------------


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (ValueError("empty_model_response"), "empty_model_response"),
        (ValueError("invalid_json_response"), "invalid_json_response"),
        (TimeoutError("timed out"), "timeout"),
        (RuntimeError("429 Too Many Requests"), "rate_limited"),
        (RuntimeError("401 unauthorized"), "auth_failed"),
        (ConnectionError("nodename nor servname provided"), "unreachable"),
        (KeyError("surprise"), "KeyError"),
    ],
)
def test_error_codes_are_stable_grouping_keys(exc: BaseException, expected: str) -> None:
    # Gateways embed request ids and model names in messages, so the raw text
    # cannot be used as a dashboard grouping key.
    assert error_code_for(exc) == expected


# --- cancellation is not a blank row ---------------------------------------


@pytest.mark.asyncio
async def test_cancelled_call_is_recorded_not_dropped() -> None:
    """A task cancelled mid-call must leave a classified row, not a blank one.

    Before this test: a call torn down by `asyncio.CancelledError` (steer,
    stop button, client disconnect, client-side timeout) exited the scope
    through `finally` with no `report_success` ever called and no litellm
    failure callback ever fired (nothing told litellm the call failed - the
    awaiting task was simply destroyed). The row landed with zero attempts,
    `error_code=None`, `error_message=None`: unreadable in a dashboard and
    indistinguishable from a bug in the audit log itself.
    """
    from jc.llm import audit_hook

    with capture_audit_rows() as captured:
        with pytest.raises(asyncio.CancelledError):
            async with audit_hook.llm_call_scope("test", "unit-test", "router") as scope:
                scope.trace_id = "trace-cancel"
                raise asyncio.CancelledError()

    assert len(captured) == 1
    row = captured[0]
    assert row.status == "failed"
    assert row.error_code == "cancelled"
    assert row.error_message is not None
    assert row.attempts == []


def test_sync_scope_cancellation_is_also_recorded() -> None:
    """The harness's synchronous scope gets the same classification.

    `sync_call_scope` is the one the DeerFlow harness streams through on its
    worker thread; it must not silently swallow the same information the
    async path now captures.
    """
    from jc.llm import audit_hook

    rows: list[Any] = []

    with audit_hook.audit_sink(rows.append):
        with pytest.raises(asyncio.CancelledError):
            with audit_hook.sync_call_scope("test", "unit-test", "harness") as scope:
                scope.trace_id = "trace-cancel-sync"
                raise asyncio.CancelledError()

    assert len(rows) == 1
    row = rows[0]
    assert row.status == "failed"
    assert row.error_code == "cancelled"
    assert row.attempts == []


def test_scope_exit_after_success_keeps_the_success_verdict() -> None:
    """A late, unrelated exception on the way out must not erase a real success.

    `report_success` runs inside the `async with`/`with` body before control
    returns to the context manager; a failure during teardown (for example
    the audit flush itself) must not flip a call that actually succeeded into
    a cancelled-looking row.
    """
    from jc.llm import audit_hook

    scope = audit_hook._CallScope(scenario="test", caller="unit-test", channel="router")
    audit_hook._note_unobserved_exit(scope, asyncio.CancelledError())
    assert scope.status == "failed"

    scope.status = "success"
    scope.error_code = None
    scope.error_message = None
    audit_hook._note_unobserved_exit(scope, RuntimeError("teardown blew up"))
    assert scope.status == "success"
    assert scope.error_code is None
    assert scope.error_message is None
