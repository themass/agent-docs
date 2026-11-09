"""The opening is the server's template (ADR-008): it names the company and role, the number of
questions, and asks for the self-introduction. No model writes it."""

from jc.services.mock_opening import opening_text


def test_the_opening_names_the_company_and_role_and_asks_for_a_self_introduction():
    text = opening_text("示例桁架科技", "后端研发工程师")
    assert "示例桁架科技后端研发工程师的面试官" in text
    assert "五到六个问题" in text
    assert "自我介绍" in text
    assert "？" not in text and "?" not in text


def test_without_a_company_or_role_the_opening_still_reads_well():
    text = opening_text(None, None)
    assert text.startswith("你好，我是这个岗位的面试官")
