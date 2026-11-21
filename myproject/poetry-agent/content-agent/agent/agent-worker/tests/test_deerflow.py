"""DeerFlow client + run monitor against a scripted gateway (httpx.MockTransport). No network."""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from agent_worker.deerflow.client import (
    DeerFlowClient,
    DeerFlowConfig,
    DeerFlowError,
    thread_id_for,
)
from agent_worker.deerflow.parse import extract_output
from agent_worker.deerflow.runtime import DeerFlowRuntime, Hooks
from agent_worker.governance import (
    Budgets,
    BudgetTracker,
    CancelToken,
    CircuitBreaker,
    FakeClock,
    RunCancelled,
    RuntimeFailure,
)
from helpers import RUN_ID, FakeDeerFlow, fence, minimal_output

FINAL = fence(minimal_output())


class Harness:
    def __init__(self, df: FakeDeerFlow, *, budgets: Budgets | None = None, fallback: str = "",
                 breaker_threshold: int = 3) -> None:
        self.df = df
        self.clock = FakeClock()
        self.budgets = budgets or Budgets()
        self.breaker = CircuitBreaker(breaker_threshold, 120.0, self.clock)
        self.client = DeerFlowClient(DeerFlowConfig("http://df", fallback_model=fallback), transport=df.transport())
        self.runtime = DeerFlowRuntime(self.client, self.breaker, self.clock)
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.admitted: list[tuple[str, str]] = []
        self.cancel = CancelToken()
        self.tracker: BudgetTracker | None = None

    def run(self) -> str:
        self.tracker = BudgetTracker(self.budgets, self.clock)
        hooks = Hooks(event=lambda t, p: self.events.append((t, p)), admitted=lambda a, b: self.admitted.append((a, b)))
        return self.runtime.execute(run_id=RUN_ID, body={"input": {"messages": []}}, budgets=self.budgets,
                                    tracker=self.tracker, cancel=self.cancel, hooks=hooks, poll_interval=1.0)

    def types(self) -> list[str]:
        return [t for t, _ in self.events]

    def of(self, event_type: str) -> list[dict[str, Any]]:
        return [p for t, p in self.events if t == event_type]


def fail_reason(h: Harness) -> str:
    with pytest.raises(RuntimeFailure) as info:
        h.run()
    return info.value.reason


# ---- success --------------------------------------------------------------------------------------
def test_success_returns_the_final_message_and_reports_metadata_only() -> None:
    h = Harness(FakeDeerFlow(FINAL))
    assert h.run() == FINAL.strip()
    assert h.admitted == [(f"poetry-{RUN_ID}", "df-run-1")]
    assert h.df.idempotency_keys == [f"poetry-worker:{RUN_ID}"]
    assert h.df.model_names == [None]                      # no model override unless a fallback is in play
    assert h.df.bodies[0]["assistant_id"] == "poetry-editor-lead"
    assert h.of("TOOL_CALL") == [{"tool": "get_work_snapshot", "outcome": "ok", "ms": None}]
    usage = h.of("MODEL_USAGE")
    assert usage == [{"model": "test-model", "input_tokens": 100, "output_tokens": 50, "ms": None, "degraded": False}]
    assert h.tracker is not None and (h.tracker.tool_calls, h.tracker.tokens) == (1, 150)
    for _, payload in h.events:
        assert "分析如下" not in json.dumps(payload, ensure_ascii=False)   # model text never goes into an event


def test_every_request_is_scoped_to_one_thread_per_run() -> None:
    h = Harness(FakeDeerFlow(FINAL))
    h.run()
    paths = [p for _, p, _ in h.df.requests]
    assert "/api/threads" in paths
    assert f"/api/threads/poetry-{RUN_ID}/runs" in paths
    assert not any(p.startswith("/api/runs/") for p in paths)          # not the stateless, non-idempotent route
    assert len(thread_id_for(RUN_ID + "-fb")) <= 64


def test_tokens_reported_by_the_run_row_are_reconciled() -> None:
    df = FakeDeerFlow(FINAL)
    df.total_tokens = 900
    h = Harness(df)
    h.run()
    assert h.tracker is not None and h.tracker.tokens == 900


# ---- retries, malformed JSON, 5xx, timeouts -------------------------------------------------------
def test_a_transient_5xx_is_retried_with_backoff_and_reported() -> None:
    df = FakeDeerFlow(FINAL)
    df.get_run_fault, df.get_run_fault_times = "5xx", 2
    h = Harness(df, breaker_threshold=10)
    assert h.run() == FINAL.strip()
    assert h.of("RETRY") == [
        {"attempt": 2, "reason": "HTTP_503", "target": "deerflow", "op": "get_run"},
        {"attempt": 3, "reason": "HTTP_503", "target": "deerflow", "op": "get_run"},
    ]
    assert h.clock.sleeps[:2] == [2.0, 5.0]


