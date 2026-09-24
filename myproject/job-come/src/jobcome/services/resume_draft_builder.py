"""Build ResumeDraft sections from ProfilePayload."""

from __future__ import annotations

from typing import Any

from jobcome.models.enums import ElevationLevel
from jobcome.resume_locale import is_english_locale
from jobcome.schemas.profile_payload import ProfilePayload
from jobcome.services.profile_i18n import overlay_profile


class ResumeDraftBuilder:
    def build(
        self,
        profile: ProfilePayload,
        *,
        elevation_level: str,
        locale: str = "zh-CN",
        job_keywords: list[str] | None = None,
        job_title: str | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        profile = overlay_profile(profile, locale)
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
                    skills = f"{skills}；岗位关键词：{kw_note}" if skills else f"岗位关键词：{kw_note}"
        sections: dict[str, Any] = {
            "locale": locale,
            "header": header,
            "summary": summary,
            "experience_blocks": experience_blocks,
            "education_blocks": education_blocks,
            "skills_block": {"title": skills_title, "content": skills},
            "project_blocks": [],
            "section_order": ["summary", "experience", "education", "skills", "projects"],
        }
        return sections, elevation_map

    @staticmethod
    def _elevate_bullet(text: str, level: str, *, english: bool = False) -> str:
        if level == ElevationLevel.CONSERVATIVE:
            return text
        if english:
            return text
        if level == ElevationLevel.STANDARD:
            if text.startswith(("负责", "参与", "完成")):
                return text
            return f"负责{text.lstrip('，, ')}"
        if not text.startswith(("主导", "负责", "推动", "设计", "优化")):
            return f"主导{text.lstrip('，, ')}，取得可量化业务成果"
        return text
