"""窄记忆的确定性策略（P6）：紧凑索引选取、去重、淘汰。纯策略层，无 I/O。

存储复用既有 ca_memory_item（一条一事实、supersede、词法排序都在），这里只补它没有的
「策略」：给提示词挑哪几条（容量内）、重复怎么并、超容量忘哪些。规则必须能被用户
一句话讲明白——所以只有 kind 优先级、时间与字数预算，没有打分模型。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from companion.agent.memory.port import MemoryItem, MemoryKind
from companion.service.card.model import render_card_lines
from companion.service.memory.policy import (
    build_context,
    dedupe_same_content,
    plan_forgetting,
    select_index,
)


def _item(i: int, content: str, kind: MemoryKind = MemoryKind.FACT, minutes_ago: int = 0) -> MemoryItem:
    return MemoryItem(id=f"m{i}", content=content, kind=kind,
                      created_at=datetime(2026, 11, 24, tzinfo=UTC) - timedelta(minutes=minutes_ago))


# ---- 紧凑索引选取 ----

def test_select_prefers_preferences_over_plain_facts():
    items = [_item(1, "普通的事实"), _item(2, "喜欢安静的咖啡馆", MemoryKind.PREFERENCE)]
    chosen = select_index(items, max_entries=1)
    assert [i.id for i in chosen] == ["m2"]


def test_select_within_same_kind_prefers_newer():
    items = [_item(1, "旧事实", minutes_ago=100), _item(2, "新事实", minutes_ago=1)]
    chosen = select_index(items, max_entries=1)
    assert [i.id for i in chosen] == ["m2"]


def test_select_respects_entry_and_char_budgets():
    items = [_item(1, "甲乙丙丁戊己庚辛壬癸" * 10, minutes_ago=5), _item(2, "短事实", minutes_ago=1),
             _item(3, "也短", minutes_ago=2)]
    chosen = select_index(items, max_entries=10, max_chars=20)
    assert [i.id for i in chosen] == ["m2", "m3"]  # 超预算的长条目跳过而不是截断


def test_select_output_order_is_display_order_newest_first():
    items = [_item(1, "旧偏好", MemoryKind.PREFERENCE, minutes_ago=500),
             _item(2, "新偏好", MemoryKind.PREFERENCE, minutes_ago=1),
             _item(3, "新事实", minutes_ago=0)]
    chosen = select_index(items, max_entries=3)
    assert [i.id for i in chosen] == ["m2", "m1", "m3"]  # kind 优先，组内新在前


# ---- 去重 ----

def test_dedupe_keeps_newest_of_identical_content():
    items = [_item(1, "住在杭州", minutes_ago=300), _item(2, "住在杭州", minutes_ago=10),
             _item(3, "养了只猫", minutes_ago=200)]
    kept = dedupe_same_content(items)
    assert [i.id for i in kept] == ["m2", "m3"]  # 新在前；同一句话只留最新


def test_dedupe_ignores_surrounding_whitespace():
    items = [_item(1, "住在杭州  "), _item(2, "住在杭州")]
    assert len(dedupe_same_content(items)) == 1


# ---- 淘汰（可忘）----

def test_forgetting_evicts_oldest_beyond_capacity():
    items = [_item(1, "很旧", minutes_ago=10000), _item(2, "较旧", minutes_ago=5000),
             _item(3, "新", minutes_ago=1)]
    evict = plan_forgetting(items, max_entries=2)
    assert [i.id for i in evict] == ["m1"]


def test_forgetting_protects_preferences_within_grace_window():
    items = [_item(1, "旧偏好", MemoryKind.PREFERENCE, minutes_ago=10000),
             _item(2, "旧事实", minutes_ago=9000), _item(3, "新事实", minutes_ago=1)]
    evict = plan_forgetting(items, max_entries=2, protect_days=30)
    assert [i.id for i in evict] == ["m2"]  # 偏好未超保护期 → 忘普通事实


def test_forgetting_still_evicts_stale_preferences_when_over_capacity():
    old = datetime(2026, 1, 1, tzinfo=UTC)
    items = [
        MemoryItem(id="p1", content="很旧的偏好", kind=MemoryKind.PREFERENCE, created_at=old),
        MemoryItem(id="f1", content="也很旧的事实", kind=MemoryKind.FACT, created_at=old),
    ]
    evict = plan_forgetting(items, max_entries=1, now=datetime(2026, 11, 24, tzinfo=UTC), protect_days=30)
    assert len(evict) == 1  # 全超出保护期时照样能收敛到容量内


# ---- 注入接口：build_context ----

def test_build_context_orders_card_before_memory():
    lines = build_context(
        card_fields={"name": "临澈", "boundaries": ["不谈钱"]},
        memory_items=[_item(1, "喜欢手冲咖啡", MemoryKind.PREFERENCE)],
        max_chars=4000,
    )
    assert lines[:3] == ["- 名字：临澈", "- 关系边界：不谈钱", "- 喜欢手冲咖啡"]


def test_build_context_empty_inputs_give_no_lines():
    assert build_context(card_fields={}, memory_items=[], max_chars=4000) == []


def test_build_context_drops_memory_lines_when_out_of_budget():
    lines = build_context(
        card_fields={"description": "D" * 100},
        memory_items=[_item(1, "记忆" * 60)],
        max_chars=120,
    )
    assert all("记忆记忆" not in line for line in lines)
    assert any(line.startswith("- 角色描述") for line in lines)  # 卡先占预算


def test_build_context_skips_card_lines_when_card_empty_and_keeps_memory():
    lines = build_context(card_fields={}, memory_items=[_item(1, "住在杭州")], max_chars=4000)
    assert lines == ["- 住在杭州"]


def test_build_context_render_matches_card_renderer_exactly():
    fields = {"name": "A", "personality": "P"}
    lines = build_context(card_fields=fields, memory_items=[], max_chars=4000)
    assert lines == render_card_lines(fields)
