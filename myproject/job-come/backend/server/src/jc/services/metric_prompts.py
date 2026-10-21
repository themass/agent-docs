"""Turn "add a number" into something the user can click.

The product problem
-------------------
`evidence_gaps` asks the right question — "这件事带来的变化能用一个数字说明吗" — and then
leaves the user in front of an empty textarea. A one-line hint ("可以从这些角度想：P99 延迟
/ QPS …") is a list of nouns; the user still has to invent the sentence, decide the unit,
and guess what shape of answer we can actually use. That is the work they came here to
have done for them, and it is the work a model is good at.

So this module expands each role-appropriate metric into a **candidate**: the dimension,
the unit it is measured in, which direction counts as good, and a sentence skeleton with
the number left out.

The line this must not cross
----------------------------
A candidate never carries a value. Not a default, not an example number, not a
placeholder that reads like one. Handing a user `P99 从 800ms 降到 200ms` to click is
fabricating a fact on their behalf — they will accept it because it looks plausible, it
reaches a real recruiter, and it collapses in the interview where the cost is entirely
theirs. See `TECH-RESUME-WRITING.md` §3.6.

What we may supply is the *shape*: `P99 延迟从 ___ 降到 ___`. The blanks are the user's,
and an unfilled candidate is never written to the profile.

Derived, not tabulated
----------------------
The dimensions themselves already live in `role_families.RolePlaybook.outcome_metrics`,
one tuple per family, and they are what the writer prompt and the gap questions are built
from. Re-listing them here with units attached would create a second copy that drifts
from the first: a family gains a metric, only one list learns about it, and the two
disagree with nothing failing. So the unit and direction are derived from the dimension
name by keyword, and an unrecognised dimension degrades to a neutral skeleton rather than
being dropped — a dimension with a plain blank is still more use than a bare noun.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from jc.domain.role_families import RolePlaybook

#: The blank the user fills. Deliberately not a number and not a realistic-looking token:
#: anything that reads like a value invites being left as-is.
BLANK = "___"


@dataclass(frozen=True, slots=True)
class MetricCandidate:
    """One clickable way to quantify a bullet. Carries no value, ever."""

    #: The dimension, as the playbook names it (`P99/P95 延迟`).
    dimension: str
    #: How it is measured (`ms`, `%`, `QPS`). Empty when the dimension has no fixed unit.
    unit: str
    #: `down` | `up` | `scale` — whether smaller, larger, or simply bigger-scope is the
    #: achievement. Drives the skeleton and lets the UI label it honestly.
    direction: str
    #: A sentence with the numbers removed, e.g. `P99 延迟从 ___ 降到 ___`.
    skeleton: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "unit": self.unit,
            "direction": self.direction,
            "skeleton": self.skeleton,
        }


#: Direction words that appear *inside* a dimension name (`风险敞口下降`,
#: `成本或工时节省`). These are checked first and they win, because the author of that
#: name already answered the direction question -- and a from/to skeleton would then
#: restate it wrongly ("风险敞口下降从 ___ 降到 ___").
_SELF_DOWN = ("下降", "降低", "减少", "节省", "收敛", "压缩")
_SELF_UP = ("提升", "增长", "增加", "提高")

#: (keywords, unit, direction). First match wins, so specific patterns precede generic
#: ones -- `错误率` must be reached before the bare `率`, or an error rate is told to go
#: up. Keyed on substrings of the dimension name because that name is authored in
#: `role_families` and this module must not re-own it.
#:
#: `direction` here means "which way is the achievement", not "which way the number
#: moved". `scale` is for dimensions where the achievement is the size itself.
_RULES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    # Smaller is better.
    # Latency and turnaround are both "smaller is better" but are not measured in the
    # same units, and offering 「天」for a P99 figure makes the hint read as wrong.
    (("延迟", "耗时", "时长", "启动"), "ms / s", "down"),
    (("mttr", "lead time", "时效", "周期", "到岗"), "天 / 小时", "down"),
    (("崩溃率", "故障率", "错误率", "差错率", "缺陷率", "投诉率", "流失"), "%", "down"),
    (("包体积", "内存占用", "资源成本", "单位成本"), "MB / GB", "down"),
    (("告警噪音", "事故数", "返工"), "", "down"),
    # Larger is better. Any `率` reaching here is one of ours by name, so the generic
    # `率` fallback sits in this group rather than in `scale`: a rate nobody listed is
    # far more often a success rate than a share.
    (("qps", "tps", "吞吐"), "QPS", "up"),
    (
        (
            "可用性", "sla", "成功率", "留存", "转化", "复购", "满意度", "nps",
            "完成率", "准确率", "赢率", "采纳",
        ),
        "%",
        "up",
    ),
    (("gmv", "arr", "收入", "营收", "回款", "客单价", "增购"), "元 / 万元", "up"),
    (("dau", "mau", "日活", "月活", "用户数", "人次"), "人", "up"),
    (("发布频率", "交付频率"), "次 / 周", "up"),
    # The size is the point. `覆盖率` before `覆盖`, or a rate loses its percent sign.
    (("覆盖率", "占比", "比例", "渗透率"), "%", "scale"),
    (("覆盖", "规模", "容量", "业务线", "团队", "数据量", "条数", "数量"), "", "scale"),
    (("成本", "预算", "费用", "金额"), "元 / 万元", "scale"),
)

#: Dimensions written as `A/B C` name two interchangeable measures of one thing
#: (`P99/P95 延迟`). Offering both as separate candidates doubles the list without adding
#: a choice, so the first is used and the second is dropped.
_ALT_RE = re.compile(r"^([^/]+)/\S+(\s+.*)?$")

#: A CJK dimension name followed directly by a Latin-script token (or the reverse) reads
#: as one run-together word. `QPS从 ___` is the symptom.
_CJK = r"\u4e00-\u9fff\u3000-\u303f"
_LATIN_THEN_CJK = re.compile(rf"([0-9A-Za-z%）\)])([{_CJK}])")
_CJK_THEN_LATIN = re.compile(rf"([{_CJK}])([0-9A-Za-z])")


def _spaced(text: str) -> str:
    """Insert the space CJK/Latin boundaries need, so `QPS从` reads as `QPS 从`."""
    out = _LATIN_THEN_CJK.sub(r"\1 \2", text)
    return _CJK_THEN_LATIN.sub(r"\1 \2", out)


def _canonical(dimension: str) -> str:
    match = _ALT_RE.match(dimension.strip())
    if not match:
        return dimension.strip()
    head, tail = match.group(1), match.group(2) or ""
    return f"{head}{tail}".strip()


def _classify(dimension: str) -> tuple[str, str]:
    """(unit, direction) for one dimension name.

    `direction` may come back as `unknown`, and that is a real answer rather than a
    failure: it produces a skeleton that asks for the number without asserting which way
    it should have moved. The alternative -- defaulting to `up` -- silently tells a user
    their error rate was supposed to increase, which is both wrong and the kind of wrong
    that looks authoritative.
    """
    low = dimension.lower()
    if any(k in dimension for k in _SELF_DOWN):
        return _unit_only(low), "self"
    if any(k in dimension for k in _SELF_UP):
        return _unit_only(low), "self"
    for keywords, unit, direction in _RULES:
        if any(k in low for k in keywords):
            return unit, direction
    return "", "unknown"


def _unit_only(low: str) -> str:
    """The unit for a dimension whose direction is already in its own name."""
    for keywords, unit, _ in _RULES:
        if any(k in low for k in keywords):
            return unit
    return ""


def _skeleton(dimension: str, direction: str) -> str:
    """A sentence with the numbers removed. Never a value, not even a plausible one."""
    if direction == "down":
        return _spaced(f"{dimension}从 {BLANK} 降到 {BLANK}")
    if direction == "up":
        return _spaced(f"{dimension}从 {BLANK} 提升到 {BLANK}")
    if direction == "scale":
        return _spaced(f"{dimension}达到 {BLANK}")
    # `self`: the name already states the movement, so restating it would contradict
    # itself. `unknown`: we have no basis for claiming a direction at all. Both get the
    # same neutral shape, which asks for the figure and asserts nothing about it.
    return _spaced(f"{dimension}：{BLANK}")


def candidates_for(
    playbook: RolePlaybook,
    *,
    limit: int = 4,
) -> list[MetricCandidate]:
    """The ways this role's work is legitimately measured, as fillable skeletons.

    Returns at most `limit`, in the playbook's own order — that order is already
    "strongest evidence first" for the family, and re-ranking it here would create a
    second opinion about the same question.
    """
    out: list[MetricCandidate] = []
    seen: set[str] = set()
    for raw in playbook.outcome_metrics:
        dimension = _canonical(raw)
        if not dimension or dimension in seen:
            continue
        seen.add(dimension)
        unit, direction = _classify(dimension)
        out.append(
            MetricCandidate(
                dimension=dimension,
                unit=unit,
                direction=direction,
                skeleton=_skeleton(dimension, direction),
            )
        )
        if len(out) >= limit:
            break
    return out


#: Gap kinds whose answer *is* a figure. Offering skeletons on the others would be
#: actively misleading: `weak_ownership` asks how far the user's ownership went
#: (「独立负责 / 带人做 / 配合」) and `empty_experience` asks what the role even was.
#: Putting 「P99 延迟从 ___ 降到 ___」under those tells the user we want a number when
#: we want a sentence, and the kinds already carry their own `examples`.
_QUANTIFIABLE_KINDS = frozenset({"missing_outcome", "unquantified_outcome", "vague_quantity"})


def candidates_for_kind(
    playbook: RolePlaybook,
    kind: str,
    *,
    limit: int = 4,
) -> list[MetricCandidate]:
    """Skeletons for a gap of this kind, or none when a number is not the answer.

    Gated on `kind` rather than on `quantification_optional`: a legal or HR role still
    has figures worth clicking when the question asked for one, and the playbook already
    decides whether such a question gets asked at all.
    """
    if kind not in _QUANTIFIABLE_KINDS:
        return []
    return candidates_for(playbook, limit=limit)


def candidates_payload(playbook: RolePlaybook, *, limit: int = 4) -> list[dict[str, Any]]:
    return [c.to_dict() for c in candidates_for(playbook, limit=limit)]
