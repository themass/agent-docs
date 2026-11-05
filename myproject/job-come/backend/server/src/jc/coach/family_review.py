"""One sheet per line of work, for the people who know that work to read.

The interviewer and the reviewer are told where to probe for each family
(`RolePlaybook.as_interview_block`). Those lists were drafted by us, not by people who do the work,
and code cannot tell whether a follow-up direction is what a good interviewer in that field asks.
This turns the lists into a document a domain expert can mark up, taken from the code so the
sheet cannot drift from what the model is told.

    python -m jc.coach.family_review > docs/operations/REVIEW-ROLE-FAMILIES.md
"""

from __future__ import annotations

from jc.domain.role_families import PLAYBOOKS, RolePlaybook

_QUESTIONS = (
    "这三条追问方向，是这个行业面试里真会问的吗？有没有该问却没写的？",
    "有没有哪一条在你们行业里是外行才会问的、或者问了反而显得不专业？",
    "成果指标和工作对象：哪些不该出现，哪些缺了？",
    "按初级、中级、高级、专家，问法应该怎么变？",
)


def _bullets(items: tuple[str, ...]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- （无）"


def render_family(playbook: RolePlaybook) -> str:
    lines = [
        f"## {playbook.label}（`{playbook.id}`）",
        "",
        "**追问方向**（面试官据此追问，评审据此判断回答是否站得住）",
        "",
        _bullets(playbook.probe_angles),
        "",
        "**成果通常这样衡量**（只当作追问的方向，不替候选人编数字）",
        "",
        "、".join(playbook.outcome_metrics) or "（无）",
        "",
        "**工作的对象通常是**",
        "",
        "、".join(playbook.object_nouns) or "（无）",
        "",
        "**审校意见**",
        "",
        "| 问题 | 你的意见 |",
        "|---|---|",
        *(f"| {question} | |" for question in _QUESTIONS),
        "",
    ]
    return "\n".join(lines)


def render_review_sheet() -> str:
    families = [p for p in PLAYBOOKS.values() if p.id != "general"]
    head = [
        "# REVIEW-ROLE-FAMILIES：各岗位族的面试追问方向，请行业内的人审校",
        "",
        "- **生成方式**：由 `python -m jc.coach.family_review` 从代码生成，不要手改本文件；"
        "审校意见写在表里的“你的意见”列，或另存一份。",
        "- **为什么需要**：下面的内容是我们起草的，没有行业专业人士看过。"
        "自动测试只能查结构，查不出“这条追问在行业里是否问到点上”。",
        "- **怎么用**：每个岗位族一节，发给做这一行的人，让对方填最后的表。"
        "不要求逐条改写，指出“这条不对”“缺了这条”就够了。",
        "- **没覆盖的**：`general`（岗位族无法判定时用的中性族）不带任何追问方向，所以不在这里。"
        "题库、评分锚点的行业差异也不在这里。",
        "",
    ]
    return "\n".join(head) + "\n" + "\n".join(render_family(p) for p in families)


if __name__ == "__main__":  # pragma: no cover
    print(render_review_sheet())
