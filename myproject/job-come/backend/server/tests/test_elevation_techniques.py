"""Tests for deterministic labelling of resume elevation techniques."""

from __future__ import annotations

import pytest

from jc.services.elevation_techniques import (
    TECHNIQUES,
    annotate_elevation_map,
    classify_change,
    summarize_techniques,
)


def test_no_change_yields_no_labels() -> None:
    assert classify_change("负责订单系统重构", "负责订单系统重构") == []


def test_empty_written_text_yields_no_labels() -> None:
    assert classify_change("负责订单系统重构", "") == []


def test_added_metric_is_quantified() -> None:
    labels = classify_change(
        "优化了发布流程",
        "优化发布流程，Lead Time 从 25 天缩短至 8 天",
    )
    assert "quantified" in labels


def test_added_outcome_without_number() -> None:
    labels = classify_change(
        "拆分支付模块",
        "拆分支付模块，解决下游服务强耦合问题",
    )
    assert "outcome" in labels
    assert "quantified" not in labels


def test_weak_verb_replaced_by_ownership_verb() -> None:
    labels = classify_change("参与网关改造", "主导网关改造")
    assert "ownership" in labels


def test_ownership_not_claimed_when_source_already_owns() -> None:
    labels = classify_change("主导网关改造", "主导 API 网关改造")
    assert "ownership" not in labels


def test_job_keyword_alignment() -> None:
    labels = classify_change(
        "负责服务治理",
        "负责服务网格治理",
        job_keywords=["服务网格", "Kubernetes"],
    )
    assert "jd_aligned" in labels


def test_job_keyword_already_present_is_not_alignment() -> None:
    labels = classify_change(
        "负责服务网格治理工作",
        "负责服务网格治理，统一流量入口",
        job_keywords=["服务网格"],
    )
    assert "jd_aligned" not in labels


def test_short_keywords_are_ignored_to_avoid_noise() -> None:
    labels = classify_change("负责 A 系统", "负责 B 系统", job_keywords=["B"])
    assert "jd_aligned" not in labels


def test_length_labels_only_fire_when_nothing_else_does() -> None:
    tightened = classify_change(
        "本人在该项目中主要是负责了一些关于配置中心的日常维护相关的工作内容",
        "维护配置中心",
    )
    assert tightened == ["tightened"]

    rich = classify_change(
        "做了发布流程的事情",
        "主导发布流程治理，部署耗时降低 40%",
    )
    assert "tightened" not in rich
    assert "expanded" not in rich


def test_labels_follow_catalogue_order() -> None:
    labels = classify_change(
        "参与推送链路相关工作",
        "主导推送链路重构，支撑全量推送 4kw，到达率提升 12%",
    )
    order = [t["id"] for t in TECHNIQUES]
    assert labels == sorted(labels, key=order.index)


def test_annotate_preserves_entries_and_does_not_mutate_input() -> None:
    source = [
        {
            "field_path": "experience_blocks[0].bullets[0]",
            "source_text": "参与监控系统建设",
            "written_text": "主导监控系统建设，告警准确率提升 30%",
            "needs_defense": True,
        }
    ]
    out = annotate_elevation_map(source)
    assert len(out) == 1
    assert out[0]["field_path"] == source[0]["field_path"]
    assert out[0]["needs_defense"] is True
    assert "ownership" in out[0]["techniques"]
    assert "techniques" not in source[0], "input must not be mutated"


def test_annotate_always_sets_techniques_key() -> None:
    out = annotate_elevation_map([{"source_text": "x", "written_text": "x"}])
    assert out[0]["techniques"] == []


def test_summarize_counts_and_keeps_catalogue_order() -> None:
    entries = annotate_elevation_map(
        [
            {"source_text": "参与网关改造", "written_text": "主导网关改造"},
            {"source_text": "优化流程", "written_text": "优化流程，耗时降低 40%"},
            {"source_text": "参与风控", "written_text": "主导风控策略迭代"},
        ]
    )
    summary = summarize_techniques(entries)
    by_id = {item["id"]: item for item in summary}
    assert by_id["ownership"]["count"] == 2
    assert by_id["quantified"]["count"] == 1
    order = [t["id"] for t in TECHNIQUES]
    assert [item["id"] for item in summary] == sorted(by_id, key=order.index)
    # Every reported technique carries user-facing copy for the UI.
    assert all(item["label"] and item["hint"] for item in summary)


def test_summarize_empty_map() -> None:
    assert summarize_techniques([]) == []


@pytest.mark.parametrize(
    ("source", "written"),
    [
        ("负责 CI 流程", "负责 CI/CD 流程与 Jenkins 迁移"),
        ("做数据同步", "搭建数据同步链路"),
    ],
)
def test_object_clarification_detected(source: str, written: str) -> None:
    assert "object" in classify_change(source, written)


def test_non_technical_objects_count_as_objects_for_their_role() -> None:
    """An operations bullet must not be told it is vague for lacking a system noun."""
    from jc.services.elevation_techniques import classify_change

    source = "负责区域客户的日常维护"
    written = "重做商机管道的分层维护方式，把高意向客户前置跟进"

    # Without a playbook the engineering-tuned regex finds no object in this bullet,
    # so a perfectly concrete sales rewrite reads as vague.
    assert "object" not in classify_change(source, written)
    assert "object" in classify_change(source, written, role_family="sales")
