"""Interview levels, and a recommended level from the profile (SPEC-MOCK-INTERVIEW-V2 §3.5).

The levels borrow the P-series names as a point of comparison only. Alibaba publishes no table
from level to years, so the levels are defined by what an interview has to check, and the year
bands are a typical range.

The recommendation is plain code. Years are the union of the profile's jobs by month, so jobs that
overlap count once. The newest job's title can move the result by one level.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from jc.schemas.profile_payload import ProfileExperience

LEVELS: tuple[str, ...] = ("junior", "mid", "senior", "expert")


@dataclass(frozen=True)
class LevelSpec:
    key: str
    label: str
    benchmark: str
    years: str
    requirement: str
    #: How deep the questions go at this level.
    depth: str
    #: Which way follow-ups lean at this level.
    follow_up: str


LEVEL_SPECS: dict[str, LevelSpec] = {
    "junior": LevelSpec(
        key="junior", label="初级", benchmark="P5", years="应届到 3 年",
        requirement="在指导下能独立完成分配的任务，基础扎实，会排查常见问题。",
        depth="是什么、怎么做：概念、实现步骤、常见的坑。",
        follow_up="追问具体怎么做、遇到过什么问题。",
    ),
    "mid": LevelSpec(
        key="mid", label="中级", benchmark="P6", years="3 到 6 年",
        requirement="独立负责一个模块或系统，从设计到上线到运维；能判断需求优先级，对不合理的需求提出异议。",
        depth="为什么这样做：理由、取舍、线上问题的排查路径。",
        follow_up="追问为什么这样做、放弃了什么。",
    ),
    "senior": LevelSpec(
        key="senior", label="高级", benchmark="P7", years="6 到 10 年",
        requirement="是一个领域的负责人，能带领跨团队项目、指导新人；对复杂问题有自己的判断，能影响团队的技术方向。",
        depth="架构与权衡：方案对比、跨团队协调、风险与演进。",
        follow_up="追问方案对比、跨团队的协调与风险。",
    ),
    "expert": LevelSpec(
        key="expert", label="专家", benchmark="P8", years="10 年以上",
        requirement="影响部门或公司层面的技术与业务决策，对行业有判断。",
        depth="方向与决策：战略取舍、组织与技术的结合、长期影响。",
        follow_up="追问决策依据与长期影响。",
    ),
}

#: Years at which each level starts, lower bound included: 3 years is already 中级.
_LEVEL_STARTS_MONTHS: tuple[tuple[str, int], ...] = (
    ("expert", 120), ("senior", 72), ("mid", 36), ("junior", 0),
)
_RAISING_WORDS = ("专家", "架构师", "负责人", "总监")
_LOWERING_WORDS = ("实习", "助理")
_OPEN_END = frozenset({"至今", "现在", "present", "now"})
# 2019, 2019-01, 2019-01-15, 2019/01, 2019.01, 2019年1月, 2019年1月15日
_DATE = re.compile(r"^(\d{4})(?:[-/.年](\d{1,2})月?(?:[-/.]?\d{1,2}日?)?)?$")


@dataclass(frozen=True)
class LevelRecommendation:
    level: str
    years: float
    reason: str


def _month_index(text: str | None, *, bare_year_is: int) -> int | None:
    """A date as a month count, or None when the text is not a date we read.

    A bare year has no month, so the caller says which one it means: January for a start,
    December for an end."""
    match = _DATE.match((text or "").strip())
    if match is None:
        return None
    year = int(match.group(1))
    month = int(match.group(2)) if match.group(2) else bare_year_is
    return year * 12 + month if 1 <= month <= 12 else None


def _interval(job: ProfileExperience, *, today_index: int) -> tuple[int, int] | None:
    """The months a job covers, as [start, end). None when its dates cannot be used."""
    start = _month_index(job.start_date, bare_year_is=1)
    if start is None:
        return None
    end_text = (job.end_date or "").strip()
    if not end_text or end_text.lower() in _OPEN_END:
        end = today_index
    else:
        end = _month_index(end_text, bare_year_is=12)
    if end is None or end < start:
        return None
    return start, end


def _union_months(intervals: Sequence[tuple[int, int]]) -> int:
    total, covered_to = 0, None
    for start, end in sorted(intervals):
        if covered_to is None or start > covered_to:
            total += end - start
            covered_to = end
        elif end > covered_to:
            total += end - covered_to
            covered_to = end
    return total


def _band(months: int) -> str:
    for key, floor in _LEVEL_STARTS_MONTHS:
        if months >= floor:
            return key
    return "junior"


def _title_shift(title: str) -> int:
    raises = any(word in title for word in _RAISING_WORDS)
    lowers = any(word in title for word in _LOWERING_WORDS)
    if raises == lowers:
        return 0
    return 1 if raises else -1


def level_for_profile(
    experiences: Sequence[ProfileExperience], *, today: date
) -> LevelRecommendation | None:
    """A recommended level, or None when no job has dates that can be read."""
    today_index = today.year * 12 + today.month
    usable = [
        (interval, job)
        for job in experiences
        if (interval := _interval(job, today_index=today_index)) is not None
    ]
    if not usable:
        return None
    ignored = len(experiences) - len(usable)

    months = _union_months([interval for interval, _ in usable])
    years = round(months / 12, 1)
    base = _band(months)

    # The newest job is the one that ends last; a job still running ends today.
    (_, _), latest = max(usable, key=lambda item: (item[0][1], item[0][0]))
    shift = _title_shift(latest.title)
    index = min(len(LEVELS) - 1, max(0, LEVELS.index(base) + shift))
    level = LEVELS[index]

    reason = f"你有约 {years:g} 年经历"
    if ignored:
        reason += f"（有 {ignored} 段经历的日期读不出来，没有计入）"
    reason += f"，最近职位是{latest.title}"
    if level != base:
        direction = "上调" if shift > 0 else "下调"
        reason += f"，职位名{direction}一级"
    reason += f"，推荐：{LEVEL_SPECS[level].label}"
    return LevelRecommendation(level=level, years=years, reason=reason)
