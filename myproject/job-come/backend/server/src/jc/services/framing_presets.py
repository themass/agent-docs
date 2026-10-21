"""Framing presets: the user-selectable angle a resume is written from.

Why this exists
---------------
The writing methodology (Action + Object + Outcome, verb strength, the quantification
ladder) decides *how a sentence is built*. It does not decide **which true thing about
the work to lead with** — and that choice is what actually makes a recruiter stop on a
bullet.

A single piece of work supports several honest framings at once:

    源材料：把订单服务从单体拆成 6 个微服务，耗时三个月，期间没有线上事故。

    强调规模   —— 拆分覆盖 6 条业务线、日均 1200 万单的订单主链路
    强调主导   —— 独立出方案、定边界、推动三个团队按季度交付
    强调结果   —— 迁移期间零线上事故，发布耗时从 40 分钟降到 6 分钟
    强调深度   —— 为跨服务一致性设计补偿事务，放弃了分布式事务方案及其原因

All four are true. Which one belongs on the page depends on the job and on what the
candidate wants to be hired as, and **the candidate is the only one who knows that**.
Before this module the choice was made implicitly inside the prompt and the user had no
way to see it, let alone change it — which is why the product felt like it had one
opaque "optimize" button and very few levers.

Hard boundary
-------------
A preset may only change **which supported fact is foregrounded and in what words**. It
can never add a fact, upgrade a verb past what the source supports, or introduce a
number. `ownership` does not mean writing 主导 where the source says 参与; it means
surfacing the decisions the source *does* record. The writer prompt and the reviewer
both re-state this, and the reviewer still blocks unsupported claims regardless of the
preset in force.

Role defaults live here rather than in `role_families.py` on purpose: they are a
product-opinion about what a recruiter in that family reads for, and keeping all 16 in
one table makes that opinion reviewable in one place instead of scattered across the
playbooks.
"""

from __future__ import annotations

from dataclasses import dataclass

from jc.domain.role_families import GENERAL

#: How many angles a user may apply at once. Two is deliberate: one angle reads as a
#: one-note resume, and four means no angle at all — everything is emphasised, so
#: nothing is.
MAX_EMPHASES = 2


@dataclass(frozen=True, slots=True)
class FramingPreset:
    id: str
    label: str
    #: Shown to the user next to the toggle.
    hint: str
    #: Injected into the writer prompt. Written as an instruction to the writer.
    instruction: str

    def as_prompt_line(self) -> str:
        return f"- **{self.id}** ({self.label}): {self.instruction}"


PRESETS: tuple[FramingPreset, ...] = (
    FramingPreset(
        id="scope",
        label="强调规模与影响面",
        hint="突出你的工作覆盖了多大的系统、多少业务线、多少用户。",
        instruction=(
            "Lead with the size of the thing acted on: traffic, data volume, user count, "
            "number of business lines, budget, headcount, geography. Use only scale "
            "figures present in the source; if a bullet has no scale in the source, write "
            "it without one rather than estimating."
        ),
    ),
    FramingPreset(
        id="ownership",
        label="强调主导与决策权",
        hint="突出你定方案、做取舍、推动他人，而不是执行既定任务。",
        instruction=(
            "Foreground the decisions the source records the candidate making: what they "
            "chose, what they rejected and why, who they had to bring along. Do not "
            "upgrade the source's verb — if the source says 参与, surface the decision "
            "that person did own inside that work instead of claiming they led it."
        ),
    ),
    FramingPreset(
        id="outcome",
        label="强调结果与指标",
        hint="把成果放在句子前半部分，让招聘方先看到变化。",
        instruction=(
            "Put the result in the first half of the bullet, then how it was achieved. "
            "Prefer before/after pairs over bare percentages. Where the source has no "
            "result, state Action + Object precisely and do not reorder for emphasis."
        ),
    ),
    FramingPreset(
        id="depth",
        label="强调专业深度",
        hint="突出难点、取舍与方法，适合技术/专业评审型面试官。",
        instruction=(
            "Name the hard part: the constraint, the failure mode, the trade-off, the "
            "method chosen over an obvious alternative. This is the angle that survives "
            "a deep-dive interview, so every detail must come from the source."
        ),
    ),
    FramingPreset(
        id="collaboration",
        label="强调跨团队推动",
        hint="突出你协调了多少方、克服了什么阻力，适合偏协同的岗位。",
        instruction=(
            "Make the collaboration surface visible: which functions, how many teams, "
            "what resistance or misalignment had to be resolved. State the candidate's "
            "actual role in it (executed / drove / decided) as the source describes it."
        ),
    ),
    FramingPreset(
        id="jd_fit",
        label="对齐目标岗位用词",
        hint="在不新增技能的前提下，换用目标岗位 JD 里的说法。",
        instruction=(
            "Re-word supported facts into the target job's own vocabulary and promote the "
            "bullets that answer its stated requirements. Never add a skill, tool or "
            "domain because the job asks for it — missing stays missing."
        ),
    ),
)

