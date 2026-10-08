from jobcome.agent.coach_task import wrap_coach_mock_message
from jobcome.coach.planner import select_bank_draws


def test_select_bank_draws_prefers_practiced() -> None:
    items = [("new", 0), ("old", 2), ("mid", 1)]
    assert select_bank_draws(items, n=1) == ["old"]


def test_select_bank_draws_empty() -> None:
    assert select_bank_draws([], n=1) == []


def test_select_bank_draws_first_round_when_none_practiced() -> None:
    items = [("a", 0), ("b", 0)]
    assert select_bank_draws(items, n=1) == ["a"]


def test_wrap_coach_mock_requires_upsert_and_chinese_task() -> None:
    text = wrap_coach_mock_message(
        "下一题",
        profile_id="prof_x",
        job_id="job_x",
        mock_session_id="mock_x",
        drawn_stems=["介绍一个难点"],
    )
    assert "面试模拟任务" in text
    assert "jobcome_question_upsert" in text
    assert "来自题库" in text
    assert "介绍一个难点" in text
    assert "下一题" in text
    assert "不要自我介绍" in text
