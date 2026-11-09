"""The checklist reads tool events. The server-driven flow asks through the ledger, not the tools,
so its events come from the ledger (ADR-007). An interview that called the tools is not doubled."""

from __future__ import annotations

from types import SimpleNamespace

from jc.coach.recording import ledger_tool_events


def _session(asked, status="completed", ended_reason="completed"):
    return SimpleNamespace(status=status, coverage={"asked": asked, "ended_reason": ended_reason})


def test_each_question_is_placed_before_the_message_that_asks_it():
    events = [
        {"role": "interviewer", "text": "你好，做个自我介绍吧。"},
        {"role": "candidate", "text": "我叫张三"},
        {"role": "interviewer", "text": "好，谢谢。讲讲你用 Python 做过的事？"},
        {"role": "candidate", "text": "我写过对账脚本"},
    ]
    session = _session([{"question_id": "q1", "kind": "main"}], status="active")
    merged = ledger_tool_events(session, events, {"q1": "讲讲你用 Python 做过的事？"})
    tools = [i for i, e in enumerate(merged) if e.get("tool") == "jc_mock_ask"]
    assert len(tools) == 1
    assert merged[tools[0] + 1]["text"].startswith("好，谢谢")
    assert merged[tools[0]]["arguments"] == {"kind": "main", "stem": "讲讲你用 Python 做过的事？",
                                             "question_id": "q1"}


def test_a_completed_interview_gets_its_end_event():
    session = _session([{"question_id": "q1", "kind": "main"}], status="completed")
    merged = ledger_tool_events(session, [], {"q1": "x"})
    assert merged[-1] == {"role": "tool", "tool": "jc_mock_end", "accepted": True,
                          "arguments": {"reason": "completed"}}


def test_an_interview_that_called_the_tools_is_not_doubled():
    events = [{"role": "tool", "tool": "jc_mock_ask", "arguments": {"stem": "x"}, "accepted": True}]
    session = _session([{"question_id": "q1", "kind": "main"}])
    assert ledger_tool_events(session, events, {"q1": "x"}) == events
