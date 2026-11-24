"""角色卡覆盖链的确定性合并（P6）。纯策略层：没有 I/O，没有模型。

规则只有一条能被用户讲明白的那种：版本按编号从小到大依次生效，后写的字段盖掉先写的；
值给 null 就是清除该字段；dict/list 整值替换，不做拼接——拼接规则用户猜不到。
"""

from __future__ import annotations

import pytest

from companion.service.card.model import (
    CardChangeInvalid,
    merge_chain,
    normalize_changeset,
    render_card_lines,
)


def test_empty_chain_returns_base():
    base = {"name": "临澈", "description": "原描述"}
    assert merge_chain(base, []) == base


def test_base_is_not_mutated():
    base = {"name": "A"}
    merge_chain(base, [{"name": "B"}])
    assert base == {"name": "A"}


def test_later_version_overrides_earlier():
    merged = merge_chain({}, [{"description": "一"}, {"description": "二"}])
    assert merged["description"] == "二"


def test_null_clears_field():
    merged = merge_chain({"personality": "温柔"}, [{"personality": None}])
    assert "personality" not in merged


def test_voice_dict_is_replaced_whole_not_merged():
    merged = merge_chain({"voice": {"engine": "x", "speed": 1.0}}, [{"voice": {"speed": 0.9}}])
    assert merged["voice"] == {"speed": 0.9}


def test_boundaries_list_is_replaced_not_appended():
    merged = merge_chain({"boundaries": ["不聊工作"]}, [{"boundaries": ["不聊钱"]}])
    assert merged["boundaries"] == ["不聊钱"]


def test_unknown_field_is_rejected():
    with pytest.raises(CardChangeInvalid):
        normalize_changeset({"system_prompt": "越权注入"})


def test_empty_changeset_is_rejected():
    with pytest.raises(CardChangeInvalid):
        normalize_changeset({})
    with pytest.raises(CardChangeInvalid):
        normalize_changeset({"name": None})  # 只剩清除、没有任何新内容也要拒：空版本没有意义


def test_name_length_is_capped():
    with pytest.raises(CardChangeInvalid):
        normalize_changeset({"name": "长" * 41})


def test_text_fields_length_is_capped():
    with pytest.raises(CardChangeInvalid):
        normalize_changeset({"description": "长" * 1001})


def test_boundaries_count_is_capped():
    with pytest.raises(CardChangeInvalid):
        normalize_changeset({"boundaries": ["x"] * 11})


def test_boundaries_item_length_is_capped():
    with pytest.raises(CardChangeInvalid):
        normalize_changeset({"boundaries": ["字" * 121]})


def test_non_string_value_is_rejected():
    with pytest.raises(CardChangeInvalid):
        normalize_changeset({"name": 3})


def test_whitespace_is_normalized_and_blank_text_clears():
    normalized = normalize_changeset({"name": "  小澈  "})
    assert normalized == {"name": "小澈"}
    # 纯空白等同清除；只剩清除的变更集等于空变更集，同样被拒
    with pytest.raises(CardChangeInvalid):
        normalize_changeset({"description": "   "})


def test_voice_must_be_a_mapping_and_is_key_limited():
    assert normalize_changeset({"voice": {"speed": 0.9}}) == {"voice": {"speed": 0.9}}
    with pytest.raises(CardChangeInvalid):
        normalize_changeset({"voice": "甜美"})


def test_render_orders_identity_then_voice_then_boundaries():
    lines = render_card_lines({
        "boundaries": ["不谈钱", "不聊工作"],
        "voice": {"speed": 0.9},
        "description": "D",
        "name": "A",
    })
    assert lines == [
        "- 名字：A",
        "- 角色描述：D",
        "- 声音偏好：speed=0.9",
        "- 关系边界：不谈钱",
        "- 关系边界：不聊工作",
    ]


def test_render_skips_absent_fields():
    assert render_card_lines({}) == []
    assert render_card_lines({"personality": "温柔"}) == ["- 性格：温柔"]
