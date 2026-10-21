"""Offline transport regressions for slow but active structured model output."""

import asyncio
import json
from unittest.mock import AsyncMock

import litellm
import pytest

from conftest import capture_audit_rows, fake_gateway, install_routing
from jc.llm.transport import router_for


@pytest.mark.asyncio
async def test_buffered_stream_uses_real_litellm_and_keeps_validation_failover(
    monkeypatch, tmp_path
):
    router = install_routing(monkeypatch, tmp_path, "ingest", ["openai/first", "openai/second"])
    with (
        capture_audit_rows() as rows,
        fake_gateway({"first": "bad json", "second": '{"ok":true}'}) as called,
    ):
        result = await router.acompletion(
            "ingest",
            messages=[],
            buffered_stream=True,
            timeout_seconds=1,
            response_validator=lambda r: json.loads(router.content_from_response(r)),
        )
    assert result == {"ok": True}
    assert len(called) == 2
    assert len(rows) == 1
    assert rows[0].status == "success"
    assert rows[0].stream is True
    assert len(rows[0].attempts) == 2
    assert rows[0].attempts[0].validator_failed


def delta(text=None, finish=None):
    return litellm.ModelResponseStream(
        model="slow-model",
        choices=[
            {"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": finish}
        ],
    )


class Stream:
    def __init__(self, chunks, delay=0):
        self.chunks = iter(chunks)
        self.delay = delay
        self.aclose = AsyncMock()

    def __aiter__(self):
        return self

    async def __anext__(self):
        await asyncio.sleep(self.delay)
        try:
            return next(self.chunks)
        except StopIteration:
            raise StopAsyncIteration from None


@pytest.mark.asyncio
async def test_active_generation_can_take_longer_than_read_idle_timeout(monkeypatch, tmp_path):
    router = install_routing(monkeypatch, tmp_path, "ingest", ["openai/first"])
    stream = Stream([delta("{"), delta('"ok"'), delta(":true}"), delta(finish="stop")], 0.015)
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=stream))
    # Each chunk is within 40ms, but total output exceeds 40ms. Unary failed here.
    with capture_audit_rows():
        result = await router.acompletion(
            "ingest",
            messages=[],
            buffered_stream=True,
            timeout_seconds=0.04,
            response_validator=lambda r: json.loads(router.content_from_response(r)),
        )
    assert result == {"ok": True}
    stream.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_stalled_stream_fails_over_once_and_closes(monkeypatch, tmp_path):
    router = install_routing(monkeypatch, tmp_path, "ingest", ["openai/first", "openai/second"])
    stalled = Stream([delta("never")], 0.2)
    good = Stream([delta('{"ok":true}'), delta(finish="stop")])
    call = AsyncMock(side_effect=[stalled, good])
    monkeypatch.setattr(litellm, "acompletion", call)
    with capture_audit_rows() as rows:
        result = await router.acompletion(
            "ingest",
            messages=[],
            buffered_stream=True,
            timeout_seconds=0.01,
            response_validator=lambda r: json.loads(router.content_from_response(r)),
        )
    assert result == {"ok": True}
    assert [c.kwargs["model"] for c in call.await_args_list] == ["openai/first", "openai/second"]
    assert all(c.kwargs["num_retries"] == 0 for c in call.await_args_list)
    assert rows[0].attempts[0].error_code == "timeout"
    stalled.aclose.assert_awaited_once()
    good.aclose.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("finish", [None, "length", "content_filter"])
async def test_incomplete_response_is_never_accepted(monkeypatch, tmp_path, finish):
    from jc.llm.buffered_stream import IncompleteStructuredStream

    router = install_routing(monkeypatch, tmp_path, "ingest", ["openai/first"])
    stream = Stream([delta('{"ok":true}'), delta(finish=finish)])
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=stream))
    validator = AsyncMock()
    with capture_audit_rows(), pytest.raises(IncompleteStructuredStream):
        await router.acompletion(
            "ingest", messages=[], buffered_stream=True, response_validator=validator
        )
    validator.assert_not_called()
    stream.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_total_deadline_cancels_without_starting_another_model(monkeypatch, tmp_path):
    router = install_routing(monkeypatch, tmp_path, "ingest", ["openai/first", "openai/second"])
    stream = Stream([delta("not yet")], 0.5)
    call = AsyncMock(return_value=stream)
    monkeypatch.setattr(litellm, "acompletion", call)
    with capture_audit_rows(), pytest.raises(TimeoutError):
        async with asyncio.timeout(0.01):
            await router.acompletion("ingest", messages=[], buffered_stream=True, timeout_seconds=1)
    call.assert_awaited_once()
    stream.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_all_endpoint_timeouts_are_audited_once_and_not_hidden(monkeypatch, tmp_path):
    router = install_routing(
        monkeypatch, tmp_path, "ingest", ["openai/first", "openai/second", "openai/third"]
    )
    call = AsyncMock(side_effect=TimeoutError())
    monkeypatch.setattr(litellm, "acompletion", call)
    with capture_audit_rows() as rows, pytest.raises(TimeoutError):
        await router.acompletion("ingest", messages=[], buffered_stream=True, timeout_seconds=0.01)
    assert call.await_count == 3
    assert len(rows) == 1
    assert rows[0].status == "failed"
    assert [a.error_code for a in rows[0].attempts] == ["timeout"] * 3


