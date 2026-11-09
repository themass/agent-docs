"""Question counting for an interview's replies. The one-question rule is the server's (ADR-008)."""

from jc.services.interview_reply import question_count


def test_counting_question_marks_in_both_scripts():
    assert question_count("你怎么看？这个呢?") == 2
    assert question_count("请讲一个你做过的项目？") == 1
    assert question_count("") == 0
