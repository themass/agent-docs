"""Turning a stored interview into what the acceptance checklist reads.

The checklist (`jc.coach.acceptance`) takes a list of events. Until now they were written by
hand, so nothing showed that a real session could be turned into them. These tests build the
rows the server really writes (the wrapped user message from `wrap_coach_mock_message`, tool
calls and their results as JSON strings, the interviewer's closing text) and check what comes
out."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.agent.coach_task import wrap_coach_mock_message
from jc.coach.acceptance import check_interviewer, check_reviewer, failures
from jc.coach.recording import (
    events_from_trace,
    record_interview,
    render_findings,
    unwrap_candidate_text,
)
from jc.db.base import Base
from jc.models.agent import AgentSession
from jc.models.agent_trace import AgentTrace
from jc.models.interview import AnswerAttempt, InterviewQuestion, MockSession
from jc.models.job import Job
from jc.models.profile import Profile
from jc.models.user import User

INTRO = "我做了五年产品，主要负责结算和对账。"
ANSWER = "我们有两个需求，对账每个月让财务多花三天，另一个是新报表，我选了对账。"
FOLLOW_ANSWER = "看的是每月多花的三天，和财务负责人一起算过。"


def wrapped(text, **kwargs):
    return wrap_coach_mock_message(
        text, profile_id="p1", job_id="j1", mock_session_id="ms1", drawn_stems=[], **kwargs)


# --- the candidate's own words -------------------------------------------


def test_the_wrapped_message_gives_back_exactly_what_the_candidate_said():
    for said in (INTRO, "好的。", "第一行\n第二行", "我说过“用户原话：”这几个字"):
        assert unwrap_candidate_text(wrapped(said, level="mid")) == said


def test_a_candidate_who_types_the_marker_on_a_line_of_their_own_is_still_returned_whole():
    said = "我回答如下：\n用户原话：\n这是我真正想说的"
    assert unwrap_candidate_text(wrapped(said)) == said


def test_a_message_that_was_never_wrapped_is_returned_as_it_is():
    assert unwrap_candidate_text("你好") == "你好"


# --- the events ---------------------------------------------------------


def row(seq, event_type, payload, role="assistant"):
    return AgentTrace(id=f"t{seq}", session_id="as1", seq=seq, event_type=event_type, role=role,
                      payload=payload, mock_session_id="ms1")


def tool(seq, name, arguments, result):
    return [row(seq, "tool_call", {"name": name, "arguments": arguments}),
            row(seq + 1, "tool_result", {"name": name, "result": json.dumps(result)}, role="tool")]


def trace_rows():
    rows = [
        row(0, "system_prompt", {"text": "..."}, role="system"),
        row(1, "user_message", {"text": wrapped("你好，我准备好了，可以开始面试了。")},
            role="user"),
        row(2, "reasoning", {"text": "先问候"}),
        row(3, "assistant_message", {"text": "你好，我是示例科技产品岗位的面试官，今天由我来面。"
                                              "先请你做个一两分钟的自我介绍吧。"}),
        row(4, "user_message", {"text": wrapped(INTRO)}, role="user"),
    ]
    rows += tool(5, "jc_mock_plan", {"mock_session_id": "ms1"}, {"stage": "opening"})
    first = "你说主要负责结算，讲一个判断过优先级的需求"
    rows += tool(7, "jc_mock_ask", {"mock_session_id": "ms1", "stem": first},
                 {"accepted": True, "question_id": "q1", "label": "第 1 题"})
    rows += [row(9, "assistant_message", {"text": first + "？"}),
             row(10, "user_message", {"text": wrapped(ANSWER)}, role="user")]
    follow_up = "你说对账每个月让财务多花三天，拿什么判断它更该先做"
    rows += tool(11, "jc_mock_ask",
                 {"mock_session_id": "ms1", "kind": "followup", "parent_question_id": "q1",
                  "stem": follow_up},
                 {"accepted": True, "question_id": "q2", "label": "第 1 题 · 追问 1"})
    rows += [row(13, "assistant_message", {"text": follow_up + "？"}),
             row(14, "user_message", {"text": wrapped(FOLLOW_ANSWER)}, role="user")]
    rows += tool(15, "jc_mock_ask", {"mock_session_id": "ms1", "stem": "讲一个失败的项目"},
                 {"accepted": False, "code": "main_limit", "reason": "主问题已达 1 个"})
    rows += tool(17, "jc_mock_open_qa", {"mock_session_id": "ms1"}, {"accepted": True})
    rows += [row(19, "assistant_message", {"text": "好，我这边问完了。你有什么想问我的吗？"}),
             row(20, "user_message", {"text": wrapped("团队有多少人？")}, role="user"),
             row(21, "assistant_message", {"text": "这个我需要和团队确认。"})]
    rows += tool(22, "jc_mock_end", {"mock_session_id": "ms1", "reason": "completed"},
                 {"accepted": True, "ended_early": False})
    rows += [row(24, "assistant_message", {"text": "面试结束了，报告会由独立评审生成。"})]
    return rows


def test_only_what_the_checklist_reads_is_kept_and_in_order():
    events, warnings = events_from_trace(trace_rows())
    kinds = [(e["role"], e.get("tool")) for e in events]
    assert kinds[:3] == [("candidate", None), ("interviewer", None), ("candidate", None)]
    assert ("tool", "jc_mock_plan") in kinds and ("tool", "jc_mock_end") in kinds
    # system prompts and reasoning are not part of what was said.
    assert all(e["role"] in ("candidate", "interviewer", "tool") for e in events)
    assert warnings == []


def test_the_candidates_text_is_the_candidates_not_the_wrapper():
    events, _ = events_from_trace(trace_rows())
    spoken = [e["text"] for e in events if e["role"] == "candidate"]
    assert spoken[:2] == ["你好，我准备好了，可以开始面试了。", INTRO]
    assert all("【面试模拟任务】" not in text for text in spoken)


def test_a_tool_call_and_its_result_become_one_event_with_the_verdict():
    events, _ = events_from_trace(trace_rows())
    asks = [e for e in events if e.get("tool") == "jc_mock_ask"]
    assert [e["accepted"] for e in asks] == [True, True, False]
    assert asks[2]["code"] == "main_limit"
    assert asks[1]["arguments"]["kind"] == "followup"
    assert "mock_session_id" not in asks[0]["arguments"]


def test_a_tool_call_with_no_result_is_kept_and_warned_about():
    rows = [r for r in trace_rows() if not (r.event_type == "tool_result" and r.seq == 8)]
    events, warnings = events_from_trace(rows)
    ask = [e for e in events if e.get("tool") == "jc_mock_ask"][0]
    assert ask["accepted"] is True
    assert any("jc_mock_ask" in w and "没有结果" in w for w in warnings)


def test_a_result_is_never_paired_with_a_call_that_came_after_it():
    # Two registrations; the second was refused. The first call's result is gone, so the refusal
    # must stay with the second call and not be handed to the first.
    rows = [r for r in trace_rows() if r.seq != 8]
    events, warnings = events_from_trace(rows)
    asks = [e for e in events if e.get("tool") == "jc_mock_ask"]
    assert [e["accepted"] for e in asks] == [True, True, False]
    assert asks[2]["code"] == "main_limit"
    assert len(warnings) == 1 and "jc_mock_ask" in warnings[0]


def test_a_result_with_no_call_before_it_is_ignored_and_warned_about():
    orphan = row(40, "tool_result", {"name": "jc_mock_end", "result": "{}"}, role="tool")
    rows = trace_rows() + [orphan]
    events, warnings = events_from_trace(rows)
    assert [e["accepted"] for e in events if e.get("tool") == "jc_mock_end"] == [True]
    assert any("jc_mock_end" in w and "找不到对应的调用" in w for w in warnings)


def test_two_calls_of_one_tool_in_flight_at_once_cannot_be_told_apart_and_this_is_known():
    # The ledger keeps no call id. With both calls open the result goes to the later one. This pins
    # the documented limit so a change to it is a decision, not an accident.
    rows = [
        row(0, "tool_call", {"name": "jc_mock_ask", "arguments": {"stem": "第一问"}}),
        row(1, "tool_call", {"name": "jc_mock_ask", "arguments": {"stem": "第二问"}}),
        row(2, "tool_result", {"name": "jc_mock_ask", "result": json.dumps({"accepted": False})},
            role="tool"),
    ]
    events, warnings = events_from_trace(rows)
    assert [e["accepted"] for e in events] == [True, False]
    assert len(warnings) == 1 and "没有结果" in warnings[0]


def test_a_result_that_is_not_json_is_kept_and_warned_about_not_guessed_at():
    rows = trace_rows()
    for r in rows:
        if r.event_type == "tool_result" and r.seq == 8:
            r.payload = {"name": "jc_mock_ask", "result": "Error: 超时"}
    events, warnings = events_from_trace(rows)
    ask = [e for e in events if e.get("tool") == "jc_mock_ask"][0]
    assert ask["accepted"] is True
    assert any("读不出" in w and "jc_mock_ask" in w for w in warnings)


def test_a_result_wrapped_in_content_blocks_is_read_too():
    rows = trace_rows()
    for r in rows:
        if r.event_type == "tool_result" and r.seq == 16:
            r.payload = {"name": "jc_mock_ask", "result": json.dumps(
                [{"type": "text", "text": json.dumps({"accepted": False, "code": "too_similar"})}])}
    events, warnings = events_from_trace(rows)
    refused = [e for e in events if e.get("tool") == "jc_mock_ask"][2]
    assert refused["accepted"] is False and refused["code"] == "too_similar"
    assert warnings == []


# --- a whole stored interview ---------------------------------------------------------------------


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/recording.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    makers = async_sessionmaker(engine, expire_on_commit=False)
    async with makers() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(Profile(id="p1", user_id="u1", owner_kind="user", version=1, payload={}))
        db.add(Job(id="j1", profile_id="p1", company="示例科技", title="产品经理", raw_text="岗位",
                   tag="warmup", fit_gaps=[], fit_blockers=[], status="active",
                   requirements={"must_have_skills": []}))
        db.add(AgentSession(id="as1", user_id="u1", profile_id="p1", role_id="coach-mock",
                            deerflow_thread_id="th"))
        for qid, stem in (("q1", "你说主要负责结算，讲一个判断过优先级的需求"),
                          ("q2", "你说对账每个月让财务多花三天，拿什么判断它更该先做"),
                          ("q3", "讲一个失败的项目")):
            db.add(InterviewQuestion(id=qid, profile_id="p1", stem=stem,
                                     question_type="behavioral"))
        db.add(AnswerAttempt(id="a1", question_id="q1", profile_id="p1", mock_session_id="ms1",
                             user_answer=ANSWER, coach_feedback={}, reference_answer=None))
        db.add(AnswerAttempt(id="a2", question_id="q2", profile_id="p1", mock_session_id="ms1",
                             user_answer=FOLLOW_ANSWER, coach_feedback={}, reference_answer=None))
        db.add(MockSession(
            id="ms1", profile_id="p1", user_id="u1", mode="target", job_id="j1",
            question_ids=["q1", "q2", "q3"], bank_draw_count=0, generated_count=0,
            status="completed", started_at=datetime(2026, 11, 5, tzinfo=UTC),
            completed_at=datetime(2026, 11, 5, 1, tzinfo=UTC), style="standard", level="mid",
            quota_counted=True, report_status="ready",
            coverage={"asked": [
                {"question_id": "q1", "kind": "main", "parent_question_id": None},
                {"question_id": "q2", "kind": "followup", "parent_question_id": "q1"},
                {"question_id": "q3", "kind": "main", "parent_question_id": None, "skipped": True},
            ], "ended_reason": "completed", "ended_early": False},
            report={"questions": [
                {"question_id": "q1", "scores": {"depth": 6},
                 "evidence": {"depth": "对账每个月让财务多花三天"}},
                {"question_id": "q3", "scores": {}, "evidence": {}}],
                "summary": {"verdict": "判断有依据。", "strengths": [
                    {"text": "优先级有依据", "quote": "对账每个月让财务多花三天"}],
                    "priorities": [{"text": "补结果", "quote": None}]}},
        ))
        for r in trace_rows():
            db.add(r)
        await db.commit()
    yield makers
    await engine.dispose()


@pytest.mark.asyncio
async def test_a_stored_interview_comes_out_with_everything_the_checklist_needs(maker):
    async with maker() as db:
        recorded = await record_interview(db, "ms1")
    assert set(recorded) >= {"events", "role_family", "answers", "skipped", "control_messages",
                             "report", "warnings", "session"}
    assert recorded["role_family"] == "pm"
    assert recorded["skipped"] == ["q3"]
    # A main question's answer holds its follow-up's answer too, as the report is checked against.
    assert FOLLOW_ANSWER in recorded["answers"]["q1"] and ANSWER in recorded["answers"]["q1"]
    assert recorded["session"]["level"] == "mid" and recorded["session"]["job"] == "产品经理"
    assert recorded["control_messages"] == []


@pytest.mark.asyncio
async def test_what_the_candidate_said_only_to_steer_the_interview_is_listed_apart(maker):
    async with maker() as db:
        db.add(row(30, "user_message", {"text": wrapped("下一题")}, role="user"))
        await db.commit()
    async with maker() as db:
        recorded = await record_interview(db, "ms1")
    assert recorded["control_messages"] == ["下一题"]


@pytest.mark.asyncio
async def test_the_recording_is_plain_json_so_it_can_be_saved_and_checked_later(maker):
    async with maker() as db:
        recorded = await record_interview(db, "ms1")
    again = json.loads(json.dumps(recorded, ensure_ascii=False))
    assert again == recorded


@pytest.mark.asyncio
async def test_the_checklist_runs_on_a_stored_interview_and_says_what_it_found(maker):
    async with maker() as db:
        recorded = await record_interview(db, "ms1")
    interviewer = check_interviewer(recorded["events"], role_family=recorded["role_family"])
    reviewer = check_reviewer(recorded["report"], answers=recorded["answers"],
                              skipped=set(recorded["skipped"]),
                              control_messages=recorded["control_messages"])
    assert failures(interviewer) == [] and failures(reviewer) == []
    text = render_findings(interviewer, reviewer)
    assert "通过" in text and "需要人来读" in text and "stays_in_the_role" in text


@pytest.mark.asyncio
async def test_a_failure_is_shown_with_its_detail_and_makes_the_run_fail(maker):
    async with maker() as db:
        recorded = await record_interview(db, "ms1")
    events = list(recorded["events"])
    events.insert(2, {"role": "interviewer", "text": "很好，回答得不错。"})
    interviewer = check_interviewer(events, role_family=recorded["role_family"])
    text = render_findings(interviewer, [])
    assert "未通过" in text and "does_not_evaluate" in text and "很好" in text


@pytest.mark.asyncio
async def test_a_session_without_a_trace_says_so_instead_of_checking_nothing(maker):
    async with maker() as db:
        db.add(MockSession(
            id="ms_empty", profile_id="p1", user_id="u1", mode="target", question_ids=[],
            bank_draw_count=0, generated_count=0, status="completed",
            started_at=datetime(2026, 11, 5, tzinfo=UTC), coverage={"asked": []}))
        await db.commit()
    async with maker() as db:
        recorded = await record_interview(db, "ms_empty")
    assert recorded["events"] == []
    assert any("没有对话记录" in w for w in recorded["warnings"])


@pytest.mark.asyncio
async def test_an_unknown_session_is_an_error_not_an_empty_recording(maker):
    async with maker() as db:
        with pytest.raises(LookupError):
            await record_interview(db, "nope")
