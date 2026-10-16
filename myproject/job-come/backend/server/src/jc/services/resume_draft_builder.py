"""Build ResumeDraft sections from ProfilePayload."""

from __future__ import annotations

from typing import Any

from jc.models.enums import ElevationLevel
from jc.resume_locale import is_english_locale
from jc.schemas.profile_payload import ProfilePayload
from jc.services.elevation_techniques import annotate_elevation_map
from jc.services.profile_i18n import overlay_profile
from jc.services.role_families import get_playbook, playbook_for_title


class ResumeDraftBuilder:
    def build(
        self,
        profile: ProfilePayload,
        *,
        elevation_level: str,
        locale: str = "zh-CN",
        job_keywords: list[str] | None = None,
        job_title: str | None = None,
        role_family: str | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        profile = overlay_profile(profile, locale)
        playbook = (
            get_playbook(role_family)
            if role_family
            else playbook_for_title(
                job_title,
                profile.experiences[0].title if profile.experiences else None,
            )
        )
        contact_parts = [
            p
            for p in [
                profile.contact.location,
                profile.contact.email,
                profile.contact.phone,
            ]
            if p
        ]
        en = is_english_locale(locale)
        pending_name = "Name pending" if en else "姓名待填"
        default_headline = "Candidate" if en else "求职者"
        pending_bullet = "(Add experience highlights)" if en else "（待补充经历要点）"
        present = "Present" if en else "至今"
        skills_title = "Skills" if en else "技能"
        header = {
            "name": profile.contact.name or pending_name,
            "headline": profile.experiences[0].title if profile.experiences else default_headline,
            "contact_line": " · ".join(contact_parts),
        }
        experience_blocks = []
        elevation_map: list[dict[str, Any]] = []
        for idx, exp in enumerate(profile.experiences):
            bullets: list[str] = []
            for b_idx, raw in enumerate(exp.highlights or [pending_bullet]):
                written = self._elevate_bullet(raw, elevation_level, english=en)
                bullets.append(written)
                if written != raw:
                    elevation_map.append(
                        {
                            "field_path": f"experience_blocks[{idx}].bullets[{b_idx}]",
                            "source_text": raw,
                            "written_text": written,
                            "needs_defense": elevation_level == ElevationLevel.ELEVATED,
                        }
                    )
            date_range = exp.start_date
            if exp.end_date:
                date_range = f"{exp.start_date} – {exp.end_date}"
            elif exp.start_date:
                date_range = f"{exp.start_date} – {present}"
            experience_blocks.append(
                {
                    "id": exp.id,
                    "company": exp.company,
                    "title": exp.title,
                    "date_range": date_range,
                    "location": exp.location,
                    "bullets": bullets,
                }
            )
        education_blocks = [
            {
                "id": edu.id,
                "school": edu.school,
                "degree_line": " · ".join(filter(None, [edu.degree, edu.major])),
                "date_range": " – ".join(filter(None, [edu.start_date, edu.end_date])) or "",
            }
            for edu in profile.education
        ]
        project_blocks = []
        for p_idx, proj in enumerate(profile.projects):
            # `highlights` is where project accomplishments live. `description` is only the
            # one-line overview; when a project has no highlights, promote it to a bullet so the
            # entry does not collapse to a bare title and read as work with no result.
            raw_bullets = list(proj.highlights or [])
            note = proj.description
            if not raw_bullets and note:
                raw_bullets = [note]
                note = None
            proj_range = proj.start_date
            if proj.start_date and proj.end_date:
                proj_range = f"{proj.start_date} – {proj.end_date}"
            elif proj.start_date:
                proj_range = f"{proj.start_date} – {present}"
            proj_bullets: list[str] = []
            for b_idx, raw in enumerate(raw_bullets):
                written = self._elevate_bullet(raw, elevation_level, english=en)
                proj_bullets.append(written)
                if written != raw:
                    # Project rewrites are reviewable too: the user must be able to see and
                    # defend every line the document shows, not only the experience bullets.
                    elevation_map.append(
                        {
                            "field_path": f"project_blocks[{p_idx}].bullets[{b_idx}]",
                            "source_text": raw,
                            "written_text": written,
                            "needs_defense": elevation_level == ElevationLevel.ELEVATED,
                        }
                    )
            project_blocks.append(
                {
                    "id": proj.id,
                    "name": proj.name,
                    "role": proj.role,
                    "date_range": proj_range,
                    "description": note,
                    "bullets": proj_bullets,
                }
            )
        skills = ", ".join(s.name for s in profile.skills) if profile.skills else ""
        summary = profile.summary or ""
        if job_title and job_title not in summary:
            prefix = f"Target role: {job_title}. " if en else f"求职方向：{job_title}。"
            summary = f"{prefix}{summary}".strip()
        if job_keywords:
            kw_note = (", ".join(job_keywords[:8]) if en else "、".join(job_keywords[:8]))
            if kw_note and kw_note not in skills:
                if en:
                    skills = f"{skills}; keywords: {kw_note}" if skills else f"Keywords: {kw_note}"
                else:
                    skills = (
                        f"{skills}；岗位关键词：{kw_note}" if skills else f"岗位关键词：{kw_note}"
                    )
        sections: dict[str, Any] = {
            "locale": locale,
            "header": header,
            "summary": summary,
            "experience_blocks": experience_blocks,
            "education_blocks": education_blocks,
            "skills_block": {"title": skills_title, "content": skills},
            "project_blocks": project_blocks,
            # Reading order is role-dependent: a design recruiter opens with the portfolio,
            # a sales recruiter wants numbers before tooling.
            "section_order": list(playbook.section_priority),
            "role_family": playbook.id,
        }
        # Keep the deterministic fallback path consistent with the LLM path: the UI
        # always receives technique labels, whether or not the model was reachable.
        return sections, annotate_elevation_map(
            elevation_map, job_keywords=job_keywords, role_family=playbook.id
        )

    # Verbs that already carry ownership; nothing to upgrade.
    _STRONG_PREFIXES = ("主导", "负责", "牵头", "搭建", "设计", "优化", "重构", "推动", "治理")
    # Weak openers that understate what the person did without adding information.
    _WEAK_PREFIXES = ("参与", "协助", "配合", "参加")
    # Vague openers that carry no meaning; dropping them avoids `负责做…` phrasing.
    _VAGUE_OPENERS = ("做了", "做过", "做", "搞", "弄")
    # Filler that pads a bullet without saying anything verifiable.
    _FILLER_SUFFIXES = ("相关工作", "相关事宜", "等工作", "方面的工作", "的工作内容")

    @classmethod
    def _elevate_bullet(cls, text: str, level: str, *, english: bool = False) -> str:
        """Rule-based fallback used when the writing model is unavailable.

        This path must stay strictly truth-preserving: it may only re-word what the
        source already says. It never appends an outcome, a metric or a scope claim,
        because there is no evidence behind one — a fabricated result is a blocking
        reviewer error and would also fail the candidate in an interview.
        """
        body = text.strip()
        if not body or level == ElevationLevel.CONSERVATIVE or english:
            return text

        for filler in cls._FILLER_SUFFIXES:
            if body.endswith(filler) and len(body) > len(filler) + 2:
                body = body[: -len(filler)].rstrip("的，, ")
                break

        for vague in cls._VAGUE_OPENERS:
            if body.startswith(vague) and len(body) > len(vague) + 1:
                body = body[len(vague):].lstrip("，, ")
                break

        if body.startswith(cls._STRONG_PREFIXES):
            return body

        if level == ElevationLevel.ELEVATED:
            # Only a weak opener may be lifted, and only to `负责` — claiming `主导`
            # requires evidence the structured profile does not carry.
            for weak in cls._WEAK_PREFIXES:
                if body.startswith(weak):
                    return f"负责{body[len(weak):].lstrip('，, ')}"
            return f"负责{body.lstrip('，, ')}"

        if body.startswith(cls._WEAK_PREFIXES + ("完成",)):
            return body
        return f"负责{body.lstrip('，, ')}"
