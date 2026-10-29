"""`fragment_guard`: merge back what the structurer over-split, prove it only in the
cases the source itself can prove -- and never changes a character of real content.
"""

from __future__ import annotations

from jc.schemas.profile_payload import ProfilePayload
from jc.services.fragment_guard import merge_oversplit_highlights

RAW = """李国庆
快手 服务端 leader
2021.07 - 至今
- 负责快手审核中台的后端架构与团队管理
- 该系统支撑 8 大基地、5000+ 审核人员
- 日均处理 2000 万条内容
- 主导从单体到微服务的拆分

阿里巴巴 高级工程师
2018.01 - 2021.06
这是一段纯文字叙述的早期经历，源文件里完全没有任何项目符号或编号。
"""


def profile(highlights: list[str], second_highlights: list[str] | None = None) -> ProfilePayload:
    return ProfilePayload.model_validate({
        "contact": {"name": "李国庆"}, "meta": {"source_locale": "zh-CN"},
        "experiences": [
            {"id": "e1", "company": "快手", "title": "服务端 leader",
             "start_date": "2021-07", "highlights": highlights},
            {"id": "e2", "company": "阿里巴巴", "title": "高级工程师",
             "start_date": "2018-01", "end_date": "2021-06",
             "highlights": second_highlights or []},
        ],
    })


def test_merges_fragments_the_source_marks_as_one_unit_and_loses_no_text():
    # The structurer split "负责...管理" and "该系统...人员" from what the source marks
    # as two bullets into four fragments, plus kept the other two as single bullets --
    # six highlights where the source's own `-` markers prove there should be four.
    oversplit = [
        "负责快手审核中台的后端架构",
        "与团队管理",
        "该系统支撑 8 大基地",
        "、5000+ 审核人员",
        "日均处理 2000 万条内容",
        "主导从单体到微服务的拆分",
    ]
    before_text = "".join(oversplit)
    p = profile(oversplit)
    merge_oversplit_highlights(p, RAW)
    merged = p.experiences[0].highlights
    assert len(merged) == 4, merged
    # Lossless: every character from every fragment survives somewhere in the result,
    # merely regrouped and joined -- the guard may misjudge a boundary, never drop text.
    assert "".join(merged).replace("；", "") == before_text


def test_does_not_touch_a_block_the_source_never_marked_with_bullets():
    # Second experience is plain prose in the source -- no markers to compare against,
    # so whatever the structurer returned (here, arbitrarily split) is left alone.
    p = profile([], ["这是一段", "纯文字叙述的早期经历"])
    merge_oversplit_highlights(p, RAW)
    assert p.experiences[1].highlights == ["这是一段", "纯文字叙述的早期经历"]


def test_does_not_touch_a_block_already_at_or_below_the_marker_count():
    # Four source markers, four highlights -- already as coarse as the source, which
    # is not the failure this guard exists to fix.
    already_right = [
        "负责快手审核中台的后端架构与团队管理",
        "该系统支撑 8 大基地、5000+ 审核人员",
        "日均处理 2000 万条内容",
        "主导从单体到微服务的拆分",
    ]
    p = profile(list(already_right))
    merge_oversplit_highlights(p, RAW)
    assert p.experiences[0].highlights == already_right


def test_noop_when_there_is_no_raw_text_to_check_against():
    # The vision/OCR ingest routes have no intermediate text at all.
    oversplit = ["一", "二", "三", "四", "五", "六"]
    p = profile(oversplit)
    merge_oversplit_highlights(p, "")
    assert p.experiences[0].highlights == oversplit
