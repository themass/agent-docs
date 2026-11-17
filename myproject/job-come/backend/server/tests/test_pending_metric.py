"""The honest-gap marker: detected, and never confused with a builder placeholder.

Two markers now reach the page, and they need opposite advice:

- `（待补充经历要点）` — our builder wrote it for a role with no source highlights.
  The fix is "write this section".
- `[量化指标待补：P99 延迟]` — the writer kept the sentence and refused to guess the
  number. The fix is "fill in this figure".

Both must be reported; neither may be reported as blocking. The export gate is advisory by
design (a false positive once locked users out of their own document), so a test that only
asserted "the issue exists" would pass even if the severity drifted to `error`. The checks
below pin severity and code on both sides, and the negative cases pin that ordinary prose —
including a bullet that legitimately mentions 量化 in another context — is left alone.
"""

from __future__ import annotations

from jc.services.delivery_report import with_delivery_issues


def _sections(bullets: list[str], *, projects: list[str] | None = None) -> dict:
    return {
        "experience_blocks": [{"bullets": bullets}],
        "project_blocks": [{"bullets": projects or []}],
    }


def test_a_pending_metric_is_reported_as_a_warning_with_its_dimension():
    issues = with_delivery_issues(
        [], _sections(["重构订单查询链路，[量化指标待补：P99 延迟] 由缓存层承接"])
    )
    pending = [i for i in issues if i.get("code") == "pending_metric"]
    assert len(pending) == 1, issues
    issue = pending[0]
    assert issue["severity"] == "warning", "a pending metric must never block export"
    assert issue["field"] == "experience_blocks[0].bullets[0]"
    assert "P99 延迟" in issue["message"], "the user must be told which number is missing"


def test_full_width_brackets_and_ascii_brackets_both_parse():
    """The writer is a model: it mixes ［］ with [], and a marker we fail to see is a
    marker the user never gets told about."""
    for text in (
        "降低了 [量化指标待补：QPS] 相关压力",
        "降低了 ［量化指标待补：QPS］相关压力",
        "降低了[量化指标待补: QPS]相关压力",
    ):
        issues = with_delivery_issues([], _sections([text]))
        assert [i["code"] for i in issues] == ["pending_metric"], text


def test_each_marker_is_reported_separately_and_in_projects_too():
    issues = with_delivery_issues(
        [],
        _sections(
            [
                "从 [量化指标待补：P99] 降到 [量化指标待补：错误率]",
            ],
            projects=["覆盖 [量化指标待补：业务线数] 条线"],
        ),
    )
    codes = [i["code"] for i in issues]
    assert codes.count("pending_metric") == 3, issues
    assert "project_blocks[0].bullets[0]" in {i["field"] for i in issues}


def test_a_builder_placeholder_keeps_its_own_code_and_advice():
    """The two markers must stay distinguishable — the tab tells the user two different
    things to do, and collapsing them sends them to the wrong screen."""
    issues = with_delivery_issues([], _sections(["（待补充经历要点）"]))
    assert [i["code"] for i in issues] == ["placeholder_bullet"]
    assert issues[0]["severity"] == "warning"


def test_ordinary_prose_is_not_a_pending_metric():
    """A negative case that a looser pattern would fail: 量化 next to 待补 in the same
    sentence, but not in the marker shape, must not produce a finding."""
    for text in (
        "量化指标待补：这句没有括号",
        "完成了量化指标的补充工作",
        "待补充经历要点见左侧",
        "P99 延迟从 800ms 降到 120ms",
    ):
        issues = with_delivery_issues([], _sections([text]))
        assert issues == [], f"{text!r} produced {issues}"
