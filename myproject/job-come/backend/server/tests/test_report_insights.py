"""The report's derived insights: weakest dimensions with a practice, first-five against last-five,
and the must-haves reached (a question meets a requirement with a mean of at least 6)."""

from __future__ import annotations

from jc.coach.report_insights import PRACTICE, insights, question_mean


def _q(qid: str, **scores):
    return {"question_id": qid, "scores": scores}


def test_question_mean_ignores_unscored_dimensions():
    assert question_mean({"depth": 6, "structure": None, "reflection": 8}) == 7.0
    assert question_mean({"depth": None}) is None


def test_three_weakest_dimensions_each_with_its_practice_and_lowest_question():
    questions = [
        _q("q1", depth=3, structure=9),
        _q("q2", depth=5, structure=8, reflection=2),
    ]
    overall = {"structure": 8.5, "depth": 4.0, "reflection": 2.0, "relevance": 7.0,
               "communication": None}
    out = insights(questions, overall, [], {})
    dims = [s["dimension"] for s in out["suggestions"]]
    assert dims == ["reflection", "depth", "relevance"]
    assert out["suggestions"][1]["question_id"] == "q1"
    assert out["suggestions"][0]["practice"] == PRACTICE["reflection"]


def test_trend_needs_ten_questions_and_compares_first_and_last_five():
    questions = [_q(f"q{i}", depth=2 if i < 5 else 8) for i in range(10)]
    out = insights(questions, {"depth": 5.0}, [], {})
    assert out["trend"] == {"first_five": 2.0, "last_five": 8.0}


def test_no_trend_for_a_short_session():
    out = insights([_q("q1", depth=5)], {"depth": 5.0}, [], {})
    assert out["trend"] is None


def test_coverage_counts_asked_and_met_requirements():
    must = ["Python", "分布式事务"]
    stems = {"q1": "讲一个你用 Python 写过的脚本", "q2": "你如何处理分布式事务"}
    questions = [_q("q1", depth=7), _q("q2", depth=4)]
    out = insights(questions, {"depth": 5.5}, must, stems)
    assert out["coverage"] == {"total": 2, "asked": 2, "meet": 1}
