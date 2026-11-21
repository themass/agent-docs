"""Shared fakes: a control bridge and a DeerFlow gateway, both on ``httpx.MockTransport``. No network."""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

FIXTURES = Path(__file__).resolve().parent / "fixtures"
RUN_ID = "run_0123456789abcdef0123456789abcdef"
MANDATE_ID = "mandate_0123456789abcdef0123456789abcdef"
TASK_ID = "task_0123456789abcdef0123456789abcdef"
WORK_ID = "work-chun-wang"
CONTROL_TOKEN = "control-test-token"
WORKER_TOKEN = "worker-test-token"


def load_fixture(style: str = "snake") -> dict[str, Any]:
    return json.loads((FIXTURES / f"chun_wang_studio_view.{style}.json").read_text(encoding="utf-8"))


class FakeBridge:
    """In-memory control bridge. ``fail`` maps a (method, path-regex) to a list of statuses to return first."""

    def __init__(self, view: dict[str, Any] | None = None, style: str = "snake") -> None:
        self.view = view if view is not None else load_fixture(style)
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.states: list[tuple[str, str | None]] = []
        self.admissions: list[dict[str, Any]] = []
        self.proposals: dict[str, dict[str, Any]] = {}
        self.proposal_posts = 0
        self.requests: list[tuple[str, str]] = []
        self.fail: list[tuple[str, re.Pattern[str], list[int]]] = []
        self.token_seen: set[str] = set()
        self.on_event: Callable[[str], None] | None = None
        self.studio_view_404 = False
        self.timeline: list[str] = []

    def fail_next(self, method: str, path_regex: str, statuses: list[int]) -> None:
        self.fail.append((method, re.compile(path_regex), list(statuses)))

    def event_types(self) -> list[str]:
        return [t for t, _ in self.events]

    def payloads(self, event_type: str) -> list[dict[str, Any]]:
        return [p for t, p in self.events if t == event_type]

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        self.requests.append((method, path))
        self.token_seen.add(request.headers.get("X-Poetry-Domain-Control-Token", ""))
        for fmethod, pattern, statuses in self.fail:
            if fmethod == method and pattern.search(path) and statuses:
                return httpx.Response(statuses.pop(0), json={"error": "injected"})
        if method == "GET" and path == "/internal/works":
            return httpx.Response(200, json={"status": "OK", "data": {"items": []}})
        if method == "GET" and path.endswith("/studio-view"):
            if self.studio_view_404:
                return httpx.Response(404, json={"error": "no route"})
            return httpx.Response(200, json=self.view if "data" in self.view else {"status": "OK", "data": self.view})
        if method == "GET" and (path.endswith(("/snapshot", "/gap-report"))):
            data = self.view.get("data", self.view)
            if path.endswith("/gap-report"):
                return httpx.Response(200, json={"status": "OK", "data": data.get("gap_report") or data.get("gapReport") or {}})
            plain = {k: v for k, v in data.items() if k not in ("gap_report", "gapReport")}
            return httpx.Response(200, json={"status": "OK", "data": plain})
        body = json.loads(request.content) if request.content else {}
        if method == "POST" and path.endswith("/events"):
            self.events.append((body["event_type"], body["payload"]))
            self.timeline.append(f"event:{body['event_type']}")
            if self.on_event:
                self.on_event(body["event_type"])
            return httpx.Response(200, json={"status": "OK", "data": {}})
        if method == "PUT" and path.endswith("/state"):
            self.states.append((body["status"], body.get("reason")))
            self.timeline.append(f"state:{body['status']}")
            return httpx.Response(200, json={"status": "OK", "data": {}})
        if method == "PUT" and path.endswith("/admission"):
            self.admissions.append(body)
            return httpx.Response(200, json={"status": "OK", "data": {}})
        if method == "POST" and path == "/internal/proposals":
            self.proposal_posts += 1
            self.timeline.append("proposal")
            key = body["idempotency_key"]
            self.proposals.setdefault(key, body)
            return httpx.Response(200, json={"status": "REVIEW_REQUIRED", "data": {"proposal_id": body["proposal_id"]}})
        return httpx.Response(404, json={"error": "no route"})


