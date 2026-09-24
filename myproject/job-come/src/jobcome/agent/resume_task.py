"""Bind resume-coach turns to the active profile."""

from __future__ import annotations

from jobcome.schemas.profile_payload import ProfilePayload

_DIGEST_CAP = 6_000


def build_profile_digest(payload: ProfilePayload, *, max_highlights: int = 8) -> str:
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
        for j, raw in enumerate(highlights[:max_highlights]):
            text = " ".join(raw.split())
            lines.append(f"  highlights[{j}]: {text[:240]}")
        extra = len(highlights) - max_highlights
        if extra > 0:
            lines.append(f"  …另有 {extra} 条")
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


def wrap_resume_coach_message(
    user_text: str,
    *,
    profile_id: str | None,
    digest: str,
) -> str:
    bound = profile_id or "（未绑定档案，请提示用户先上传/选择简历）"
    digest_block = digest.strip() or "（未能加载档案摘要，请调用 jobcome_profile_get）"
    return (
        "【简历优化任务】\n"
        f"你正在服务已打开的档案 profile_id={bound}。不要自我介绍，不要调用 ask_clarification。\n"
        "用户原话：\n"
        f"{user_text.strip()}\n\n"
        "当前档案摘要（只基于这些事实改写）：\n"
        f"{digest_block}\n\n"
        "若用户在改某一段：写出建议要点并在意图明确时 jobcome_profile_patch。"
    )
