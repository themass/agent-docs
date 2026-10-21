"""LLM-powered resume elevation (writer scenario)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from copy import deepcopy
from typing import Any

from jc.config import settings
from jc.domain.profile_context import material_profile
from jc.domain.role_families import get_playbook, playbook_for_title
from jc.llm.call_context import llm_context
from jc.llm.router import get_llm_router
from jc.schemas.profile_payload import ProfilePayload
from jc.services.approved_resume_text import preserve_confirmed
from jc.services.elevation_techniques import annotate_elevation_map
from jc.services.framing_presets import as_prompt_block, resolve_emphases
from jc.services.profile_i18n import overlay_profile
from jc.services.resume_blueprint import blueprint_for
from jc.services.resume_draft_builder import ResumeDraftBuilder
from jc.services.resume_structure import compose_document
from jc.services.text_overlap import best_origin
from jc.skills.composer import compose_writing_prompt

#: The writing methodology lives in this skill package, not in a prompt file. The
#: package is read per request rather than cached on the instance because the
#: fragment *selection* depends on the role family of the document being written —
#: a single cached prompt string is what made every role share one methodology.
_SKILL_ID = "resume-writer"
logger = logging.getLogger(__name__)


class ResumeElevator:
    def __init__(self) -> None:
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
        # The bar this document is judged against. Derived from the playbook, so it
        # cannot drift from it, and measured after generation by `evaluate_blueprint`.
        blueprint = blueprint_for(playbook.id)
        # Which supported fact each bullet leads with. The user picks; an empty pick
        # falls back to what a recruiter in this family reads for first.
        emphases = resolve_emphases(
            framing_emphases
            if framing_emphases is not None
            else profile.preferences.framing_emphases,
            role_family=playbook.id,
        )
        if not settings.jc_llm_enabled:
            return await asyncio.to_thread(
                self._builder.build, profile,
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
                # Source units are invariant. Family counts are advisory completeness
                # references, never quotas that license splitting a project narrative.
                # Supplied as data as well as prose because the model satisfied the prose
                # version while producing documents that met none of these.
                "document_requirements": {
                    "lead_role_reference_bullets": blueprint.lead_bullets,
                    "other_roles_reference_bullets": blueprint.tail_bullets,
                    "preserve_source_units": True,
                    "min_outcome_ratio": blueprint.outcome_ratio,
                    "scope_line_must_state": list(blueprint.scope_dimensions),
                    "summary_formula": list(blueprint.summary_formula),
                },
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
                "profile": material_profile(profile),
            }
            def validate(response: Any) -> dict[str, Any]:
                data = json.loads(router.content_from_response(response))
                if not isinstance(data, dict) or not data.get("experience_blocks"):
                    # Checked here, not after the call: an answer with no
                    # experience blocks is the one failure the writer chain can
                    # actually recover from by asking a different model.
                    raise ValueError("LLM returned invalid sections")
                return data

            async with asyncio.timeout(settings.jc_preview_writer_timeout_seconds):
                sections = await router.acompletion(
                    "writer",
                    log_context=llm_context("resume_elevator"),
                    messages=[
                        {
                            "role": "system",
                            "content": self._compose_system_prompt(
                                playbook, emphases, blueprint
                            ),
                        },
                        {
                            "role": "user",
                            "content": json.dumps(user_payload, ensure_ascii=False),
                        },
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                    response_validator=validate,
                )
            sections = self._normalize_sections(sections)

            baseline_sections, _ = await asyncio.to_thread(
                self._builder.build, profile,
                elevation_level="conservative",
                locale=locale,
                job_keywords=job_keywords,
                job_title=job_title,
                role_family=playbook.id,
            )
            sections.setdefault("locale", locale)
            sections.setdefault("role_family", playbook.id)
            sections.setdefault("framing_emphases", emphases)
            # A model that forgets `project_blocks` must not be able to delete 项目经历 from the
            # document. The deterministic builder already derived them from the profile, so fall
            # back to those rather than shipping a resume that is missing real work.
            if profile.projects and not sections.get("project_blocks"):
                sections["project_blocks"] = baseline_sections.get("project_blocks") or []

            guarded = self._preserve_source_units(sections, baseline_sections)
            if guarded:
                logger.warning("writer_structure_guard restored_blocks=%s", guarded)
                sections["generation"] = {
                    "mode": "structure_guarded",
                    "warning": (
                        "部分优化结果改变了原有项目或段落边界，"
                        "已保留这些部分的档案原文；其余内容正常优化。"
                    ),
                    "restored_blocks": guarded,
                }
            sections = preserve_confirmed(sections, profile, baseline_sections)
            # Document-level composition runs **before** the diff is computed, so the
            # order the user sees is the order the change list explains. It may adjust
            # section order, never project paragraph order or sentence content.
            structure = compose_document(
                sections,
                role_family=playbook.id,
                job_keywords=job_keywords,
            )
            sections["structure"] = structure.to_dict()
            sections = preserve_confirmed(sections, profile, baseline_sections)

            elevation_map = annotate_elevation_map(
                self._diff_maps(baseline_sections, sections, elevation_level),
                job_keywords=job_keywords,
                role_family=playbook.id,
            )
            return sections, elevation_map
        except Exception as exc:
            logger.warning(
                "Preview writer unavailable; using source layout: %s",
                type(exc).__name__, exc_info=True,
            )
            sections, elevation_map = await asyncio.to_thread(
                self._builder.build, profile,
                # A failed AI writer must not silently substitute rule-based
                # ownership inflation while claiming to show the original text.
                elevation_level="conservative",
                locale=locale,
                job_keywords=job_keywords,
                job_title=job_title,
                role_family=playbook.id,
            )
            from jc.services.preview_progress import report
            report("generate", message="AI 写作未完成，正在按档案原文生成排版预览。")
            sections["generation"] = {
                "mode": "source_layout",
                "warning": (
                    "AI 写作未完成，当前显示档案原文排版；"
                    "已确认的修改已保留。可重试 AI 优化。"
                ),
            }
            return sections, elevation_map

    @staticmethod
    def _compose_system_prompt(
        playbook: Any, emphases: list[str], blueprint: Any = None
    ) -> str:
        """Writer system prompt for this specific document.

        Assembled from the `resume-writer` skill package, which selects its own
        universal layers and then the fragment for this role family. Only the
        document-specific parts are passed in from here: the measurable bar and the
        angles the user chose. The honesty rules stay in the skill's always-loaded
        body, so no family fragment can be written in a way that relaxes them.
        """
        return compose_writing_prompt(
            skill_id=_SKILL_ID,
            playbook=playbook,
            document_contract=blueprint.as_prompt_block() if blueprint is not None else "",
            extra_sections=(
                ("Framing angles chosen for this document", as_prompt_block(emphases)),
            ),
        ).text

    #: Overlap at or above which a written bullet is treated as a rewrite of a specific
    #: source line. Matches `writing_invariants._ATTRIBUTION_THRESHOLD` on purpose: both
    #: answer "which source line did this sentence come from", and two different answers
    #: to that question would make the change list and the honesty audit disagree about
    #: the same bullet.
    _ATTRIBUTION_THRESHOLD = 0.30

    @classmethod
    def _diff_maps(
        cls,
        baseline: dict[str, Any],
        elevated: dict[str, Any],
        elevation_level: str,
    ) -> list[dict[str, Any]]:
        """Pair each written bullet with the source line it was written from.

        Matched by content, not by list position. Position-pairing silently assumed one
        written bullet per source bullet in the same order, which three legitimate
        behaviours break: the writer may split or merge bullets, and the structure pass
        reorders them strongest-first. Under position-pairing a reordered block reports
        every bullet as rewritten, so the change list — the one screen where the user
        checks that nothing was invented — fills with noise and stops being read.

        Each source line may be claimed once. A merged bullet therefore shows the
        strongest of its sources, and the other source shows up as dropped in
        `resume_coverage`, which is the correct place for it.
        """
        out: list[dict[str, Any]] = []
        for key in ("experience_blocks", "project_blocks"):
            base_blocks = baseline.get(key) or []
            new_blocks = elevated.get(key) or []
            for idx, new_block in enumerate(new_blocks):
                old_block = base_blocks[idx] if idx < len(base_blocks) else {}
                candidates = [
                    b for b in (old_block.get("bullets") or []) if isinstance(b, str) and b.strip()
                ]
                claimed: set[int] = set()
                new_bullets = [
                    b for b in (new_block.get("bullets") or []) if isinstance(b, str)
                ]
                for b_idx, written in enumerate(new_bullets):
                    available = [
                        (i, text) for i, text in enumerate(candidates) if i not in claimed
                    ]
                    source = ""
                    if available:
                        match = best_origin(written, [text for _, text in available])
                        if match is not None and match.score >= cls._ATTRIBUTION_THRESHOLD:
                            claimed.add(available[match.index][0])
                            source = match.text
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

    @staticmethod
    def _preserve_source_units(
        sections: dict[str, Any], baseline: dict[str, Any]
    ) -> list[str]:
        """Keep each source entity and paragraph intact; never guess how fragments merge.

        A structurally invalid rewrite falls back to its source block, not a second
        model call. IDs win; a unique untranslated identity supports legacy models.
        If identity is ambiguous, restore that whole section rather than attach a
        project's claims to a different employer/project. No profile data is mutated.
        """
        restored: list[str] = []
        for key, identity in (
            ("experience_blocks", ("company", "title")),
            ("project_blocks", ("name",)),
        ):
            originals = baseline.get(key) or []
            written = sections.get(key) or []
            if not originals and not written:
                continue
            if len(written) != len(originals):
                sections[key] = deepcopy(originals)
                restored.append(key)
                continue
            ordered: list[dict[str, Any]] = []
            used: set[int] = set()
            for index, original in enumerate(originals):
                candidates = [
                    i for i, block in enumerate(written)
                    if i not in used and isinstance(block, dict)
                    and original.get("id") and block.get("id") == original["id"]
                ]
                if not candidates:
                    candidates = [
                        i for i, block in enumerate(written)
                        if i not in used and isinstance(block, dict)
                        and not block.get("id")
                        and all(block.get(k) == original.get(k) for k in identity)
                    ]
                if len(candidates) != 1:
                    sections[key] = deepcopy(originals)
                    restored.append(key)
                    break
                match = candidates[0]
                used.add(match)
                block = written[match]
                # One source paragraph -> one rewritten paragraph, at every strength.
                if len(block.get("bullets") or []) != len(original.get("bullets") or []):
                    block = deepcopy(original)
                    restored.append(f"{key}[{index}]")
                ordered.append(block)
            else:
                sections[key] = ordered
        return restored

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
                # The scope line is one sentence by contract. A model that returns a
                # paragraph or a list there would push the bullets off the first screen
                # of the block, which defeats the point of having it.
                block["scope_line"] = cls._clean_scope_line(block.get("scope_line"))
        return sections

    #: Longest scope line that still reads as one line in the rendered document. Measured
    #: against the export template at A4 width: beyond this it wraps to three lines and
    #: competes with the bullets it is supposed to introduce.
    _SCOPE_LINE_MAX = 90

    @classmethod
    def _clean_scope_line(cls, value: Any) -> str | None:
        """One sentence of 角色与范围, or None.

        Truncation is deliberately *not* done by cutting mid-sentence: a scope line that
        ends in an ellipsis reads as a rendering bug. An over-long value is reduced to its
        first clause, which is the part that carries the role and the scale.
        """
        if not isinstance(value, str):
            return None
        text = value.strip().strip("。.;；")
        if not text:
            return None
        if len(text) <= cls._SCOPE_LINE_MAX:
            return text
        parts = [p for p in re.split(r"[。；;]", text) if p.strip()]
        head = parts[0].strip() if parts else text
        return head[: cls._SCOPE_LINE_MAX].strip() or None

    @classmethod
    def _split_bullet(cls, text: str) -> list[str]:
        if not text:
            return []
        # Punctuation and visual line wrapping are not semantic unit boundaries.
        # Background, action and outcome can legitimately share a single source item.
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