def test_malformed_json_and_timeouts_are_retryable() -> None:
    for fault, reason in (("bad_json", "BAD_JSON"), ("timeout", "TIMEOUT")):
        df = FakeDeerFlow(FINAL)
        df.get_run_fault, df.get_run_fault_times = fault, 1
        h = Harness(df)
        assert h.run() == FINAL.strip()
        assert h.of("RETRY")[0]["reason"] == reason


def test_persistent_failure_exhausts_retries_when_the_breaker_stays_closed() -> None:
    df = FakeDeerFlow(FINAL)
    df.get_run_fault, df.get_run_fault_times = "5xx", 99
    h = Harness(df, breaker_threshold=10)
    assert fail_reason(h) == "RETRIES_EXHAUSTED"
    assert len(h.of("RETRY")) == 2 and h.of("CIRCUIT_OPEN") == []


def test_persistent_failure_opens_the_breaker_and_never_falls_back_to_the_stub() -> None:
    df = FakeDeerFlow(FINAL)
    df.get_run_fault, df.get_run_fault_times = "5xx", 99
    h = Harness(df)
    assert fail_reason(h) == "CIRCUIT_OPEN"
    assert h.of("CIRCUIT_OPEN") == [{"target": "deerflow", "reopens_in_s": 120}]


def test_an_open_breaker_blocks_the_next_run_without_calling_the_gateway_then_recovers() -> None:
    df = FakeDeerFlow(FINAL)
    df.get_run_fault, df.get_run_fault_times = "5xx", 3
    h = Harness(df)
    assert fail_reason(h) == "CIRCUIT_OPEN"
    before = len(df.requests)
    assert fail_reason(h) == "CIRCUIT_OPEN" and len(df.requests) == before      # fail fast, gateway untouched
    h.clock.t += 121                                                             # half-open: a probe is allowed
    h.df._gets = 0
    h.df.get_run_fault_times = 0
    assert h.run() == FINAL.strip() and h.breaker.state == "closed"


# ---- non-retryable gateway answers ----------------------------------------------------------------
@pytest.mark.parametrize(("status", "reason"), [(401, "DEERFLOW_AUTH_FAILED"), (403, "DEERFLOW_AUTH_FAILED"),
                                                (409, "DEERFLOW_CONFLICT"), (422, "DEERFLOW_REJECTED")])
def test_create_run_rejections_are_not_retried(status: int, reason: str) -> None:
    df = FakeDeerFlow(FINAL)
    df.create_status = status
    h = Harness(df, fallback="poetry-fallback")
    assert fail_reason(h) == reason
    assert len(df.bodies) == 1 and h.of("RETRY") == []        # no retry, and no model switch for an auth or schema problem


def test_a_gateway_5xx_on_create_does_not_become_a_stub_run() -> None:
    df = FakeDeerFlow(FINAL)
    df.create_status = 500
    assert fail_reason(Harness(df)) == "CIRCUIT_OPEN"


@pytest.mark.parametrize(("status", "reason"), [("error", "DEERFLOW_RUN_ERROR"), ("timeout", "DEERFLOW_RUN_TIMEOUT"),
                                                ("interrupted", "DEERFLOW_RUN_INTERRUPTED")])
def test_terminal_failure_statuses(status: str, reason: str) -> None:
    assert fail_reason(Harness(FakeDeerFlow(FINAL, statuses=["running", status]))) == reason


def test_a_successful_run_with_no_final_ai_message_fails() -> None:
    df = FakeDeerFlow(None)
    assert fail_reason(Harness(df)) == "NO_FINAL_MESSAGE"
    df = FakeDeerFlow(None)
    df.message_rows = [{"seq": 1, "event_type": "llm.ai.response", "category": "message",
                        "content": {"content": "", "tool_calls": [{"name": "x"}]}, "metadata": {}}]
    assert fail_reason(Harness(df)) == "NO_FINAL_MESSAGE"       # last AI message still wanted a tool


def test_a_model_error_fallback_message_is_a_failure_not_an_output() -> None:
    df = FakeDeerFlow(FINAL)
    df.fallback = True
    assert fail_reason(Harness(df)) == "MODEL_ERROR_FALLBACK"


# ---- budgets --------------------------------------------------------------------------------------
def test_wall_clock_budget_cancels_the_remote_run() -> None:
    df = FakeDeerFlow(FINAL, statuses=["running"])
    h = Harness(df, budgets=Budgets(max_wall_seconds=5))
    assert fail_reason(h) == "WALL_TIMEOUT"
    assert any(m == "POST" and p.endswith("/cancel") for m, p, _ in df.requests)


