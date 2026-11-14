"""Audit queue: drop under pressure, flush on shutdown, respect the feature flag."""

from __future__ import annotations

import asyncio
import logging
import time

import pytest

from jc.llm import call_log
from jc.llm.call_log import CallRecord, LLMLogContext, submit_call


def _record(i: int = 0) -> CallRecord:
    return CallRecord(
        scenario="probe",
        context=LLMLogContext(caller="test", user_id="u1"),
        status="ok",
        final_model=f"m{i}",
    )


@pytest.fixture(autouse=True)
async def _reset_queue(monkeypatch: pytest.MonkeyPatch):
    """Each test gets a fresh queue and no background drain unless started."""
    call_log._audit_queue = None
    call_log._audit_worker = None
    call_log._dropped = 0
    monkeypatch.setattr(call_log.settings, "jc_llm_log_enabled", True)
    monkeypatch.setattr(call_log.settings, "jc_llm_log_queue_max", 8)
    yield
    # Stop any worker we started.
    if call_log._audit_worker is not None:
        call_log._audit_worker.cancel()
        try:
            await call_log._audit_worker
        except (asyncio.CancelledError, Exception):
            pass
    call_log._audit_queue = None
    call_log._audit_worker = None
    call_log._dropped = 0


def test_submit_when_full_does_not_raise_or_block(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(call_log.settings, "jc_llm_log_queue_max", 3)
    for i in range(3):
        submit_call(_record(i))
    t0 = time.perf_counter()
    submit_call(_record(99))  # 4th → full
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.05  # must not block
    assert call_log._dropped == 1
    assert call_log._queue().qsize() == 3


def test_drop_warns_every_hundred(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture):
    monkeypatch.setattr(call_log.settings, "jc_llm_log_queue_max", 1)
    submit_call(_record(0))  # fills
    with caplog.at_level(logging.WARNING, logger="jc.llm.call_log"):
        for i in range(1, 201):
            submit_call(_record(i))
    warnings = [r for r in caplog.records if "dropped" in r.getMessage().lower() or "queue full" in r.getMessage().lower()]
    # _dropped becomes 1..200; warning when _dropped % 100 == 1 → at 1 and 101
    assert len(warnings) == 2
    assert call_log._dropped == 200


def test_disabled_skips_enqueue(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(call_log.settings, "jc_llm_log_enabled", False)
    submit_call(_record())
    assert call_log._audit_queue is None


@pytest.mark.asyncio
async def test_stop_waits_for_queue_drain(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(call_log.settings, "jc_llm_log_queue_max", 50)
    written: list[str] = []

    async def _fake_record(record: CallRecord) -> None:
        await asyncio.sleep(0.01)
        written.append(record.final_model or "")

    monkeypatch.setattr(call_log, "record_call", _fake_record)
    await call_log.start_audit_writer()
    for i in range(5):
        submit_call(_record(i))
    await call_log.stop_audit_writer()
    assert len(written) == 5
    assert call_log._queue().qsize() == 0
