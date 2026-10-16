"""Bind resume-coach turns to the active profile."""

from __future__ import annotations

from jc.schemas.agent import AgentUiContext
from jc.schemas.profile_payload import ProfilePayload

_DIGEST_CAP = 12_000


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


def wrap_resume_coach_message(
    user_text: str,
    *,
    profile_id: str | None,
    digest: str,
    ui_context: AgentUiContext | None = None,
) -> str:
    bound = profile_id or "（未绑定档案，请提示用户先上传/选择简历）"
    digest_block = digest.strip() or "（未能加载档案摘要，请调用 jc_profile_get）"
    ui_block = format_ui_context(ui_context)
    ui_section = f"{ui_block}\n\n" if ui_block else ""
    return (
        "【简历优化任务】\n"
        f"你正在服务已打开的档案 profile_id={bound}。不要自我介绍，不要调用 ask_clarification。\n"
        f"{ui_section}"
        "用户原话：\n"
        f"{user_text.strip()}\n\n"
        "当前档案摘要（只基于这些事实改写）：\n"
        f"{digest_block}\n\n"
        "若用户在改某一段：写出建议要点并在意图明确时 jc_profile_patch。"
    )
