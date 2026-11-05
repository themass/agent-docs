"""The command that runs the real-model checklist on a recorded or a stored interview.

    python -m jc.coach.acceptance_run --file recording.json
    python -m jc.coach.acceptance_run --session <mock_session_id>
    python -m jc.coach.acceptance_run --session <id> --save recording.json

It exits non-zero when a rule fails, so it can sit in a script; rules that need a person to read the
interview are listed but never fail the run."""

from __future__ import annotations

import json

import pytest

from jc.coach import acceptance_run
from jc.coach.acceptance_run import main, run_on_recording

GOOD = {
    "session": {"id": "ms1", "style": "standard", "level": "mid", "job": "产品经理",
                "status": "completed", "report_status": "ready", "ended_reason": "completed"},
    "role_family": "pm",
    "events": [
        {"role": "interviewer", "text": "你好，我是示例科技产品岗位的面试官，今天由我来面。"
                                          "先请你做个一两分钟的自我介绍吧。"},
        {"role": "candidate", "text": "我做了五年产品。"},
        {"role": "tool", "tool": "jc_mock_open_qa", "arguments": {}, "accepted": True},
        {"role": "interviewer", "text": "好，我这边问完了。你有什么想问我的吗？"},
        {"role": "tool", "tool": "jc_mock_end", "arguments": {"reason": "completed"},
         "accepted": True},
    ],
    "answers": {"q1": "我们有两个需求，对账每个月让财务多花三天。"},
    "skipped": [],
    "control_messages": [],
    "report": {"questions": [{"question_id": "q1", "scores": {"depth": 6},
                              "evidence": {"depth": "对账每个月让财务多花三天"}}],
               "summary": {"verdict": "判断有依据。", "strengths": [
                   {"text": "优先级有依据", "quote": "对账每个月让财务多花三天"}],
                   "priorities": [{"text": "补结果", "quote": None}]}},
    "warnings": [],
}


def test_a_good_recording_passes_and_says_what_is_left_for_a_person():
    ok, text = run_on_recording(GOOD)
    assert ok is True
    assert "未通过" not in text and "通过（" in text and "需要人来读" in text


def test_a_failing_rule_fails_the_run_and_is_named():
    bad = json.loads(json.dumps(GOOD))
    bad["events"].insert(2, {"role": "interviewer", "text": "很好，回答得不错。"})
    ok, text = run_on_recording(bad)
    assert ok is False and "does_not_evaluate" in text


def test_warnings_from_the_recording_are_shown_first_and_do_not_fail_the_run():
    warned = dict(GOOD, warnings=["jc_mock_ask 的结果读不出来，按“已通过”处理：Error"])
    ok, text = run_on_recording(warned)
    assert ok is True
    assert text.index("读取记录时") < text.index("通过（")
    assert "jc_mock_ask 的结果读不出来" in text


def test_a_recording_with_no_events_is_not_a_pass():
    ok, text = run_on_recording(dict(GOOD, events=[], warnings=["没有对话记录"]))
    assert ok is False and "没有可检查的对话" in text


def test_the_report_part_is_skipped_with_a_note_when_there_is_no_report_yet():
    ok, text = run_on_recording(dict(GOOD, report=None))
    assert ok is True and "还没有报告" in text


def test_main_checks_a_saved_file_and_exits_zero_when_it_passes(tmp_path, capsys):
    path = tmp_path / "rec.json"
    path.write_text(json.dumps(GOOD, ensure_ascii=False), encoding="utf-8")
    assert main(["--file", str(path)]) == 0
    assert "通过（" in capsys.readouterr().out


def test_main_exits_non_zero_when_a_rule_fails(tmp_path, capsys):
    bad = json.loads(json.dumps(GOOD))
    bad["events"].insert(2, {"role": "interviewer", "text": "很好。"})
    path = tmp_path / "rec.json"
    path.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    assert main(["--file", str(path)]) == 1


def test_main_says_so_when_the_file_is_not_a_recording(tmp_path, capsys):
    path = tmp_path / "rec.json"
    path.write_text("{}", encoding="utf-8")
    assert main(["--file", str(path)]) == 2
    assert "不是一份面试记录" in capsys.readouterr().err


def test_main_says_so_when_the_file_is_missing(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.json")]) == 2
    assert "读不到文件" in capsys.readouterr().err


def test_main_needs_one_source(capsys):
    with pytest.raises(SystemExit):
        main([])
    with pytest.raises(SystemExit):
        main(["--file", "a.json", "--session", "ms1"])


def test_the_module_can_be_run_as_a_command():
    assert callable(getattr(acceptance_run, "main"))


# --- the database path, end to end ----------------------------------------


def test_a_stored_interview_is_read_saved_and_checked_again_from_the_file(tmp_path, monkeypatch):
    import asyncio
    from datetime import UTC, datetime

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import jc.models  # noqa: F401
    from jc.coach.recording import record_interview
    from jc.db.base import Base
    from jc.models.agent import AgentSession
    from jc.models.agent_trace import AgentTrace
    from jc.models.interview import MockSession
    from jc.models.profile import Profile
    from jc.models.user import User

    url = f"sqlite+aiosqlite:///{tmp_path}/cli.sqlite"

    async def prepare():
        engine = create_async_engine(url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as db:
            db.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
            await db.flush()
            db.add(Profile(id="p1", user_id="u1", owner_kind="user", version=1, payload={}))
            db.add(AgentSession(id="as1", user_id="u1", profile_id="p1", role_id="coach-mock",
                                deerflow_thread_id="th"))
            db.add(MockSession(
                id="ms1", profile_id="p1", user_id="u1", mode="target", question_ids=[],
                bank_draw_count=0, generated_count=0, status="active",
                started_at=datetime(2026, 11, 5, tzinfo=UTC), style="standard", level="mid",
                coverage={"asked": []}))
            db.add(AgentTrace(id="t1", session_id="as1", seq=1, event_type="assistant_message",
                              role="assistant", mock_session_id="ms1", payload={
                                  "text": "你好，我是示例科技的面试官，先请你做个自我介绍吧。"}))
            await db.commit()
        await engine.dispose()

    asyncio.run(prepare())

    async def recorded(session_id):
        engine = create_async_engine(url)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as db:
                return await record_interview(db, session_id)
        finally:
            await engine.dispose()

    monkeypatch.setattr(acceptance_run, "_record", recorded)
    saved = tmp_path / "saved.json"
    first = main(["--session", "ms1", "--save", str(saved)])
    data = json.loads(saved.read_text(encoding="utf-8"))
    assert data["events"][0]["role"] == "interviewer" and data["session"]["id"] == "ms1"
    # The saved file is checked on its own, with no database, and gives the same answer.
    assert main(["--file", str(saved)]) == first


def test_an_unknown_session_exits_with_two_and_says_which(monkeypatch, capsys):
    async def missing(session_id):
        raise LookupError(f"没有这场面试：{session_id}")

    monkeypatch.setattr(acceptance_run, "_record", missing)
    assert main(["--session", "nope"]) == 2
    assert "没有这场面试：nope" in capsys.readouterr().err


def test_a_report_with_a_fault_fails_the_run_even_when_the_interview_was_fine():
    bad = json.loads(json.dumps(GOOD))
    bad["report"]["questions"][0]["evidence"] = {"depth": "性能提升了三倍"}  # never said
    ok, text = run_on_recording(bad)
    assert ok is False and "quotes_are_the_candidates_words" in text
