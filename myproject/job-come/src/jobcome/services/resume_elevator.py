"""LLM-powered resume elevation (writer scenario)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jobcome.config import settings
from jobcome.llm.router import get_llm_router
from jobcome.schemas.profile_payload import ProfilePayload
from jobcome.services.profile_i18n import overlay_profile
from jobcome.services.resume_draft_builder import ResumeDraftBuilder

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "elevate" / "resume_writer.md"
_MAX_BULLETS_PER_EXP = 8


class ResumeElevator:
    def __init__(self) -> None:
        self._system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
        self._builder = ResumeDraftBuilder()

    async def build_sections(
        self,
        profile: ProfilePayload,
        *,
        elevation_level: str,
        locale: str = "zh-CN",
        job_keywords: list[str] | None = None,
        job_title: str | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        profile = overlay_profile(profile, locale)
        if not settings.job_come_llm_enabled:
            return self._builder.build(
                profile,
                elevation_level=elevation_level,
                locale=locale,
                job_keywords=job_keywords,
                job_title=job_title,
            )

        try:
            router = get_llm_router()
            user_payload = {
                "elevation_level": elevation_level,
                "locale": locale,
                "job_title": job_title,
                "job_keywords": job_keywords or [],
                "profile": profile.model_dump(mode="json"),
            }
            response = await router.acompletion(
                "writer",
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(user_payload, ensure_ascii=False)[:40_000],
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            sections = json.loads(router.content_from_response(response))
            if not isinstance(sections, dict) or not sections.get("experience_blocks"):
                raise ValueError("LLM returned invalid sections")
            sections = self._normalize_sections(sections)

            baseline_sections, elevation_map = self._builder.build(
                profile,
                elevation_level="conservative",
                locale=locale,
                job_keywords=job_keywords,
                job_title=job_title,
            )
            elevation_map = self._diff_maps(baseline_sections, sections, elevation_level)
            sections.setdefault("locale", locale)
            sections.setdefault("section_order", baseline_sections.get("section_order"))
            return sections, elevation_map
        except Exception:
            return self._builder.build(
                profile,
                elevation_level=elevation_level,
                locale=locale,
                job_keywords=job_keywords,
                job_title=job_title,
            )

    @staticmethod
    def _diff_maps(
        baseline: dict[str, Any],
        elevated: dict[str, Any],
        elevation_level: str,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        base_exps = baseline.get("experience_blocks") or []
        new_exps = elevated.get("experience_blocks") or []
        for idx, new_exp in enumerate(new_exps):
            old_exp = base_exps[idx] if idx < len(base_exps) else {}
            old_bullets = old_exp.get("bullets") or []
            new_bullets = new_exp.get("bullets") or []
            for b_idx, written in enumerate(new_bullets):
                source = old_bullets[b_idx] if b_idx < len(old_bullets) else ""
                if written != source:
                    out.append(
                        {
                            "field_path": f"experience_blocks[{idx}].bullets[{b_idx}]",
                            "source_text": source,
                            "written_text": written,
                            "needs_defense": elevation_level == "elevated",
                        }
                    )
        return out

    @classmethod
    def _normalize_sections(cls, sections: dict[str, Any]) -> dict[str, Any]:
        for exp in sections.get("experience_blocks") or []:
            raw_bullets = exp.get("bullets") or []
            normalized: list[str] = []
            for bullet in raw_bullets:
                if not isinstance(bullet, str):
                    continue
                normalized.extend(cls._split_bullet(bullet.strip()))
            exp["bullets"] = cls._trim_bullets(normalized)
        return sections

    @classmethod
    def _split_bullet(cls, text: str) -> list[str]:
        if not text:
            return []
        parts = [p.strip() for p in re.split(r"[；;\n]+", text) if p.strip()]
        if len(parts) > 1:
            return parts
        return [text]

    @classmethod
    def _trim_bullets(cls, bullets: list[str]) -> list[str]:
        cleaned = [b.strip() for b in bullets if isinstance(b, str) and b.strip()]
        return cleaned[:_MAX_BULLETS_PER_EXP]