def test_tool_call_budget() -> None:
    df = FakeDeerFlow(None, statuses=["running"])
    df.message_rows = [{"seq": n, "event_type": "llm.tool.result", "category": "message",
                        "content": {"name": "get_work_snapshot", "status": "success"}, "metadata": {}} for n in (1, 2, 3)]
    h = Harness(df, budgets=Budgets(max_tool_calls=1))
    assert fail_reason(h) == "TOOL_BUDGET_EXCEEDED" and len(h.of("TOOL_CALL")) == 3


def test_token_budget() -> None:
    h = Harness(FakeDeerFlow(FINAL, statuses=["running", "success"]), budgets=Budgets(max_tokens=100))
    assert fail_reason(h) == "TOKEN_BUDGET_EXCEEDED"


def test_budget_updates_are_throttled() -> None:
    df = FakeDeerFlow(FINAL, statuses=["running"] * 12 + ["success"])
    h = Harness(df)
    h.run()
    assert len(h.of("BUDGET_UPDATE")) <= 2


# ---- cancellation ---------------------------------------------------------------------------------
def test_cancellation_stops_polling_and_cancels_the_remote_run() -> None:
    df = FakeDeerFlow(FINAL, statuses=["running"] * 10)
    h = Harness(df)
    calls = []
    df.on_get_run = lambda: (calls.append(1), h.cancel.cancel("user") if len(calls) == 2 else None)
    with pytest.raises(RunCancelled):
        h.run()
    assert len(calls) == 2 and any(p.endswith("/cancel") for _, p, _ in df.requests)


# ---- explicit fallback model (upstream 2.2.0 has no automatic failover) ---------------------------
def test_a_model_error_switches_to_the_configured_fallback_model_and_is_marked_degraded() -> None:
    df = FakeDeerFlow(FINAL, statuses=["error", "success"])
    df.fallback_final_text = FINAL
    h = Harness(df, fallback="poetry-fallback")
    assert h.run() == FINAL.strip()
    assert df.model_names == [None, "poetry-fallback"]
    assert df.idempotency_keys == [f"poetry-worker:{RUN_ID}", f"poetry-worker:{RUN_ID}-fb"]
    assert [a[0] for a in h.admitted] == [f"poetry-{RUN_ID}", f"poetry-{RUN_ID}-fb"]
    assert {"attempt": 2, "reason": "MODEL_FALLBACK:DEERFLOW_RUN_ERROR", "target": "deerflow", "op": "switch_model"} in h.of("RETRY")
    assert h.of("MODEL_USAGE")[-1]["degraded"] is True and h.of("MODEL_USAGE")[-1]["model"] == "fallback-model"


def test_without_a_configured_fallback_a_model_error_is_just_a_failure() -> None:
    h = Harness(FakeDeerFlow(FINAL, statuses=["error"]))
    assert fail_reason(h) == "DEERFLOW_RUN_ERROR" and h.df.model_names == [None]


def test_the_fallback_is_tried_once() -> None:
    h = Harness(FakeDeerFlow(FINAL, statuses=["error"]), fallback="poetry-fallback")
    assert fail_reason(h) == "DEERFLOW_RUN_ERROR"
    assert h.df.model_names == [None, "poetry-fallback"] and len(h.of("RETRY")) == 1


def test_no_fallback_after_the_run_was_cancelled() -> None:
    df = FakeDeerFlow(FINAL, statuses=["running", "error"])
    h = Harness(df, fallback="poetry-fallback")
    df.on_get_run = lambda: h.cancel.cancel("user")
    with pytest.raises(RunCancelled):
        h.run()
    assert df.model_names == [None]


# ---- client details ---------------------------------------------------------------------------------
def test_auth_headers_follow_the_gateway_contract() -> None:
    assert DeerFlowConfig("http://df").headers() == {}
    assert DeerFlowConfig("http://df", token="shared-secret").headers() == {
        "X-DeerFlow-Internal-Token": "shared-secret", "X-DeerFlow-Owner-User-Id": "poetry-authoring"}
    assert DeerFlowConfig("http://df", token="dfp_abc").headers() == {"Authorization": "Bearer dfp_abc"}
    assert DeerFlowConfig("http://df", token="dfp_abc", auth_mode="internal").headers().keys() == {
        "X-DeerFlow-Internal-Token", "X-DeerFlow-Owner-User-Id"}
    assert DeerFlowConfig("http://df", token="x", auth_mode="none").headers() == {}
    assert DeerFlowConfig("http://df", token="x", owner_user_id="o").headers()["X-DeerFlow-Owner-User-Id"] == "o"


