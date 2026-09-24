"""LLM stream accumulator tests."""

from __future__ import annotations

from jobcome.agent.llm_stream import accumulate_tool_delta, tool_calls_from_accumulator


class _Fn:
    def __init__(self, name: str | None = None, arguments: str | None = None) -> None:
        self.name = name
        self.arguments = arguments


class _TC:
    def __init__(self, index: int, id: str | None = None, function: _Fn | None = None) -> None:
        self.index = index
        self.id = id
        self.function = function


def test_tool_call_accumulator() -> None:
    acc: dict[int, dict[str, str]] = {}
    accumulate_tool_delta(
        acc,
        [
            _TC(0, id="c1", function=_Fn(name="jobcome_profile_get", arguments='{"')),
            _TC(0, function=_Fn(arguments='profile_id":"p1"}')),
        ],
    )
    calls = tool_calls_from_accumulator(acc)
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "jobcome_profile_get"
