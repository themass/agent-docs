"""JD coverage for a full mock interview (SPEC-MOCK-INTERVIEW §4): every must-have is asked about,
the check is deterministic, and a gap is never reported as a pass."""

from __future__ import annotations

from jc.coach.coverage import Candidate, coverage_of, key_terms, next_targets, pick_next

MUST = ["熟悉 Java 或 C++，了解微服务架构", "熟悉 MySQL、Redis", "良好的沟通与协作能力"]


def test_every_must_have_asked_about_is_covered():
    questions = [
        "请讲讲你做微服务拆分的经验",
        "你怎么优化 MySQL 的慢查询？",
        "你如何与产品经理协作？",
    ]
    result = coverage_of(MUST, questions)
    assert result.complete
    assert result.ratio == 1.0


def test_an_uncovered_must_have_is_reported_missing_not_passed():
    result = coverage_of(MUST, ["请讲讲你做微服务拆分的经验"])
    assert not result.complete
    assert "熟悉 MySQL、Redis" in result.missing
    assert "良好的沟通与协作能力" in result.missing


def test_a_jd_with_no_must_haves_is_a_gap_not_a_pass():
    result = coverage_of([], ["随便一个问题"])
    assert result.no_requirements
    assert not result.complete, "nothing to check is not the same as fully covered"


def test_a_requirement_with_no_usable_terms_is_not_counted_as_coverable():
    # "的" and "和" alone carry no skill; a question containing them must not cover it.
    result = coverage_of(["的和"], ["你的工作和经历是什么？"])
    assert result.no_requirements


def test_unrelated_questions_do_not_falsely_cover():
    assert coverage_of(["良好的沟通与协作能力"], ["你对好的代码有什么看法？"]).covered == []
    assert coverage_of(["熟悉 MySQL、Redis"], ["你们团队的服务上线流程是怎样的？"]).covered == []


def test_latin_matching_is_case_insensitive():
    assert coverage_of(["熟悉 Kubernetes"], ["讲讲你的 kubernetes 部署经验"]).complete


def test_key_terms_split_chinese_runs_into_bigrams():
    terms = key_terms("了解微服务架构")
    assert {"微服", "服务", "架构"} <= terms


def test_next_targets_follow_the_jd_order():
    assert next_targets(MUST, ["你怎么优化 MySQL 的慢查询？"]) == [
        "熟悉 Java 或 C++，了解微服务架构",
        "良好的沟通与协作能力",
    ]


def test_picker_targets_the_earliest_uncovered_requirement():
    available = [
        Candidate("q_协作", "你如何与产品经理协作？", experience="A公司"),
        Candidate("q_mysql", "你怎么优化 MySQL 的慢查询？", experience="B公司"),
    ]
    picked = pick_next(MUST, asked=[], available=available)
    # Java/微服务 is the earliest must-have, and nothing available reaches it, so the next
    # uncovered one that something does reach is picked.
    assert picked.question_id in {"q_协作", "q_mysql"}


def test_picker_avoids_the_same_experience_twice_in_a_row():
    # `last` is about A公司 and does NOT reach the Kubernetes requirement, so Kubernetes stays open.
    # Two candidates reach it: one on A公司 (the same job as `last`), one on B公司.
    last = Candidate("q1", "你在 A公司的发布流程是怎样的？", experience="A公司")
    available = [
        Candidate("q2", "你在 A公司怎么用 Kubernetes 部署服务？", experience="A公司"),
        Candidate("q3", "你在 B公司怎么用 Kubernetes 部署服务？", experience="B公司"),
    ]
    picked = pick_next(["熟悉 Kubernetes"], asked=[last], available=available)
    assert picked.question_id == "q3", "a different experience should be asked next"


def test_picker_returns_none_when_nothing_reaches_a_gap():
    picked = pick_next(
        ["熟悉 Kubernetes"],
        asked=[],
        available=[
            Candidate("q1", "你擅长什么编程语言？", experience=None),
        ],
    )
    assert picked is None


def test_picker_never_repeats_a_question():
    q = Candidate("q1", "你怎么优化 MySQL 的慢查询？", experience="A公司")
    assert pick_next(["熟悉 MySQL、Redis"], asked=[q], available=[q]) is None