def test_the_internal_token_is_sent_on_every_request_with_csrf_on_mutations() -> None:
    """CSRFMiddleware does not exempt the internal token (only an Authorization header), so POSTs carry the pair."""
    df = FakeDeerFlow(FINAL)
    client = DeerFlowClient(DeerFlowConfig("http://df", token="shared-secret"), transport=df.transport())
    client.ensure_thread("t1", {})
    client.get_run("t1", "r1")
    client.cancel("t1", "r1")
    client.ping()
    assert all(h.get("x-deerflow-internal-token") == "shared-secret" for _, _, h in df.requests)
    assert not any("authorization" in h for _, _, h in df.requests)
    for method, _, h in df.requests:
        if method == "POST":
            token = h["x-csrf-token"]
            assert len(token) >= 32 and h["cookie"] == f"csrf_token={token}"        # double-submit: header equals cookie
        else:
            assert "x-csrf-token" not in h and "cookie" not in h
    assert len({h["x-csrf-token"] for m, _, h in df.requests if m == "POST"}) == 1   # stable for the client's life


def test_bearer_and_open_gateway_modes_send_no_csrf_pair() -> None:
    for config in (DeerFlowConfig("http://df", token="dfp_abc"), DeerFlowConfig("http://df")):
        df = FakeDeerFlow(FINAL)
        DeerFlowClient(config, transport=df.transport()).ensure_thread("t1", {})
        assert "x-csrf-token" not in df.requests[0][2] and "cookie" not in df.requests[0][2]


def test_ping_and_segment_validation() -> None:
    df = FakeDeerFlow(FINAL)
    client = DeerFlowClient(DeerFlowConfig("http://df"), transport=df.transport())
    assert client.ping() is True
    df.health_status = 503
    assert client.ping() is False
    for bad in ("../x", "a/b", "", "a" * 65, "a b"):
        with pytest.raises(DeerFlowError):
            client.get_run(bad, "r")


def test_thread_ids_are_valid_for_any_run_id() -> None:
    import re

    for run_id in (RUN_ID, "run_" + "a" * 120, "run_x"):
        assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", thread_id_for(run_id))


def test_a_run_row_without_status_is_a_bad_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"run_id": "x"})

    client = DeerFlowClient(DeerFlowConfig("http://df"), transport=httpx.MockTransport(handler))
    with pytest.raises(DeerFlowError) as info:
        client.get_run("t", "r")
    assert info.value.reason == "BAD_JSON" and info.value.retryable


# ---- extracting agent-output/1 from the last message -----------------------------------------------
def test_the_last_json_fence_wins() -> None:
    first, last = minimal_output(summary="先写的"), minimal_output(summary="最后的")
    text = fence(first) + "\n我再想想,更正如下:\n" + fence(last)
    value, violations = extract_output(text, 60000)
    assert violations == [] and value["summary"] == "最后的"


def test_fence_variants_and_bare_object() -> None:
    body = json.dumps(minimal_output(), ensure_ascii=False)
    for text in (f"```json\n{body}\n```", f"前言\n```JSON\n{body}\n```\n后记", f"```json \n{body}\n``` "):
        value, violations = extract_output(text, 60000)
        assert violations == [] and value["schema"] == "agent-output/1", text
    value, violations = extract_output(body, 60000)
    assert violations == [] and value["task_type"] == "GAP_ANALYSIS"


@pytest.mark.parametrize(("text", "code"), [
    ("", "V1.EMPTY_MESSAGE"), ("   \n", "V1.EMPTY_MESSAGE"),
    ("我分析完了,没有结构化输出。", "V1.NO_JSON_FENCE"),
    ("```json\n{not valid json}\n```", "V1.BAD_JSON"),
    ('```json\n["a", "b"]\n```', "V1.NOT_OBJECT"),
    ("```python\nprint(1)\n```", "V1.NO_JSON_FENCE"),
])
def test_unusable_messages_are_rejected_with_a_code(text: str, code: str) -> None:
    value, violations = extract_output(text, 60000)
    assert value is None and [f"{v.rule}.{v.code}" for v in violations] == [code]


def test_an_over_long_message_is_rejected_before_parsing() -> None:
    value, violations = extract_output(fence(minimal_output(summary="长" * 1000)), 200)
    assert value is None and [f"{v.rule}.{v.code}" for v in violations] == ["V8.OUTPUT_TOO_LONG"]


def test_a_broken_last_fence_is_not_rescued_by_an_earlier_good_one() -> None:
    text = fence(minimal_output()) + "\n```json\n{broken\n```\n"
    value, violations = extract_output(text, 60000)
    assert value is None and violations[0].code == "BAD_JSON"
