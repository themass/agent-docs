"""LLM-powered resume elevation (writer scenario)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jc.config import settings
from jc.llm.router import get_llm_router
from jc.schemas.profile_payload import ProfilePayload
from jc.services.elevation_techniques import annotate_elevation_map
from jc.services.framing_presets import as_prompt_block, resolve_emphases
from jc.services.profile_i18n import overlay_profile
from jc.services.resume_draft_builder import ResumeDraftBuilder
from jc.services.role_families import get_playbook, playbook_for_title

_PROMPT_PATH = Path(__file__).resolve().parents[3].parent / "agent" / "prompts" / "elevate" / "resume_writer.md"


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
        role_family: str | None = None,
        fit_gaps: list[str] | None = None,
        elevate_hints: list[str] | None = None,
        framing_emphases: list[str] | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        profile = overlay_profile(profile, locale)
        # What counts as a strong resume differs by role. The playbook supplies this
        # family's outcome vocabulary and reading order; it never supplies facts.
        playbook = (
            get_playbook(role_family)
            if role_family
            else playbook_for_title(
                job_title,
                profile.experiences[0].title if profile.experiences else None,
            )
        )
        # Which supported fact each bullet leads with. The user picks; an empty pick
        # falls back to what a recruiter in this family reads for first.
        emphases = resolve_emphases(
            framing_emphases
            if framing_emphases is not None
            else profile.preferences.framing_emphases,
            role_family=playbook.id,
        )
        if not settings.jc_llm_enabled:
            return self._builder.build(
                profile,
                elevation_level=elevation_level,
                locale=locale,
                job_keywords=job_keywords,
                job_title=job_title,
                role_family=playbook.id,
            )

        try:
            router = get_llm_router()
            user_payload = {
                "elevation_level": elevation_level,
                "locale": locale,
                "job_title": job_title,
                "job_keywords": job_keywords or [],
                "role_family": playbook.id,
                "framing_emphases": emphases,
                # Requirements the JD asks for that the fit scorer judged under-evidenced.
                # The writer's job is to find existing support for these in the profile and
                # surface it — not to claim them. Unsupported requirements stay off the page.
                "jd_under_evidenced": list(fit_gaps or []),
                "jd_elevate_hints": list(elevate_hints or []),
                # Facts the user typed in answer to our evidence questions. These are
                # user-authored, so they count as source material exactly like a bullet.
                "user_supplied_evidence": [
                    {
                        "field_path": a.field_path,
                        "question": a.question,
                        "answer": a.answer,
                    }
                    for a in profile.evidence_answers
                ],
                "profile": profile.model_dump(mode="json"),
            }
            response = await router.acompletion(
                "writer",
                messages=[
                    {
                        "role": "system",
                        "content": self._compose_system_prompt(playbook, emphases),
                    },
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
                role_family=playbook.id,
            )
            elevation_map = annotate_elevation_map(
                self._diff_maps(baseline_sections, sections, elevation_level),
                job_keywords=job_keywords,
                role_family=playbook.id,
            )
            sections.setdefault("locale", locale)
            sections.setdefault("section_order", baseline_sections.get("section_order"))
            sections.setdefault("role_family", playbook.id)
            sections.setdefault("framing_emphases", emphases)
            # A model that forgets `project_blocks` must not be able to delete 项目经历 from the
            # document. The deterministic builder already derived them from the profile, so fall
            # back to those rather than shipping a resume that is missing real work.
            if profile.projects and not sections.get("project_blocks"):
                sections["project_blocks"] = baseline_sections.get("project_blocks") or []
            return sections, elevation_map
        except Exception:
            return self._builder.build(
                profile,
                elevation_level=elevation_level,
                locale=locale,
                job_keywords=job_keywords,
                job_title=job_title,
                role_family=playbook.id,
            )

    def _compose_system_prompt(self, playbook: Any, emphases: list[str]) -> str:
        """Writer system prompt for this specific document.

        The playbook says what a strong resume means for this audience; the emphasis
        block says which supported fact to lead with. Both are presentation guidance and
        are appended rather than templated in, so the base prompt stays the single place
        the honesty rules live.
        """
        parts = [
            self._system_prompt,
            f"## Role playbook for this document\n{playbook.as_prompt_block()}",
        ]
        emphasis_block = as_prompt_block(emphases)
        if emphasis_block:
            parts.append(f"## Framing angles chosen for this document\n{emphasis_block}")
        return "\n\n".join(parts)

    @staticmethod
    def _diff_maps(
        baseline: dict[str, Any],
        elevated: dict[str, Any],
        elevation_level: str,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for key in ("experience_blocks", "project_blocks"):
            base_blocks = baseline.get(key) or []
            new_blocks = elevated.get(key) or []
            for idx, new_block in enumerate(new_blocks):
                old_block = base_blocks[idx] if idx < len(base_blocks) else {}
                old_bullets = old_block.get("bullets") or []
                new_bullets = new_block.get("bullets") or []
                for b_idx, written in enumerate(new_bullets):
                    source = old_bullets[b_idx] if b_idx < len(old_bullets) else ""
                    if written != source:
                        out.append(
                            {
                                "field_path": f"{key}[{idx}].bullets[{b_idx}]",
                                "source_text": source,
                                "written_text": written,
                                "needs_defense": elevation_level == "elevated",
                            }
                        )
        return out

    @classmethod
    def _normalize_sections(cls, sections: dict[str, Any]) -> dict[str, Any]:
        for key in ("experience_blocks", "project_blocks"):
            for block in sections.get(key) or []:
                raw_bullets = block.get("bullets") or []
                normalized: list[str] = []
                for bullet in raw_bullets:
                    if not isinstance(bullet, str):
                        continue
                    normalized.extend(cls._split_bullet(bullet.strip()))
                block["bullets"] = cls._clean_bullets(normalized)
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
    def _clean_bullets(cls, bullets: list[str]) -> list[str]:
        """Drop blanks and exact duplicates, keeping source order.

        Deliberately does **not** cap the count. A hard cap silently deletes accomplishments the
        extractor was told to preserve losslessly, and under-writing a senior career is the
        failure users actually notice. Length is the writer prompt's job, not the parser's.
        """
        cleaned: list[str] = []
        seen: set[str] = set()
        for bullet in bullets:
            if not isinstance(bullet, str):
                continue
            text = bullet.strip()
            if not text or text in seen:
                continue
            seen.add(text)
            cleaned.append(text)
        return cleaned