class FakeDeerFlow:
    """Scripted DeerFlow gateway. ``statuses`` is consumed one per GET run; the last one repeats."""

    def __init__(self, final_text: str | None = None, statuses: list[str] | None = None) -> None:
        self.final_text = final_text
        self.statuses = statuses or ["running", "success"]
        self.requests: list[tuple[str, str, dict[str, str]]] = []
        self.bodies: list[dict[str, Any]] = []
        self.create_status = 200
        self.thread_status = 200
        self.message_rows: list[dict[str, Any]] | None = None
        self.total_tokens = 0
        self.fallback = False
        self.on_get_run: Callable[[], None] | None = None
        self._gets = 0
        self.idempotency_keys: list[str] = []
        self.get_run_fault: str | None = None      # "5xx" | "bad_json" | "timeout"
        self.get_run_fault_times = 0
        self.fallback_final_text: str | None = None  # served once a run carries context.model_name
        self.model_names: list[str | None] = []
        self.health_status = 200

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _rows(self, thread: str = "") -> list[dict[str, Any]]:
        if self.message_rows is not None:
            return self.message_rows
        if thread.endswith("-fb") and self.fallback_final_text is not None:
            return [{"seq": 1, "event_type": "llm.ai.response", "category": "message",
                     "content": {"content": self.fallback_final_text, "tool_calls": [],
                                 "usage_metadata": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}},
                     "metadata": {"model": "fallback-model", "status": "ok"}}]
        rows = [
            {"seq": 1, "event_type": "llm.tool.result", "category": "message",
             "content": {"name": "get_work_snapshot", "status": "success"}, "metadata": {}},
        ]
        if self.final_text is not None:
            rows.append({"seq": 2, "event_type": "llm.ai.response", "category": "message",
                         "content": {"content": self.final_text, "tool_calls": [],
                                     "usage_metadata": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}},
                         "metadata": {"model": "test-model", "status": "fallback" if self.fallback else "ok"}})
        return rows

    def _handle(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        self.requests.append((method, path, dict(request.headers)))
        if method == "GET" and path == "/health":
            return httpx.Response(self.health_status, json={"status": "ok"})
        if method == "POST" and path == "/api/threads":
            return httpx.Response(self.thread_status, json={"thread_id": json.loads(request.content)["thread_id"]})
        if method == "POST" and re.fullmatch(r"/api/threads/[^/]+/runs", path):
            body = json.loads(request.content)
            self.bodies.append(body)
            self.model_names.append((body.get("context") or {}).get("model_name"))
            self.idempotency_keys.append(request.headers.get("Idempotency-Key", ""))
            if self.create_status != 200:
                return httpx.Response(self.create_status, json={"detail": "x"})
            return httpx.Response(200, json={"run_id": "df-run-1", "thread_id": path.split("/")[3], "status": "pending"})
        if method == "GET" and re.fullmatch(r"/api/threads/[^/]+/runs/[^/]+", path):
            if self.on_get_run:
                self.on_get_run()
            if self.get_run_fault and self.get_run_fault_times > 0:
                self.get_run_fault_times -= 1
                if self.get_run_fault == "timeout":
                    raise httpx.ReadTimeout("slow", request=request)
                if self.get_run_fault == "bad_json":
                    return httpx.Response(200, content=b"<html>not json</html>")
                return httpx.Response(503, json={"detail": "down"})
            status = self.statuses[min(self._gets, len(self.statuses) - 1)]
            self._gets += 1
            return httpx.Response(200, json={"run_id": "df-run-1", "status": status, "total_tokens": self.total_tokens})
        if method == "GET" and path.endswith("/messages"):
            after = int(request.url.params.get("after_seq", "0") or 0)
            thread = path.split("/")[3]
            return httpx.Response(200, json={"data": [r for r in self._rows(thread) if r["seq"] > after], "has_more": False})
        if method == "POST" and path.endswith("/cancel"):
            return httpx.Response(202)
        return httpx.Response(404)


class SyncExecutor:
    """Runs submitted work inline so tests are deterministic."""

    def submit(self, fn: Callable[..., Any], *args: Any) -> None:
        fn(*args)

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        pass


def fence(obj: Any) -> str:
    return "分析如下。\n```json\n" + json.dumps(obj, ensure_ascii=False) + "\n```\n"


def minimal_output(task_type: str = "GAP_ANALYSIS", **overrides: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "schema": "agent-output/1", "task_type": task_type, "summary": "测试摘要",
        "items": [{"kind": "GAP", "epistemic": "DRAFT_TEXT", "target_ref": None, "body": "缺口说明",
                   "evidence_refs": ["claim-bg-city"], "severity": "HIGH", "annotation": None, "source_request": None}],
        "unknowns": [], "human_review_question": "是否继续?",
    }
    out.update(overrides)
    return out


# ---- builders shared by the runner / app tests ---------------------------------------------------
def make_settings(**over: Any) -> Any:
    from agent_worker.config import Settings

    base: dict[str, Any] = {
        "port": 8102, "profile_root": Path(__file__).resolve().parents[2] / "deerflow-profile",
        "control_url": "http://bridge", "control_token": CONTROL_TOKEN, "worker_token": WORKER_TOKEN,
        "deerflow_enabled": True, "deerflow_url": "http://df", "deerflow_token": "", "deerflow_assistant_id": "poetry-editor-lead",
        "deerflow_auth_mode": "auto", "deerflow_owner_user_id": "poetry-authoring", "deerflow_fallback_model": "",
        "max_concurrent_runs": 2, "queue_limit": 2, "control_timeout": 5.0, "deerflow_timeout": 5.0, "poll_interval": 1.0,
    }
    base.update(over)
    return Settings(**base)


def make_runner(bridge: FakeBridge, df: FakeDeerFlow | None = None, *, clock: Any = None,
                executor: Any = None, fallback_model: str = "", breaker_threshold: int = 3, **settings: Any) -> Any:
    from agent_worker.control import ControlClient
    from agent_worker.deerflow.client import DeerFlowClient, DeerFlowConfig
    from agent_worker.deerflow.runtime import DeerFlowRuntime
    from agent_worker.governance import CircuitBreaker, FakeClock
    from agent_worker.runner import Runner

    clock = clock or FakeClock()
    breaker = CircuitBreaker(breaker_threshold, 120.0, clock)
    control = ControlClient("http://bridge", CONTROL_TOKEN, transport=bridge.transport(), sleep=lambda s: None)
    runtime = None
    if df is not None:
        client = DeerFlowClient(DeerFlowConfig("http://df", fallback_model=fallback_model), transport=df.transport())
        runtime = DeerFlowRuntime(client, breaker, clock)
    return Runner(make_settings(**settings), control, runtime, breaker=breaker, clock=clock,
                  executor=executor or SyncExecutor())


def make_request(runtime: str = "STUB", task_type: str = "GAP_ANALYSIS", **over: Any) -> Any:
    from agent_worker.runner import DispatchRequest

    fields: dict[str, Any] = {
        "run_id": RUN_ID, "task_id": TASK_ID, "mandate_id": MANDATE_ID, "work_id": WORK_ID, "task_type": task_type,
        "instructions": "请 publish 这首诗", "runtime": runtime, "profile_fingerprint": "f" * 64, "actor_role": "CONTENT_EDITOR",
    }
    fields.update(over)
    return DispatchRequest(**fields)


class HoldExecutor:
    """Accepts work but never runs it (a queued run)."""

    def __init__(self) -> None:
        self.pending: list[tuple[Callable[..., Any], tuple[Any, ...]]] = []

    def submit(self, fn: Callable[..., Any], *args: Any) -> None:
        self.pending.append((fn, args))

    def run_all(self) -> None:
        while self.pending:
            fn, args = self.pending.pop(0)
            fn(*args)

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        pass


VID = "text-chun-wang-draft"


def annotation_item(**ann: Any) -> dict[str, Any]:
    body = {"version_id": VID, "line_seq": 2, "annotation_kind": "WORD", "audience": "PRIMARY",
            "content": "草木深:草木长得茂盛。", "claim_value": "草木深:草木长得茂盛。",
            "certainty": "LIKELY", "source_id": None}
    body.update(ann)
    return {"kind": "ANNOTATION", "epistemic": "INTERPRETATION", "target_ref": f"line:{VID}#2", "body": "第二句字词注释草稿",
            "evidence_refs": [f"line:{VID}#2"], "severity": None, "annotation": body, "source_request": None}


def source_request_item(**over: Any) -> dict[str, Any]:
    item = {"kind": "SOURCE_REQUEST", "epistemic": "FACT_REQUEST", "target_ref": "claim:claim-bg-city",
            "body": "需要为该 claim 找可核对的来源", "evidence_refs": ["claim-bg-city"], "severity": "HIGH",
            "annotation": None,
            "source_request": {"claim_ref": "claim-bg-city", "what_to_verify": "沦陷期京城状况的记载",
                               "suggested_source_kind": "OFFICIAL_HISTORY", "suggested_source_title": None}}
    item.update(over)
    return item
