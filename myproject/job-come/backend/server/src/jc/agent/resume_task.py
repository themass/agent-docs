"""Bind resume-coach turns to the active profile."""

from __future__ import annotations

from jc.domain.role_families import resolve_role_family
from jc.schemas.agent import AgentUiContext
from jc.schemas.profile_payload import ProfilePayload
from jc.services.profile_intake import build_intake_plan

_DIGEST_CAP = 12_000

#: Methodology for the conversational path. The agent cannot read a SKILL.md itself:
#: DeerFlow injects only a skill's name and location, and the body is fetched by the
#: model calling `read_file` — a tool V1 deliberately does not grant. So the host
#: composes the methodology and sends it with the turn. Without this the coach had
#: the resume-coach rules and nothing else: no bullet method, no role-family
#: standard, which is why "丰富一点" produced longer sentences rather than the
#: constraint / method / scope / outcome material the profile already contained.
_COACH_SKILL_ID = "resume-coach"

#: Methodology for a profile that cannot produce a resume yet. Editing methodology is
#: the wrong tool there: "rewrite this bullet to lead with the outcome" has nothing to
#: operate on when there are no bullets, and the coach would fill the gap with template
#: prose — which reads like a resume and contains none of the user's career.
#:
#: Selected on `can_generate` rather than on `mode`, because that is the same signal the
#: intake panel shows the user. A profile the UI calls 「还差材料」 and a coach that acts
#: as though the draft just needs polish are the two halves of one bug.
_INTERVIEW_SKILL_ID = "profile-interview"


def build_profile_digest(payload: ProfilePayload, *, max_highlights: int | None = None) -> str:
    """Render the profile the coach is editing.

    `max_highlights` defaults to no limit on purpose. The coach is asked things like
    「这段再丰富一些」, and it can only work with what this digest shows — a capped digest made the
    agent propose rewrites against a truncated career and silently ignore the rest.
    """
    lines: list[str] = []
    name = (payload.contact.name or "").strip()
    if name:
        lines.append(f"姓名：{name}")
    if payload.summary:
        lines.append(f"摘要：{payload.summary.strip()[:400]}")
    if not payload.experiences:
        lines.append("（尚无工作经历）")
    for i, exp in enumerate(payload.experiences):
        end = exp.end_date or "至今"
        loc = f" · {exp.location}" if exp.location else ""
        lines.append(f"experiences[{i}] {exp.company} · {exp.title} · {exp.start_date}–{end}{loc}")
        highlights = exp.highlights or []
        if not highlights:
            lines.append("  highlights: （空）")
        shown = highlights if max_highlights is None else highlights[:max_highlights]
        for j, raw in enumerate(shown):
            text = " ".join(raw.split())
            lines.append(f"  highlights[{j}]: {text[:240]}")
        extra = len(highlights) - len(shown)
        if extra > 0:
            lines.append(f"  …另有 {extra} 条")
    for i, proj in enumerate(payload.projects):
        role = f" · {proj.role}" if proj.role else ""
        lines.append(f"projects[{i}] {proj.name}{role}")
        if proj.description:
            lines.append(f"  description: {' '.join(proj.description.split())[:240]}")
        proj_highlights = proj.highlights or []
        shown_proj = (
            proj_highlights if max_highlights is None else proj_highlights[:max_highlights]
        )
        for j, raw in enumerate(shown_proj):
            lines.append(f"  highlights[{j}]: {' '.join(raw.split())[:240]}")
        extra_proj = len(proj_highlights) - len(shown_proj)
        if extra_proj > 0:
            lines.append(f"  …另有 {extra_proj} 条")
    for i, edu in enumerate(payload.education[:4]):
        lines.append(
            f"education[{i}] {edu.school} · {edu.degree or ''} {edu.major or ''}".strip()
        )
    skills = "、".join(s.name for s in payload.skills[:20] if s.name)
    if skills:
        lines.append(f"技能：{skills}")
    digest = "\n".join(lines)
    if len(digest) > _DIGEST_CAP:
        return digest[: _DIGEST_CAP - 1] + "…"
    return digest


def format_ui_context(ctx: AgentUiContext | None) -> str:
    if ctx is None:
        return ""
    lines = [f"界面：page={ctx.page} step={ctx.step}"]
    focus = ctx.focus
    if focus is None:
        lines.append("用户未点选具体字段；按原话在档案里定位。")
        return "\n".join(lines)
    excerpt = (focus.excerpt or "").strip()
    lines.append(
        f"用户当前指向：path={focus.path} kind={focus.kind} label={focus.label or '（无标题）'}"
    )
    if excerpt:
        lines.append(f"指向摘录：{excerpt[:240]}")
    lines.append("若用户说「这块/这段/这条」，优先改上述 path，不要再问改哪一段。")
    return "\n".join(lines)