@pytest.mark.asyncio
async def test_partial_json_is_discarded_before_next_model(monkeypatch, tmp_path):
    router = install_routing(monkeypatch, tmp_path, "ingest", ["openai/first", "openai/second"])
    partial = Stream([delta('{"not_saved":')])
    good = Stream([delta('{"ok":true}'), delta(finish="stop")])
    call = AsyncMock(side_effect=[partial, good])
    monkeypatch.setattr(litellm, "acompletion", call)
    with capture_audit_rows():
        result = await router.acompletion(
            "ingest",
            messages=[],
            buffered_stream=True,
            response_validator=lambda r: json.loads(router.content_from_response(r)),
        )
    assert result == {"ok": True}
    partial.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_continuously_active_stream_cannot_starve_fallback(monkeypatch, tmp_path):
    router = install_routing(monkeypatch, tmp_path, "ingest", ["openai/first", "openai/second"])
    # Every chunk meets the idle timeout, but the whole attempt must be bounded.
    active = Stream([delta(" ")] * 100, 0.005)
    good = Stream([delta('{"ok":true}'), delta(finish="stop")])
    call = AsyncMock(side_effect=[active, good])
    monkeypatch.setattr(litellm, "acompletion", call)
    with capture_audit_rows():
        result = await router.acompletion(
            "ingest", messages=[], buffered_stream=True,
            timeout_seconds=0.1, stream_attempt_timeout_seconds=0.03,
            response_validator=lambda r: json.loads(router.content_from_response(r)),
        )
    assert result == {"ok": True}
    assert call.await_count == 2
    assert "stream_attempt_timeout_seconds" not in call.await_args.kwargs
    active.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_structured_stream_has_one_fallback_owner_even_before_content(monkeypatch, tmp_path):
    from litellm.exceptions import MidStreamFallbackError

    router = install_routing(monkeypatch, tmp_path, "ingest", ["openai/first", "openai/second"])

    class Overloaded(Stream):
        async def __anext__(self):
            raise MidStreamFallbackError(
                message="overloaded", model="first", llm_provider="openai",
                original_exception=ConnectionError("overloaded"), is_pre_first_chunk=True,
            )

    broken = Overloaded([])
    good = Stream([delta('{"ok":true}'), delta(finish="stop")])
    call = AsyncMock(side_effect=[broken, good])
    monkeypatch.setattr(litellm, "acompletion", call)
    nested = AsyncMock(side_effect=AssertionError("Router must not own structured-stream fallback"))
    monkeypatch.setattr(router_for("ingest").router, "acompletion", nested)
    with capture_audit_rows() as rows:
        result = await router.acompletion(
            "ingest", messages=[], buffered_stream=True,
            response_validator=lambda r: json.loads(router.content_from_response(r)),
        )
    assert result == {"ok": True}
    nested.assert_not_called()
    assert [c.kwargs["model"] for c in call.await_args_list] == ["openai/first", "openai/second"]
    assert all(c.kwargs["num_retries"] == 0 for c in call.await_args_list)
    assert len(rows[0].attempts) == 2
    broken.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_normal_agent_stream_is_not_gated_by_structured_only_variables(monkeypatch, tmp_path):
    router = install_routing(monkeypatch, tmp_path, "coach", ["openai/only"])
    stream = Stream([delta("hello"), delta(finish="stop")])
    monkeypatch.setattr(router_for("coach").router, "acompletion", AsyncMock(return_value=stream))
    with capture_audit_rows():
        opened = await router.astream_completion("coach", messages=[])
    assert opened is stream
