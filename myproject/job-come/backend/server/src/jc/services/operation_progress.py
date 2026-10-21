"""Request-owned progress streams with real stages and cancellation-safe teardown."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextvars import ContextVar
from typing import Any

import anyio

from jc.exceptions import AppError

_sink: ContextVar[Callable[[dict[str, Any]], None] | None] = ContextVar("operation_progress", default=None)


def report(stage: str, *, done: bool = False, message: str | None = None, status: str | None = None) -> None:
    sink = _sink.get()
    if sink:
        sink({"type": "progress", "stage": stage, "status": status or ("done" if done else "running"), "message": message})


async def stream_operation(run: Callable[[], Awaitable[Any]], profile_id: str, *,
                           rollback_db: Callable[[], Awaitable[None]], operation: str,
                           label: str, log: logging.Logger,
                           timeout_seconds: float, heartbeat_seconds: float = 10) -> AsyncIterator[bytes]:
    """Own/cancel the generation task; persist no process-local job state.

    The same request owns the service's DB session. On disconnect the producer is
    cancelled and awaited before dependency cleanup may close that session.
    """
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    run_id = uuid.uuid4().hex[:12]
    started = time.monotonic()
    last_stage = "starting"
    terminal = False

    def record(event: str, *, stage: str = "", status: str = "") -> None:
        # No profile payload, prompt, generated text or free-form event message.
        log.info(
            "%s_lifecycle event=%s run_id=%s profile_id=%s stage=%s status=%s elapsed_ms=%d",
            operation, event, run_id, profile_id, stage, status, int((time.monotonic() - started) * 1000),
        )

    record("started")

    async def rollback() -> None:
        try:
            # A dead MySQL connection can also hang during rollback. Bound cleanup
            # independently so it cannot swallow the terminal timeout SSE event.
            async with asyncio.timeout(5):
                await rollback_db()
        except Exception:
            # Broken connection cleanup must not suppress the terminal error,
            # otherwise the client would receive heartbeats forever.
            log.warning("%s rollback failed profile=%s", operation, profile_id, exc_info=True)

    async def produce() -> None:
        token = _sink.set(queue.put_nowait)
        try:
            async with asyncio.timeout(timeout_seconds):
                result = await run()
            queue.put_nowait({"type": "result", "data": result.model_dump(mode="json") if hasattr(result, "model_dump") else result})
        except TimeoutError:
            await rollback()
            log.warning("%s deadline exceeded profile=%s budget=%s", operation, profile_id, timeout_seconds)
            queue.put_nowait({"type": "error", "code": f"{operation}_timeout",
                              "message": f"{label}超时，已停止本次任务。请重试；已保存的档案不会丢失。"})
        except AppError as exc:
            await rollback()
            queue.put_nowait({"type": "error", "code": exc.code, "message": exc.message})
        except Exception:
            await rollback()
            log.exception("%s failed profile=%s", operation, profile_id)
            queue.put_nowait({"type": "error", "code": f"{operation}_failed",
                              "message": f"{label}失败，档案仍已保存。请重试；若持续失败，请联系管理员查看服务日志。"})
        finally:
            _sink.reset(token)

    task = asyncio.create_task(produce())
    try:
        yield b": connected\n\n"
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), heartbeat_seconds)
            except TimeoutError:
                record("waiting", stage=last_stage)
                yield b": heartbeat\n\n"
                continue
            if event["type"] == "progress":
                last_stage = event["stage"]
                record("stage", stage=last_stage, status=event["status"])
            elif event["type"] in {"result", "error"}:
                terminal = True
                record("finished", stage=last_stage,
                       status="success" if event["type"] == "result" else event.get("code", "error"))
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode()
            if event["type"] in {"result", "error"}:
                break
    finally:
        if not terminal:
            record("disconnected", stage=last_stage)
        # Starlette disconnect uses level cancellation: every unshielded await
        # can be cancelled again, including the DB driver's cleanup. Do not let
        # dependency teardown close the session until its producer has stopped.
        with anyio.CancelScope(shield=True):
            if not task.done():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