def coach_skill_for(payload: ProfilePayload | None) -> str:
    """Which methodology this turn needs: edit an existing resume, or build one.

    The split is on whether the profile can produce a document at all. A user whose
    profile is empty, a skeleton, or years out of date does not need bullet-level
    rewriting advice — there is nothing to rewrite, and a coach given editing
    methodology answers 「帮我改改」 by generating plausible resume prose that contains
    none of their actual career.

    `can_generate` is the same signal the intake panel renders, so the sidebar and the
    panel cannot disagree about whether this profile still needs material.
    """
    if payload is None:
        return _COACH_SKILL_ID
    if build_intake_plan(payload).can_generate:
        return _COACH_SKILL_ID
    return _INTERVIEW_SKILL_ID


def coach_role_family_for(payload: ProfilePayload | None) -> str | None:
    """Which role family's methodology this profile's coach turn should use.

    The family is inferred from the profile's own titles rather than a target job:
    the coach edits the career the user has, and a JD may not be selected at all.
    An unrecognised title yields `None` -> the neutral playbook, which is correct —
    guessing a family wrong means coaching against the wrong audience.

    Returns the family *id*, not composed prompt text. The methodology itself is
    rendered into the system layer by `JCProductRulesMiddleware` (see
    `jc.agent.standing_instructions`); this function's only job is to pick which
    one applies, because that is the one part of the decision that needs the
    profile and the middleware does not have it.
    """
    if payload is None:
        return None
    return resolve_role_family(
        override=payload.preferences.role_family,
        profile_titles=tuple(exp.title for exp in payload.experiences[:3]),
    )


def coach_shortfall_for(payload: ProfilePayload | None) -> tuple[str, ...]:
    """What this profile still needs before a resume can be generated, in the user's words.

    Taken from the intake plan so the sidebar quotes the same shortfall the intake panel
    shows. The coach needs it for a reason the guidance cannot supply: methodology says
    *how* to ask, while this says *what is still missing on this particular profile* —
    without it the model has to infer the gap from the digest, and an empty digest reads
    the same as a failed profile load.
    """
    if payload is None:
        return ()
    plan = build_intake_plan(payload)
    return tuple(plan.blocking)


def wrap_resume_coach_message(
    user_text: str,
    *,
    profile_id: str | None,
    digest: str,
    ui_context: AgentUiContext | None = None,
    interview: bool = False,
    shortfall: tuple[str, ...] = (),
    include_digest: bool = True,
) -> str:
    """User words plus a small live index/focus; policy stays in the system layer.

    The caller supplies a bounded index from turn_profile_context, never a complete
    resume. Detailed facts and large constraints are read by section/field tool.
    include_digest=False remains compatible with older pointer-only callers.
    """
    bound = profile_id or "（未绑定档案，请提示用户先上传/选择简历）"
    ui_block = format_ui_context(ui_context)
    ui_section = f"{ui_block}\n\n" if ui_block else ""

    if interview:
        shortfall_block = (
            "还差的材料：\n" + "\n".join(f"- {item}" for item in shortfall) + "\n\n"
            if shortfall
            else ""
        )
        digest_block = digest.strip() or "（档案目前还是空的）"
        return (
            f"profile_id={bound}\n"
            f"{ui_section}"
            f"{shortfall_block}"
            "档案现有内容：\n"
            f"{digest_block}\n\n"
            f"{user_text.strip()}"
        )

    if include_digest:
        digest_block = digest.strip() or "（未能加载档案摘要，请调用 jc_profile_get）"
        digest_section = f"当前档案索引/选中字段（不是全部事实，先分区读取再改写）：\n{digest_block}\n\n"
    else:
        digest_section = (
            "（档案摘要已在本会话开头给过。若上一轮确认过修改，先调用 jc_profile_get"
            "读取最新档案，不要凭记忆改写。）\n\n"
        )

    # The user's own words go last, closest to where the model starts writing.
    # Everything above is addressing context; this is the request.
    return (
        f"profile_id={bound}\n"
        f"{ui_section}"
        f"{digest_section}"
        f"{user_text.strip()}"
    )
