"""Run lifecycle: concurrency cap, event publishing, cancellation, finalisation.

Responsibilities split with the BFF (it already created the run and set it RUNNING before dispatch):
the worker only writes events, the final state (AWAITING_REVIEW / FAILED) and the proposal. The only
extra admission is DEERFLOW's runtime correlation, written with status RUNNING.

Cancellation: the BFF calls ``cancel`` first and, on success, writes FAILED itself but NOT a
``RUN_CANCELLED`` event. So the worker appends exactly one ``RUN_CANCELLED`` and from that moment writes
nothing else for the run: not events, not state, not a proposal. Model output arriving later is dropped.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import traceback
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from agent_worker import stub
from agent_worker.compile import compile_proposal, validate_proposal
from agent_worker.config import Settings
from agent_worker.control import ControlClient, ControlError
from agent_worker.deerflow.parse import extract_output
from agent_worker.deerflow.prompt import build_prompt, mandate_body
from agent_worker.deerflow.runtime import DeerFlowRuntime, Hooks
from agent_worker.governance import (
    BudgetTracker,
    CancelToken,
    CircuitBreaker,
    RunCancelled,
    RuntimeFailure,
    SystemClock,
    load_budgets,
)
from agent_worker.snapshot import SnapshotView
from agent_worker.validate import Violation, validate_output

log = logging.getLogger("agent_worker.runner")

MAX_FINISHED = 512
MAX_TOMBSTONES = 512


@dataclass(frozen=True)
class DispatchRequest:
    run_id: str
    task_id: str
    mandate_id: str
    work_id: str
    task_type: str
    instructions: str
    runtime: str
    profile_fingerprint: str
    actor_role: str


@dataclass
class RunContext:
    request: DispatchRequest
    cancel: CancelToken = field(default_factory=CancelToken)
    lock: threading.Lock = field(default_factory=threading.Lock)
    silenced: bool = False  # set by a user cancel: no further writes of any kind
    cancel_announced: bool = False
    state: str = "QUEUED"

    @property
    def run_id(self) -> str:
        return self.request.run_id


class Runner:
    def __init__(
        self,
        settings: Settings,
        control: ControlClient,
        deerflow: DeerFlowRuntime | None,
        *,
        breaker: CircuitBreaker | None = None,
        clock: Any = None,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self.settings = settings
        self.control = control
        self.deerflow = deerflow
        self.clock = clock or SystemClock()
        self.breaker = breaker or CircuitBreaker(3, 120.0, self.clock)
        self._executor = executor or ThreadPoolExecutor(max_workers=settings.max_concurrent_runs, thread_name_prefix="run")
        self._lock = threading.Lock()
        self._active: dict[str, RunContext] = {}
        self._finished: OrderedDict[str, str] = OrderedDict()
        self._tombstones: OrderedDict[str, None] = OrderedDict()

    # ---- public API ----------------------------------------------------------------------------
    @property
    def active_runs(self) -> int:
        with self._lock:
            return len(self._active)

    def dispatch(self, request: DispatchRequest) -> str:
        """'accepted' | 'duplicate' | 'busy'. Idempotent per run_id for the life of the process."""
        with self._lock:
            if request.run_id in self._active or request.run_id in self._finished or request.run_id in self._tombstones:
                return "duplicate"
            if len(self._active) >= self.settings.max_concurrent_runs + self.settings.queue_limit:
                return "busy"
            ctx = RunContext(request)
            self._active[request.run_id] = ctx
        self._executor.submit(self._guarded, ctx)
        return "accepted"

    def cancel(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            ctx = self._active.get(run_id)
            if ctx is None and run_id in self._finished:
                return {"run_id": run_id, "cancelled": False, "state": self._finished[run_id]}
            if ctx is None:
                # Unknown here (e.g. worker restarted): remember it so a late dispatch is refused,
                # and still announce the cancellation once because the BFF will not.
                self._remember_tombstone(run_id)
        if ctx is None:
            self._announce_unknown_cancel(run_id)
            return {"run_id": run_id, "cancelled": True, "state": "UNKNOWN_TO_WORKER"}
        ctx.silenced = True          # first: later writes from the run thread are dropped
        ctx.cancel.cancel("user")    # wake any sleep / poll
        self._announce_cancel(ctx)   # waits for an in-flight write, then appends RUN_CANCELLED once
        return {"run_id": run_id, "cancelled": True, "state": "CANCELLED"}

    def shutdown(self, wait_seconds: float = 8.0) -> None:
        """Stop accepting work; unfinished runs end FAILED(WORKER_SHUTDOWN) so none stays RUNNING silently."""
        with self._lock:
            contexts = list(self._active.values())
        for ctx in contexts:
            ctx.cancel.cancel("shutdown")
        self._executor.shutdown(wait=True, cancel_futures=False)

    # ---- cancellation helpers ------------------------------------------------------------------
    def _announce_cancel(self, ctx: RunContext) -> None:
        with ctx.lock:
            if ctx.cancel_announced:
                return
            ctx.cancel_announced = True
            self._post_event(ctx.run_id, "RUN_CANCELLED", {"by": "editor", "stage": ctx.state})

    def _announce_unknown_cancel(self, run_id: str) -> None:
        self._post_event(run_id, "RUN_CANCELLED", {"by": "editor", "stage": "not_running_here"})

    def _remember_tombstone(self, run_id: str) -> None:
        self._tombstones[run_id] = None
        while len(self._tombstones) > MAX_TOMBSTONES:
            self._tombstones.popitem(last=False)

    # ---- writes (all go through the gate) ------------------------------------------------------
    def _post_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> bool:
        try:
            self.control.append_event(run_id, event_type, payload)
            return True
        except ControlError as exc:
            log.warning("event %s for %s not recorded (%s)", event_type, run_id, exc.reason)
            return False

    def _emit(self, ctx: RunContext, event_type: str, payload: dict[str, Any]) -> None:
        with ctx.lock:
            if ctx.silenced:
                return
            self._post_event(ctx.run_id, event_type, payload)

    def _write(self, ctx: RunContext, fn: Any) -> bool:
        """Run a state/proposal write unless the run was cancelled. Raises ControlError on failure."""
        with ctx.lock:
            if ctx.silenced:
                return False
            fn()
            return True

    # ---- execution -----------------------------------------------------------------------------
    def _guarded(self, ctx: RunContext) -> None:
        try:
            self._execute(ctx)
        except RunCancelled:
            ctx.state = "CANCELLED"
            if not ctx.silenced:  # shutdown, not a user cancel
                self._fail(ctx, "WORKER_SHUTDOWN")
        except RuntimeFailure as exc:
            self._fail(ctx, exc.reason)
        except Exception as exc:  # noqa: BLE001 - last resort; never leak model text or secrets
            log.error("run %s crashed: %s\n%s", ctx.run_id, type(exc).__name__, "".join(traceback.format_tb(exc.__traceback__)[-3:]))
            self._fail(ctx, "INTERNAL_ERROR")
        finally:
            with self._lock:
                self._active.pop(ctx.run_id, None)
                self._finished[ctx.run_id] = ctx.state
                while len(self._finished) > MAX_FINISHED:
                    self._finished.popitem(last=False)

    def _fail(self, ctx: RunContext, reason: str) -> None:
        ctx.state = "FAILED"
        self._emit(ctx, "RUNTIME_FAILED", {"reason": reason, "generator": ctx.request.runtime})
        try:
            self._write(ctx, lambda: self.control.set_state(ctx.run_id, "FAILED", f"运行失败:{reason}"))
        except ControlError as exc:
            log.error("run %s: FAILED state not recorded (%s)", ctx.run_id, exc.reason)

    def _execute(self, ctx: RunContext) -> None:
        req = ctx.request
        if ctx.silenced:
            ctx.state = "CANCELLED"
            return
        ctx.state = "RUNNING"
        generator = req.runtime
        self._emit(ctx, "RUN_STARTED", {"runtime": req.runtime, "generator": generator, "task_type": req.task_type,
                                        "profile_fingerprint": req.profile_fingerprint})
        budgets = load_budgets(self.settings.budgets_path, req.task_type)
        if budgets.defaulted:
            self._emit(ctx, "STEP", {"name": "budget_defaults", "detail": ",".join(budgets.defaulted)[:200]})
        self.breaker.configure(budgets.failure_threshold, budgets.open_seconds)
        tracker = BudgetTracker(budgets, self.clock)
        ctx.cancel.check()

        if req.runtime == "DEERFLOW" and (not self.settings.deerflow_enabled or self.deerflow is None):
            raise RuntimeFailure("DEERFLOW_DISABLED")

        def on_call(tool: str, outcome: str, ms: int) -> None:
            tracker.add_tool_call()
            self._emit(ctx, "TOOL_CALL", {"tool": tool, "outcome": outcome, "ms": ms})

        self._emit(ctx, "STEP", {"name": "load_context", "detail": req.work_id})
        try:
            raw_view = self.control.load_context(req.work_id, req.run_id, req.mandate_id, on_call)
        except ControlError as exc:
            raise RuntimeFailure("CONTEXT_LOAD_FAILED", exc.reason) from exc
        ctx.cancel.check()
        view = SnapshotView.from_raw(raw_view)
        if not view.work_id:
            raise RuntimeFailure("WORK_NOT_FOUND")
        self._emit(ctx, "CONTEXT_LOADED", {"snapshot_hash": view.digest(), "counts": view.counts()})
        self._emit(ctx, "BUDGET_UPDATE", tracker.snapshot())

        if req.runtime == "STUB":
            self._emit(ctx, "STEP", {"name": "generate", "detail": "deterministic"})
            raw = stub.generate(req.task_type, view)
            self._emit(ctx, "MODEL_USAGE", {"model": "deterministic-stub", "input_tokens": 0, "output_tokens": 0,
                                            "ms": 0, "degraded": False})
        else:
            raw = self._run_deerflow(ctx, view, budgets, tracker)
            if raw is None:
                return
        ctx.cancel.check()

        result = validate_output(raw, view, expected_task_type=req.task_type, max_output_chars=budgets.max_output_chars)
        if not result.ok or result.output is None:
            self._reject(ctx, result.violations)
            return
        digest = hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        self._emit(ctx, "OUTPUT_ACCEPTED", {"items": len(result.output.items), "sha256": digest, "generator": generator})

        proposal = compile_proposal(result.output, req.run_id)
        problems = validate_proposal(proposal)
        if problems:
            self._reject(ctx, [Violation("P", p.split("@")[0].removeprefix("P.")) for p in problems])
            return
        ctx.cancel.check()
        self._emit(ctx, "STEP", {"name": "record_proposal", "detail": f"{len(proposal['changes'])} changes"})
        holder: dict[str, str] = {}
        try:
            wrote = self._write(ctx, lambda: holder.update(id=self.control.create_proposal(
                run_id=req.run_id, mandate_id=req.mandate_id, work_id=req.work_id,
                actor_role=req.actor_role, proposal=proposal)))
        except ControlError as exc:
            raise RuntimeFailure("PROPOSAL_WRITE_FAILED", exc.reason) from exc
        if not wrote:
            return
        executable = sum(1 for c in proposal["changes"] if c.get("draft_payload"))
        self._emit(ctx, "PROPOSAL_RECORDED", {"proposal_id": holder["id"], "changes": len(proposal["changes"]),
                                              "executable": executable, "generator": generator})
        self._emit(ctx, "BUDGET_UPDATE", tracker.snapshot())
        try:
            self._write(ctx, lambda: self.control.set_state(
                req.run_id, "AWAITING_REVIEW", "已记录 DRAFT 提案,等待人工评审"))
        except ControlError as exc:
            raise RuntimeFailure("STATE_WRITE_FAILED", exc.reason) from exc
        ctx.state = "AWAITING_REVIEW"

    def _reject(self, ctx: RunContext, violations: list[Violation]) -> None:
        ctx.state = "FAILED"
        rules = list(dict.fromkeys(v.rule for v in violations))
        codes = list(dict.fromkeys(f"{v.rule}.{v.code}" for v in violations))[:30]
        self._emit(ctx, "OUTPUT_REJECTED", {"rules": rules, "codes": codes, "generator": ctx.request.runtime})
        try:
            self._write(ctx, lambda: self.control.set_state(
                ctx.run_id, "FAILED", f"输出未通过校验:{','.join(rules)}"))
        except ControlError as exc:
            log.error("run %s: FAILED state not recorded (%s)", ctx.run_id, exc.reason)

    def _run_deerflow(self, ctx: RunContext, view: SnapshotView, budgets: Any, tracker: BudgetTracker) -> dict[str, Any] | None:
        req = ctx.request
        assert self.deerflow is not None
        prompt = build_prompt(run_id=req.run_id, mandate_id=req.mandate_id, actor_role=req.actor_role,
                              work_id=req.work_id, task_type=req.task_type,
                              profile_fingerprint=req.profile_fingerprint, instructions=req.instructions, view=view)
        body = mandate_body(prompt, run_id=req.run_id, mandate_id=req.mandate_id, work_id=req.work_id,
                            task_type=req.task_type, profile_fingerprint=req.profile_fingerprint,
                            max_turns=budgets.max_turns)

        def admitted(thread_id: str, runtime_run_id: str) -> None:
            if ctx.silenced:
                return
            try:
                self._write(ctx, lambda: self.control.admit_running(req.run_id, thread_id, runtime_run_id))
            except ControlError as exc:  # correlation is for observability; the run itself can continue
                log.warning("run %s: runtime ids not recorded (%s)", req.run_id, exc.reason)

        hooks = Hooks(event=lambda t, p: self._emit(ctx, t, p), admitted=admitted)
        self._emit(ctx, "STEP", {"name": "deerflow_run", "detail": "submit"})
        text = self.deerflow.execute(run_id=req.run_id, body=body, budgets=budgets, tracker=tracker,
                                     cancel=ctx.cancel, hooks=hooks, poll_interval=self.settings.poll_interval)
        parsed, violations = extract_output(text, budgets.max_output_chars)
        if violations:
            self._reject(ctx, violations)
            return None
        return parsed
