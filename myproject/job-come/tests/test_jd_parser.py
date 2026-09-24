"""JD parser heuristic fallback."""

from jobcome.services.jd_parser_service import JdParserService


def test_jd_heuristic_parse() -> None:
    text = "高级后端工程师\n字节跳动\n要求 Python、分布式"
    result = JdParserService._heuristic_parse(text)
    assert result.role_title == "高级后端工程师"
    assert result.company == "字节跳动"