_BY_ID = {p.id: p for p in PRESETS}

# What a recruiter in each family reads for first. Used as the default selection, and
# shown to the user as a recommendation they are free to override.
_RECOMMENDED: dict[str, tuple[str, ...]] = {
    "backend": ("scope", "depth"),
    "frontend": ("outcome", "depth"),
    "ios": ("outcome", "depth"),
    "devops": ("outcome", "scope"),
    "data": ("outcome", "depth"),
    "pm": ("outcome", "ownership"),
    "design": ("depth", "collaboration"),
    "operations": ("outcome", "scope"),
    "marketing": ("outcome", "scope"),
    "sales": ("outcome", "ownership"),
    "customer_success": ("outcome", "collaboration"),
    "hr": ("scope", "collaboration"),
    "finance": ("depth", "ownership"),
    "legal": ("depth", "collaboration"),
    "management": ("ownership", "scope"),
    GENERAL: ("outcome", "scope"),
}


def get_preset(preset_id: str | None) -> FramingPreset | None:
    if not preset_id:
        return None
    return _BY_ID.get(str(preset_id).strip().lower())


def recommended_for(role_family: str | None) -> list[str]:
    """Default angles for a family, falling back to the neutral pair."""
    key = (role_family or "").strip().lower()
    return list(_RECOMMENDED.get(key, _RECOMMENDED[GENERAL]))


def resolve_emphases(
    selected: list[str] | None,
    *,
    role_family: str | None,
) -> list[str]:
    """Settle which angles apply to this document.

    An empty or all-unknown selection falls back to the family recommendation rather
    than to "no angle": the writer always had an implicit emphasis, and defaulting to
    the role's own reading order is strictly better than defaulting to whatever the
    model felt like. Order is preserved so the user's first pick stays primary, and
    the list is capped because emphasising everything emphasises nothing.
    """
    out: list[str] = []
    for raw in selected or []:
        pid = str(raw).strip().lower()
        if pid in _BY_ID and pid not in out:
            out.append(pid)
        if len(out) >= MAX_EMPHASES:
            break
    return out or recommended_for(role_family)


def as_prompt_block(emphases: list[str]) -> str:
    """Render the chosen angles for the writer prompt, strongest first."""
    lines: list[str] = []
    for idx, pid in enumerate(emphases):
        preset = _BY_ID.get(pid)
        if preset is None:
            continue
        rank = "Primary" if idx == 0 else "Secondary"
        lines.append(f"{rank}: {preset.as_prompt_line()[2:]}")
    if not lines:
        return ""
    return "\n".join(
        [
            "These angles decide which supported fact leads each bullet. They never "
            "license a new fact, a stronger verb than the source supports, or a number.",
            *lines,
        ]
    )


def catalogue(role_family: str | None = None) -> list[dict[str, object]]:
    """Preset catalogue for the UI, flagging this role's recommendations."""
    rec = set(recommended_for(role_family))
    return [
        {
            "id": p.id,
            "label": p.label,
            "hint": p.hint,
            "recommended": p.id in rec,
        }
        for p in PRESETS
    ]
