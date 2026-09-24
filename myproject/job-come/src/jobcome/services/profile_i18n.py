"""Project and overlay Profile i18n packs (display fields only)."""

from __future__ import annotations

from jobcome.resume_locale import TRACK_EN, TRACK_ZH, detect_source_locale, normalize_track
from jobcome.schemas.profile_payload import (
    ProfileI18nEducation,
    ProfileI18nExperience,
    ProfileI18nPack,
    ProfilePayload,
)


def profile_display_text(profile: ProfilePayload) -> str:
    parts: list[str] = [profile.summary or ""]
    for exp in profile.experiences:
        parts.extend([exp.title, exp.company, *(exp.highlights or [])])
    for edu in profile.education:
        parts.extend([edu.school, edu.degree or "", edu.major or ""])
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
        skills_line=", ".join(s.name for s in profile.skills) if profile.skills else None,
    )


def align_i18n_pack(profile: ProfilePayload, pack: ProfileI18nPack) -> ProfileI18nPack:
    """Keep experience/education ids in lockstep with the source profile."""
    by_exp = {item.id: item for item in pack.experiences}
    by_edu = {item.id: item for item in pack.education}
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
                degree_line=(overlay.degree_line if overlay and overlay.degree_line else source_line),
            )
        )
    return ProfileI18nPack(
        summary=pack.summary if pack.summary is not None else profile.summary,
        headline=pack.headline
        or (profile.experiences[0].title if profile.experiences else None),
        experiences=experiences,
        education=education,
        skills_line=pack.skills_line
        or (", ".join(s.name for s in profile.skills) if profile.skills else None),
    )


def overlay_profile(profile: ProfilePayload, locale: str) -> ProfilePayload:
    """Apply i18n display fields; company/dates/contact stay on the source profile."""
    track = TRACK_EN if normalize_track(locale) == TRACK_EN else TRACK_ZH
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
    return ProfilePayload.model_validate(data)
