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
from jc.services.resume_repair import (
    accept_repair,
    measured_track,
    merge_repaired_blocks,
    plan_repair,
)
from jc.services.resume_structure import compose_document
from jc.services.text_overlap import best_origin
from jc.skills.composer import compose_writing_prompt

#: The writing methodology lives in this skill package, not in a prompt file. The
#: package is read per request rather than cached on the instance because the
#: fragment *selection* depends on the role family of the document being written —
#: a single cached prompt string is what made every role share one methodology.
_SKILL_ID = "resume-writer"
logger = logging.getLogger(__name__)

#: Appended to the writer prompt for a repair pass. States only the *shape* of a repair
#: response; every rule about what may be claimed stays in the skill package, which this
#: text must never restate or relax.
_REPAIR_CONTRACT = """

## Repair pass

You are revising specific blocks of a resume you already wrote. The user payload names
each block, the measured problem with it, and the confirmed source facts for it.

Return **only** JSON of this shape, containing only the blocks you were asked to revise:

```json
{
  "summary": "string (only if the instructions mention the summary)",
  "experience_blocks": [{ "id": "unchanged source id", "bullets": ["string"] }],
  "project_blocks": [{ "id": "unchanged source id", "bullets": ["string"] }]
}
```

- Keep each block's `id` exactly as given; it is how the revision is matched back.
- Return the same number of bullets you were given, **except** when the problem lists
  dropped source highlights — then add exactly those, as their own bullets.
- `source_facts` is the only material you may draw on. It is what the user confirmed.
- Do not restate the employer, job title, project name or dates; those are not yours to
  change here and will be ignored.
- Every rule in the sections above still applies. A problem description never licenses a
  claim the source does not support: if a block cannot be improved honestly, return it
  unchanged.
"""


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

            # The whole chain shares one deadline, so each attempt must be
            # shorter than it. `routing.yaml` gives every writer endpoint 180s
            # while this budget is 90s: a single slow primary then consumed the
            # entire budget and the two fallback models were never asked, which
            # turns a three-model chain into a one-model chain exactly when the
            # primary is unhealthy. Mirrors `resume_reviewer`, which already
            # derives a per-attempt share this way.
            total_budget = settings.jc_preview_writer_timeout_seconds
            chain_length = len(router.chain_for("writer")) if hasattr(router, "chain_for") else 3
            attempt_budget = total_budget / (max(1, chain_length) + 0.5)
            async with asyncio.timeout(total_budget):
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
                    timeout_seconds=attempt_budget,
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
            self._restore_dropped_scope_lines(sections, profile)
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

            # Everything above measured this draft and reported to the user. This is the
            # one step that acts on the measurement. Runs after the guards so the repair
            # sees the document the user would otherwise have received.
            sections = await self._repair_once(
                sections,
                profile,
                playbook=playbook,
                blueprint=blueprint,
                emphases=emphases,
                baseline_sections=baseline_sections,
                locale=locale,
            )

            elevation_map = annotate_elevation_map(
                self._diff_maps(baseline_sections, sections, elevation_level),
                job_keywords=job_keywords,
                role_family=playbook.id,
            )
            return sections, elevation_map
        except Exception as exc:
            # The message, not just the type: a gateway rejecting a request
            # parameter (`InvalidParameter: Range of max_tokens ...`) and a model
            # timing out both arrive as generic exception classes, and only the
            # message separates "misconfigured" from "slow". Logging the type
            # alone is what let a 400 on every endpoint look like flakiness.
            logger.warning(
                "Preview writer unavailable; using source layout: %s: %s",
                type(exc).__name__, exc, exc_info=True,
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

    async def _repair_once(
        self,
        sections: dict[str, Any],
        profile: ProfilePayload,
        *,
        playbook: Any,
        blueprint: Any,
        emphases: list[str],
        baseline_sections: dict[str, Any],
        locale: str,
    ) -> dict[str, Any]:
        """Rewrite the blocks that measurably missed, once, and keep it only if better.

        Returns the original draft unchanged whenever the repair is not warranted, not
        possible, or not an improvement. A repair is an upside: never let it fail the
        preview, and never let it be the reason a user sees an error.

        The prompt comes from `compose_writing_prompt`, the same assembly the first pass
        uses, rather than a second prompt written for repairs. This costs ~14k tokens of
        input per repair and is worth it: a repair prompt with its own copy of the
        honesty rules is a second definition of what counts as a fact, and this
        repository has already been bitten three times by exactly that
        (`jc-writer` vs `writer`, `config.yaml`'s three English lines vs the skill's
        101-line contract, two drifting model lists).
        """
        if not settings.jc_preview_repair_enabled:
            return sections
        try:
            plan = plan_repair(sections, profile, role_family=playbook.id)
        except Exception:  # noqa: BLE001 — measurement must never break generation
            logger.warning("repair planning failed", exc_info=True)
            return sections
        if plan is None:
            return sections

        generation = dict(sections.get("generation") or {})
        try:
            router = get_llm_router()
            payload = {
                "task": "repair",
                "locale": locale,
                "instructions": list(plan.document),
                "blocks": [
                    {
                        "collection": target.collection,
                        "id": target.block_id,
                        "problems": list(target.reasons),
                        "current": self._block_for_repair(sections, target),
                        "source_facts": self._source_facts(profile, target),
                    }
                    for target in plan.blocks
                ],
                "summary_formula": list(blueprint.summary_formula),
                "framing_emphases": emphases,
            }

            def validate(response: Any) -> dict[str, Any]:
                data = json.loads(router.content_from_response(response))
                if not isinstance(data, dict):
                    raise ValueError("repair returned a non-object")
                return data

            async with asyncio.timeout(settings.jc_preview_repair_timeout_seconds):
                repaired = await router.acompletion(
                    "writer",
                    log_context=llm_context("resume_repair"),
                    messages=[
                        {
                            "role": "system",
                            "content": self._compose_system_prompt(
                                playbook, emphases, blueprint
                            )
                            + _REPAIR_CONTRACT,
                        },
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                    response_validator=validate,
                    timeout_seconds=settings.jc_preview_repair_timeout_seconds,
                )
            candidate = merge_repaired_blocks(sections, repaired, plan)
            # A repair is still a writer, so it is subject to the same confirmed-text
            # protection: an approved sentence must not be re-paraphrased here either.
            candidate = preserve_confirmed(candidate, profile, baseline_sections)
            verdict = accept_repair(
                sections, candidate, profile, role_family=playbook.id
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Preview repair unavailable; keeping first draft: %s: %s",
                type(exc).__name__, exc, exc_info=True,
            )
            generation["repair"] = {"attempted": True, "accepted": False,
                                    "reason": f"error:{type(exc).__name__}"}
            sections["generation"] = generation
            return sections

        # Recorded either way. Without this the feature is unobservable: "did the repair
        # help" has no answer, and a gate that silently rejects everything looks
        # identical to a gate that never fires.
        generation["repair"] = {"attempted": True, **verdict.to_dict(),
                                "plan": plan.to_dict()}
        logger.info(
            "preview_repair blocks=%d accepted=%s reason=%s",
            len(plan.blocks), verdict.accepted, verdict.reason,
        )
        result = candidate if verdict.accepted else sections
        result["generation"] = generation
        return result

    @staticmethod
    def _block_for_repair(sections: dict[str, Any], target: Any) -> dict[str, Any]:
        """The block as currently written, trimmed to what a rewrite may change."""
        doc = measured_track(sections)
        blocks = doc.get(target.collection) or []
        block = blocks[target.index] if target.index < len(blocks) else {}
        if not isinstance(block, dict):
            return {}
        keep = ("id", "company", "title", "name", "role", "scope_line", "description", "bullets")
        return {k: block[k] for k in keep if k in block}

    @staticmethod
    def _source_facts(profile: ProfilePayload, target: Any) -> dict[str, Any]:
        """The confirmed source for this block. The repair may use nothing else."""
        entities = (
            profile.experiences if target.collection == "experience_blocks"
            else profile.projects
        )
        entity = next((e for e in entities if e.id == target.block_id), None)
        if entity is None:
            return {}
        out: dict[str, Any] = {
            "scope": entity.scope,
            "highlights": list(entity.highlights or []),
        }
        if getattr(entity, "description", None):
            out["description"] = entity.description
        out["user_supplied_evidence"] = [
            {"field_path": a.field_path, "question": a.question, "answer": a.answer}
            for a in profile.evidence_answers
            if target.block_id and target.block_id in (a.field_path or "")
        ]
        return out

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
    def _restore_dropped_scope_lines(
        sections: dict[str, Any], profile: ProfilePayload
    ) -> None:
        """Re-attach a scope line the writer dropped, but only a user-authored one.

        `scope` is where team size, mandate and business scale live, and it is the only
        source that knows them. `null` is a legal writer answer meaning "the source
        carries no scope fact" — but when the user actually typed a `scope`, the source
        plainly did carry one, so the null is an omission. Dropping it deletes the
        highest-signal line in the block.

        Restores from the **profile**, never from the deterministic baseline: with no
        `scope` that baseline synthesises `在{company}担任{title}`, which restates the
        heading directly above it and says nothing about scale. Re-attaching that is
        worse than the null — it fills the most valuable line in the block with a
        tautology, which is exactly what makes an export read as unoptimized.

        Only fills an absent value; never overwrites a line the writer wrote.
        """
        for key, source_key in (
            ("experience_blocks", "experiences"),
            ("project_blocks", "projects"),
        ):
            stated = {
                entity.id: entity.scope.strip()
                for entity in getattr(profile, source_key)
                if (entity.scope or "").strip()
            }
            for block in sections.get(key) or []:
                if not isinstance(block, dict) or block.get("scope_line"):
                    continue
                scope = stated.get(block.get("id"))
                if scope:
                    block["scope_line"] = scope

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
