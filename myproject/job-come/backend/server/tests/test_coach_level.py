"""Interview levels and the recommendation from a profile (SPEC-MOCK-INTERVIEW-V2 §3.5).

The recommendation is plain code. These tests pin the year bands, how overlapping jobs are
counted, how a title moves the level, and that messy dates never raise."""

from __future__ import annotations

from datetime import date

import pytest

from jc.coach.level import LEVEL_SPECS, LEVELS, level_for_profile
from jc.schemas.profile_payload import ProfileExperience

TODAY = date(2026, 11, 5)


def _job(start: str, end: str | None, title: str = "后端工程师", n: int = 1) -> ProfileExperience:
    return ProfileExperience(id=f"e{n}", company="某公司", title=title, start_date=start,
                             end_date=end)


def test_the_four_levels_are_declared_with_a_spec_each():
    assert LEVELS == ("junior", "mid", "senior", "expert")
    assert [LEVEL_SPECS[key].benchmark for key in LEVELS] == ["P5", "P6", "P7", "P8"]
    assert all(LEVEL_SPECS[key].depth and LEVEL_SPECS[key].follow_up for key in LEVELS)


def test_five_years_of_backend_work_recommends_mid():
    out = level_for_profile([_job("2019-01", "2024-01")], today=TODAY)
    assert out is not None
    assert (out.level, out.years) == ("mid", 5.0)


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("2023-12", "2026-10", "junior"),  # 2.9 years
        ("2023-10", "2026-10", "mid"),     # 3.0 years: lower bound inclusive
        ("2020-10", "2026-10", "senior"),  # 6.0 years
        ("2016-10", "2026-10", "expert"),  # 10.0 years
    ],
)
def test_the_year_bands_include_their_lower_bound(start, end, expected):
    out = level_for_profile([_job(start, end)], today=TODAY)
    assert out is not None and out.level == expected


def test_overlapping_jobs_are_counted_once():
    jobs = [_job("2020-01", "2022-01", n=1), _job("2021-01", "2023-01", n=2)]
    out = level_for_profile(jobs, today=TODAY)
    assert out is not None and out.years == 3.0


def test_a_job_without_an_end_date_runs_to_today():
    out = level_for_profile([_job("2021-11", None)], today=TODAY)
    assert out is not None and out.years == 5.0


def test_a_senior_title_in_the_latest_job_raises_one_level():
    jobs = [_job("2019-01", "2022-01", "后端工程师", 1), _job("2022-02", "2024-01", "架构师", 2)]
    out = level_for_profile(jobs, today=TODAY)
    assert out is not None and out.level == "senior" and "架构师" in out.reason


def test_an_intern_title_in_the_latest_job_lowers_one_level():
    jobs = [_job("2019-01", "2024-01", "实习生")]
    out = level_for_profile(jobs, today=TODAY)
    assert out is not None and out.level == "junior"


def test_only_the_latest_job_decides_the_title_adjustment():
    jobs = [_job("2019-01", "2021-01", "技术总监", 1), _job("2021-02", "2024-01", "开发工程师", 2)]
    out = level_for_profile(jobs, today=TODAY)
    assert out is not None and out.level == "mid"


def test_a_title_with_words_from_both_sides_adjusts_nothing():
    out = level_for_profile([_job("2019-01", "2024-01", "实习架构师")], today=TODAY)
    assert out is not None and out.level == "mid"


def test_the_adjustment_stays_within_the_four_levels():
    top = level_for_profile([_job("2012-01", "2024-01", "技术总监")], today=TODAY)
    bottom = level_for_profile([_job("2025-06", "2026-06", "助理工程师")], today=TODAY)
    assert top is not None and top.level == "expert"
    assert bottom is not None and bottom.level == "junior"


@pytest.mark.parametrize(
    ("start", "end"),
    [("", None), ("至今", None), ("2020", "2022"), ("abc", "def"), ("2024-05", "2022-01")],
)
def test_unusable_dates_give_no_recommendation_and_never_raise(start, end):
    assert level_for_profile([_job(start, end)], today=TODAY) is None


def test_a_job_with_a_bad_date_is_skipped_but_the_others_count():
    jobs = [_job("至今", None, n=1), _job("2019-01", "2024-01", n=2)]
    out = level_for_profile(jobs, today=TODAY)
    assert out is not None and out.years == 5.0


def test_no_experience_gives_no_recommendation():
    assert level_for_profile([], today=TODAY) is None


def test_the_reason_names_years_title_and_level():
    out = level_for_profile([_job("2019-01", "2024-01", "后端工程师")], today=TODAY)
    assert out is not None
    assert "约 5 年" in out.reason and "后端工程师" in out.reason and "中级" in out.reason
