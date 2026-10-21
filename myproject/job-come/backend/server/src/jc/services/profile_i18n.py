"""Project and overlay Profile i18n packs (display fields only)."""

from __future__ import annotations

from jc.resume_locale import TRACK_EN, TRACK_ZH, detect_source_locale, normalize_track
from jc.schemas.profile_payload import (
    ProfileI18nEducation,
    ProfileI18nExperience,
    ProfileI18nPack,
    ProfileI18nProject,
    ProfilePayload,
)


def profile_display_text(profile: ProfilePayload) -> str:
    parts: list[str] = [profile.summary or ""]
    for exp in profile.experiences:
        parts.extend([exp.title, exp.company, *(exp.highlights or [])])
    for edu in profile.education:
        parts.extend([edu.school, edu.degree or "", edu.major or ""])
    for proj in profile.projects:
        parts.extend([proj.name, proj.description or "", *(proj.highlights or [])])
    return "\n".join(p for p in parts if p)


def detect_profile_source_locale(profile: ProfilePayload) -> str:
    if profile.meta.source_locale:
        return normalize_track(profile.meta.source_locale)
    return detect_source_locale(profile_display_text(profile))


def project_i18n_pack(profile: ProfilePayload) -> ProfileI18nPack:
    headline = profile.experiences[0].title if profile.experiences else ""
    return ProfileI18nPack(
        summary=profile.summary,
        headline=headline,
        experiences=[
            ProfileI18nExperience(id=exp.id, title=exp.title, highlights=list(exp.highlights or []))
            for exp in profile.experiences
        ],
        education=[
            ProfileI18nEducation(
                id=edu.id,
                degree_line=" · ".join(filter(None, [edu.degree, edu.major])) or None,
            )
            for edu in profile.education
        ],
        projects=[
            ProfileI18nProject(
                id=proj.id,
                name=proj.name,
                role=proj.role,
                description=proj.description,
                highlights=list(proj.highlights or []),
            )
            for proj in profile.projects
        ],
        skills_line=", ".join(s.name for s in profile.skills) if profile.skills else None,
    )


def align_i18n_pack(profile: ProfilePayload, pack: ProfileI18nPack) -> ProfileI18nPack:
    """Keep experience/education ids in lockstep with the source profile."""
    by_exp = {item.id: item for item in pack.experiences}
    by_edu = {item.id: item for item in pack.education}
    by_proj = {item.id: item for item in pack.projects}
    experiences: list[ProfileI18nExperience] = []
    for exp in profile.experiences:
        overlay = by_exp.get(exp.id)
        experiences.append(
            ProfileI18nExperience(
                id=exp.id,
                title=(overlay.title if overlay and overlay.title else exp.title),
                highlights=(
                    list(overlay.highlights)
                    if overlay and overlay.highlights
                    else list(exp.highlights or [])
                ),
            )
        )
    education: list[ProfileI18nEducation] = []
    for edu in profile.education:
        overlay = by_edu.get(edu.id)
        source_line = " · ".join(filter(None, [edu.degree, edu.major])) or None
        education.append(
            ProfileI18nEducation(
                id=edu.id,
                degree_line=(
                overlay.degree_line if overlay and overlay.degree_line else source_line
            ),
            )
        )
    projects: list[ProfileI18nProject] = []
    for proj in profile.projects:
        overlay = by_proj.get(proj.id)
        projects.append(
            ProfileI18nProject(
                id=proj.id,
                name=(overlay.name if overlay and overlay.name else proj.name),
                role=(overlay.role if overlay and overlay.role else proj.role),
                description=(
                    overlay.description
                    if overlay and overlay.description
                    else proj.description
                ),
                highlights=(
                    list(overlay.highlights)
                    if overlay and overlay.highlights
                    else list(proj.highlights or [])
                ),
            )
        )
    return ProfileI18nPack(
        summary=pack.summary if pack.summary is not None else profile.summary,
        headline=pack.headline
        or (profile.experiences[0].title if profile.experiences else None),
        experiences=experiences,
        education=education,
        projects=projects,
        skills_line=pack.skills_line
        or (", ".join(s.name for s in profile.skills) if profile.skills else None),
    )


def overlay_profile(profile: ProfilePayload, locale: str) -> ProfilePayload:
    """Apply i18n display fields; company/dates/contact stay on the source profile."""
    track = TRACK_EN if normalize_track(locale) == TRACK_EN else TRACK_ZH
    # Source fields are authoritative; an old translated cache must not undo edits.
    if (
        track == detect_profile_source_locale(profile)
        or profile.meta.i18n_status.get(track) == "stale"
    ):
        return profile
    pack = profile.i18n.get(track)
    if pack is None:
        return profile
    pack = align_i18n_pack(profile, pack)
    data = profile.model_dump()
    if pack.summary is not None:
        data["summary"] = pack.summary
    exp_by_id = {item.id: item for item in pack.experiences}
    for exp in data.get("experiences") or []:
        overlay = exp_by_id.get(exp["id"])
        if overlay is None:
            continue
        if overlay.title:
            exp["title"] = overlay.title
        if overlay.highlights:
            exp["highlights"] = overlay.highlights
    edu_by_id = {item.id: item for item in pack.education}
    for edu in data.get("education") or []:
        overlay = edu_by_id.get(edu["id"])
        if overlay and overlay.degree_line:
            edu["degree"] = overlay.degree_line
            edu["major"] = None
    proj_by_id = {item.id: item for item in pack.projects}
    for proj in data.get("projects") or []:
        overlay = proj_by_id.get(proj["id"])
        if overlay is None:
            continue
        if overlay.name:
            proj["name"] = overlay.name
        if overlay.role:
            proj["role"] = overlay.role
        if overlay.description:
            proj["description"] = overlay.description
        if overlay.highlights:
            proj["highlights"] = overlay.highlights
    return ProfilePayload.model_validate(data)
