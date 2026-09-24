"""Steer cancel closes in-flight tools so nothing is left half-open."""

from jobcome.adapters.deerflow_harness_client import close_open_tools


def test_close_open_tools_emits_cancelled_results() -> None:
    open_tools = ["jobcome_profile_get", "jobcome_fit_score"]
    events = close_open_tools(open_tools)
    assert open_tools == []
    assert [e["type"] for e in events] == ["tool_result", "tool_result"]
    assert all(e["result"] == "[cancelled]" for e in events)
    assert {e["name"] for e in events} == {"jobcome_profile_get", "jobcome_fit_score"}


def test_close_open_tools_noop_when_empty() -> None:
    assert close_open_tools([]) == []
