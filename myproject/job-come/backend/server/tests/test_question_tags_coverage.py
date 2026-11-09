"""A question tagged with a must-have counts as covering it, even when its words do not match.

Live (2026-11-08): the report said 「必备项 7 项里只问到 1 项」 for interviews that had asked about
most of them: a requirement such as 「漏斗分析」 is seldom in the words of a good question."""

from __future__ import annotations

from jc.coach.coverage import coverage_of, question_match_text

MUST = ["用户增长运营", "漏斗分析", "A/B 测试", "数据驱动决策"]


def test_a_stem_alone_does_not_reach_a_requirement_it_does_not_name():
    stem = "注册到首单流失最重，原因你是靠什么数据坐实的？"
    assert "漏斗分析" not in coverage_of(MUST, [stem]).covered


def test_a_tag_naming_the_requirement_covers_it():
    stem = "注册到首单流失最重，原因你是靠什么数据坐实的？"
    text = question_match_text(stem, ["漏斗分析"])
    assert "漏斗分析" in coverage_of(MUST, [text]).covered


def test_no_tags_leaves_the_stem_as_it_was():
    assert question_match_text("讲一次你处理故障的经历", None) == "讲一次你处理故障的经历"
    assert question_match_text("讲一次你处理故障的经历", []) == "讲一次你处理故障的经历"


def test_the_tag_is_read_on_the_question_row(tmp_path):
    from jc.coach.coverage import coverage_of as cover

    assert cover(MUST, [question_match_text("x", ["A/B 测试"])]).covered == ["A/B 测试"]
