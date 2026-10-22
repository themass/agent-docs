"""Resume elevate and export."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from agentkit.common.ids import new_id
from agentkit.web.auth import Actor, UserActor
from sqlalchemy.ext.asyncio import AsyncSession

from jc.config import settings
from jc.db.profile_snapshot_hook import bind_snapshot_source
from jc.db.session import release_db_connection
from jc.domain.role_families import resolve_role_family
from jc.exceptions import ConflictError, NotFoundError
from jc.models.enums import ExportFormat, ExportJobStatus, ReviewerStatus
from jc.models.resume import ExportJob, ResumeDraft
from jc.resume_locale import (
    TRACK_BILINGUAL,
    TRACK_EN,
    TRACK_ZH,
    is_bilingual_track,
    normalize_track,
    other_monolingual,
    template_id_for_locale,
)
from jc.schemas.profile_payload import ProfilePayload
from jc.schemas.resume import (
    ElevatePreviewResponse,
    ExportJobResponse,
    ExportRequest,
    ResumeDraftResponse,
)
from jc.services.approved_resume_text import preserve_confirmed, with_confirmed_fields
from jc.services.framing_presets import resolve_emphases
from jc.services.localize_service import LocalizeService
from jc.services.profile_i18n import (
    detect_profile_source_locale,
    project_i18n_pack,
)
from jc.services.profile_photo_service import photo_data_uri, set_header_photo
from jc.services.profile_service import ProfileService
from jc.services.resume_blueprint import evaluate_blueprint
from jc.services.resume_coverage import audit_coverage
from jc.services.resume_diagnostics import diagnose
from jc.services.resume_draft_builder import ResumeDraftBuilder
from jc.services.resume_elevator import ResumeElevator
from jc.services.preview_progress import report
from jc.services.resume_render_engine import ResumeRenderEngine
from jc.services.resume_reviewer import ResumeReviewer
from jc.services.resume_structure import audit_structure
from jc.services.writing_invariants import audit_additions
from jc.storage_backend import get_storage_backend
from jc.storage_client import download_url_for_key
from jc.storage_keys import storage_key
from jc.stores.profile_store import ProfileStore
from jc.stores.resume_store import ResumeStore


@dataclass(frozen=True, slots=True)
class JobHints:
    """Everything the writer should know about the target job.

    `gaps` and `elevate_hints` come from the fit-score run that already happened on this
    job. They name requirements the JD asks for that the resume does not currently
    surface — which is exactly the material the writer should be looking for in the
    profile. They are hints about *where to look*, never licence to add facts.
    """

    keywords: list[str] = field(default_factory=list)
    title: str | None = None
    role_category: str | None = None
    gaps: list[str] = field(default_factory=list)
    elevate_hints: list[str] = field(default_factory=list)


def compose_bilingual_sections(
    zh_sections: dict[str, Any],
    en_sections: dict[str, Any],
    *,
    zh_draft_id: str,
    en_draft_id: str,
    show_photo: bool = False,
) -> dict[str, Any]:
    """Wrap the two monolingual drafts into one bilingual document.

    `show_photo` is the user's `show_in_bilingual` opt-in, and it has to be applied
    *here* rather than trusted from the parts. The bilingual draft is assembled from
    the zh and en drafts that were each built for their own track, so the zh half
    legitimately carries a headshot (the Chinese track draws one when the switch is
    on) — and the top-level `header` below is a copy of that zh header. Copying it
    verbatim published the photo on the bilingual export even with the opt-in off,
    which is exactly the leak `ProfilePhoto.renders_for_locale` exists to prevent.
    The en half needs no such treatment: the English track never renders a photo at
    all, so there is nothing in it to strip.

    Stripping rather than re-deriving keeps this a pure function of its inputs: the
    builder already decided *whether* a photo may be drawn for each track, and the
    only thing left is "does the bilingual document get the zh one".
    """
    zh_header = dict(zh_sections.get("header") or {})
    zh_track_sections = zh_sections
    if not show_photo and "photo_data_uri" in zh_header:
        zh_header.pop("photo_data_uri", None)
        # The nested zh half is what the bilingual template actually renders
        # (`render_html` passes `zh_sections` straight to the macro), so dropping the
        # key from the flattened copy alone would leave the photo on the page.
        zh_track_sections = {**zh_sections, "header": zh_header}
    return {
        "track": "bilingual",
        "locale": TRACK_BILINGUAL,
        "zh_draft_id": zh_draft_id,
        "en_draft_id": en_draft_id,
        "zh_sections": zh_track_sections,
        "en_sections": en_sections,
        "header": zh_header,
        "summary": zh_sections.get("summary"),
        "experience_blocks": zh_sections.get("experience_blocks") or [],
        "education_blocks": zh_sections.get("education_blocks") or [],
        "skills_block": zh_sections.get("skills_block") or {},
        "section_order": ["summary", "experience", "education", "skills"],
    }


logger = logging.getLogger(__name__)


class ResumeService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._profiles = ProfileService(db)
        self._resumes = ResumeStore(db)
        self._builder = ResumeDraftBuilder()
        self._elevator = ResumeElevator()
        self._renderer = ResumeRenderEngine()
        self._reviewer = ResumeReviewer()
        self._localizer = LocalizeService()
        self._storage = get_storage_backend()

    async def elevate(
        self,
        profile_id: str,
        *,
        actor: Actor,
        elevation_level: str,
        locale: str = TRACK_ZH,
        template_id: str | None = None,
        job_id: str | None = None,
    ) -> ResumeDraftResponse:
        track = normalize_track(locale)
        if is_bilingual_track(track):
            return await self._elevate_bilingual(
                profile_id, actor=actor, elevation_level=elevation_level, job_id=job_id
            )
        template_id = template_id or template_id_for_locale(track)
        profile_resp = await self._profiles.get(profile_id, actor=actor)
        payload = await with_confirmed_fields(self._db, profile_id, profile_resp.payload)
        hints = await self._job_hints(profile_id, job_id)
        role_family = resolve_role_family(
            override=payload.preferences.role_family,
            job_category=hints.role_category,
            job_title=hints.title,
            profile_titles=tuple(e.title for e in payload.experiences[:2]),
        )
        await release_db_connection(self._db)
        sections, elevation_map = await self._elevator.build_sections(
            payload,
            elevation_level=elevation_level,
            locale=track,
            job_keywords=hints.keywords or None,
            job_title=hints.title,
            role_family=role_family,
            fit_gaps=hints.gaps,
            elevate_hints=hints.elevate_hints,
            framing_emphases=resolve_emphases(
                payload.preferences.framing_emphases, role_family=role_family
            ),
        )
        current_profile = await self._profiles.get(profile_id, actor=actor)
        if current_profile.version != profile_resp.version:
            raise ConflictError("生成期间档案已更新，请重新生成预览，避免展示旧内容。", code="preview_profile_changed")
        if job_id:
            sections["job_context_hash"] = self._job_context_hash(hints)
        draft = ResumeDraft(
            id=new_id("rdft"),
            profile_id=profile_id,
            profile_version=profile_resp.version,
            job_id=job_id,
            elevation_level=elevation_level,
            locale=track,
            template_id=template_id,
            sections=sections,
            elevation_map=elevation_map,
            reviewer_status=ReviewerStatus.PENDING,
            reviewer_notes=None,
            exported_at=None,
        )
        await self._resumes.create_draft(draft)
        await self._db.flush()
        await self._db.refresh(draft)
        response = self._to_draft_response(draft)
        await self._db.commit()
        return response

    async def preview_events(self, profile_id: str, *, actor: Actor, **kwargs: Any):
        from jc.services.preview_progress import stream_preview

        # Run auth/ownership before returning the event iterator so HTTP status is
        # preserved; the route never reaches into storage implementation details.
        logger.info("preview_preflight_started profile_id=%s", profile_id)
        await self._profiles.get(profile_id, actor=actor)
        await release_db_connection(self._db)
        logger.info("preview_preflight_completed profile_id=%s", profile_id)
        return stream_preview(self, profile_id, actor=actor, **kwargs)

    async def preview(
        self,
        profile_id: str,
        *,
        actor: Actor,
        elevation_level: str,
        locale: str = TRACK_ZH,
        job_id: str | None = None,
        force: bool = False,
    ) -> ElevatePreviewResponse:
        report("read")
        await self._profiles.get(profile_id, actor=actor)
        report("read", done=True)
        report("generate")
        track = normalize_track(locale)
        if is_bilingual_track(track):
            draft = await self._ensure_bilingual_draft(
                profile_id, actor=actor, elevation_level=elevation_level, force=force, job_id=job_id
            )
        else:
            template_id = template_id_for_locale(track)
            draft = await self._resumes.get_latest_draft(
                profile_id, elevation_level=elevation_level, locale=track, job_id=job_id
            )
            stale = draft is not None and await self._is_stale_for_profile(
                draft, profile_id=profile_id, actor=actor
            )
            # `writer_failed` is separated from the generic staleness label so the log can
            # answer "why is this regenerating": a retried outage and an edited profile
            # are the same event under one label, and only one of them is a problem.
            cache_reason = (
                "forced" if force else "missing" if draft is None else
                "template_changed" if draft.template_id != template_id else
                "writer_failed" if stale and self._writer_failed(
                    draft.sections if isinstance(draft.sections, dict) else {}
                ) else
                "profile_or_options_changed" if stale else "hit"
            )
            logger.info("preview_cache profile_id=%s locale=%s level=%s reason=%s draft_id=%s",
                        profile_id, track, elevation_level, cache_reason, draft.id if draft else "none")
            if cache_reason != "hit":
                draft_resp = await self.elevate(
                    profile_id,
                    actor=actor,
                    elevation_level=elevation_level,
                    locale=track,
                    template_id=template_id,
                    job_id=job_id,
                )
                draft = await self._resumes.get_draft_by_id(draft_resp.id)
                if draft is None:
                    raise NotFoundError(
                        "没找到这份优化稿，请重新生成预览。",
                        code="draft_not_found",
                    )
        # Generation includes persistence of every language track. Only the outer
        # request may complete a phase; a bilingual child finishing is not enough.
        logger.info("preview_content profile_id=%s draft_id=%s mode=%s",
                    profile_id, draft.id, (draft.sections.get("generation") or {}).get("mode", "legacy_or_composed"))
        report("generate", done=True)
        report("save")
        profile_resp = await self._profiles.get(profile_id, actor=actor)
        approved_payload = await with_confirmed_fields(self._db, profile_id, profile_resp.payload)
        sections = await asyncio.to_thread(
            self._normalize_sections, draft.sections, approved_payload, locale=draft.locale
        )
        # Repair legacy cached drafts too; exports must use the same protected
        # sections that the preview shows, rather than a display-only overlay.
        if approved_payload.meta.approved_resume_fields and sections != draft.sections:
            draft.sections = sections
            await self._db.commit()
            await self._db.refresh(draft)
        report("save", done=True)
        report("render")
        # Photo applied to the render copy only. The audits below score written
        # content, and a base64 blob on the header is not content -- keeping it out
        # of their input means turning the switch on can never move a coverage or
        # blueprint number.
        rendered = await asyncio.to_thread(
            self._with_live_photo, sections, profile_resp.payload, locale=draft.locale
        )
        html = await asyncio.to_thread(
            self._renderer.render_html, rendered, template_id=draft.template_id
        )
        report("render", done=True)
        report("audit")
        # Length is reported here, not only at export: a thin document is fixable at
        # step 3 (regenerate, change framing, answer an evidence question) and is not
        # fixable on the download screen. Keywords stay at step 4 -- they need the JD,
        # and acting on them means editing the profile, not the draft.
        hints = await self._job_hints(profile_id, draft.job_id)
        # Prefer the report stamped at generation time: it records what composition
        # actually *did*, including moves. Re-auditing a stored draft can only observe
        # the result, so a draft generated before this field existed falls back to that.
        family = self._draft_role_family(sections, profile_resp.payload.model_dump())
        structure = draft.sections.get("structure") if isinstance(draft.sections, dict) else None
        if not isinstance(structure, dict):
            structure = audit_structure(
                sections,
                role_family=family,
                job_keywords=hints.keywords or None,
            ).to_dict()
        result = ElevatePreviewResponse(
            draft=self._to_draft_response(draft, sections=rendered),
            html=html,
            coverage=audit_coverage(sections, profile_resp.payload).to_dict(),
            diagnostics=diagnose(sections, job_keywords=hints.keywords or None).to_dict(),
            structure=structure,
            # The family's bar and how this draft measures against it. Returned at step 3
            # because that is where every unmet requirement is still actionable; by the
            # download screen the only remaining option is to go back.
            blueprint=evaluate_blueprint(sections, role_family=family).to_dict(),
        )
        report("audit", done=True)
        return result

    async def export(
        self,
        profile_id: str,
        *,
        actor: UserActor,
        body: ExportRequest,
    ) -> ExportJobResponse:
        export_profile = await self._profiles.get(profile_id, actor=actor)
        track = normalize_track(body.locale)
        template_id = body.template_id or template_id_for_locale(track)

        draft: ResumeDraft | None = None
        if body.draft_id:
            draft = await self._resumes.get_draft_by_id(body.draft_id)
            if draft is None or draft.profile_id != profile_id:
                raise NotFoundError("没找到这份优化稿，请重新生成预览。", code="draft_not_found")
        if draft is None:
            if is_bilingual_track(track):
                draft = await self._ensure_bilingual_draft(
                    profile_id, actor=actor, elevation_level=body.elevation_level.value
                )
            else:
                draft_row = await self._resumes.get_latest_draft(
                    profile_id,
                    elevation_level=body.elevation_level.value,
                    locale=track,
                )
                if draft_row is None or draft_row.template_id != template_id:
                    draft_row = await self._ensure_draft(
                        profile_id,
                        actor=actor,
                        elevation_level=body.elevation_level.value,
                        locale=track,
                        template_id=template_id,
                    )
                draft = draft_row
        if draft is None:
            raise NotFoundError("还没有可导出的优化稿，请先成功生成预览。", code="draft_not_found")

        # Review belongs to review_for_export, not file generation. Re-running it for
        # PDF, Word and HTML adds three model calls and can outlive the HTTP proxy.
        # Keep the persisted verdict unchanged, including PENDING if never reviewed.
        # Snapshot before ending the read transaction: rollback expires ORM objects.
        sections = dict(draft.sections or {})
        draft_locale = draft.locale
        draft_template = draft.template_id
        draft_id = draft.id
        job_id = new_id("expj")
        job_format = body.format.value
        await release_db_connection(self._db)
        job = ExportJob(
            id=job_id,
            user_id=actor.user_id,
            profile_id=profile_id,
            resume_draft_id=draft_id,
            format=job_format,
            locale=draft_locale,
            status=ExportJobStatus.PROCESSING,
        )
        await self._resumes.create_export_job(job)
        # Make PROCESSING durable and release the connection before slow external I/O.
        # A worker interruption must not erase the fact that the export was attempted.
        await self._db.commit()

        stage = "render"
        try:
            render_sections = await asyncio.to_thread(
                self._with_live_photo, sections, export_profile.payload, locale=draft_locale
            )
            if body.format == ExportFormat.DOCX:
                content = await asyncio.to_thread(self._renderer.render_docx, render_sections)
                ext = "docx"
                content_type = (
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            else:
                html = await asyncio.to_thread(
                    self._renderer.render_html, render_sections, template_id=draft_template
                )
                if body.format == ExportFormat.PDF:
                    content = await asyncio.to_thread(self._renderer.render_pdf, html)
                    ext = "pdf"
                    content_type = "application/pdf"
                else:
                    content = html.encode("utf-8")
                    ext = "html"
                    content_type = "text/html; charset=utf-8"
            from jc.services.export_quality import validate_export

            stage = "validate"
            quality = await asyncio.to_thread(validate_export, content, ext, render_sections)
            text_layer = quality.get("text_layer", {})
            if text_layer.get("warnings"):
                # Codes/counts only; never write PDF text or contact data to app logs.
                logger.warning("Export %s PDF text-layer diagnostics: %s",
                               job_id, text_layer["warnings"])
            object_key = storage_key("profiles", profile_id, "export", f"{job_id}.{ext}")
            stage = "upload"
            await asyncio.to_thread(
                self._storage.put_object, object_key, content, content_type=content_type
            )
            stage = "download_url"
            download_url = await asyncio.to_thread(download_url_for_key, object_key)
            stage = "persist"
            job = await self._resumes.get_export_job(job_id)
            if job is None:
                raise RuntimeError("Export job disappeared during rendering")
            await self._resumes.mark_export_done(job, storage_key=object_key)
            await self._db.commit()
            return ExportJobResponse(
                id=job_id,
                status=ExportJobStatus.DONE,
                format=job_format,
                download_url=download_url,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Export %s failed at %s", job_id, stage)
            # A flush/commit failure leaves the session unusable until rollback.
            # Reload by scalar ID, never read expired attributes from the old job.
            await self._db.rollback()
            job = await self._resumes.get_export_job(job_id)
            if job is None:
                raise
            await self._resumes.mark_export_failed(job, f"[{stage}] {type(exc).__name__}: {exc}")
            await self._db.commit()
            stage_label = {
                "render": "文件生成", "validate": "文件完整性检查",
                "upload": "文件上传", "download_url": "下载链接生成", "persist": "保存导出记录",
            }[stage]
            return ExportJobResponse(
                id=job_id,
                status=ExportJobStatus.FAILED,
                format=job_format,
                error_message=f"{stage_label}失败，请重试；如仍失败，请提供导出编号 {job_id}。",
            )

    async def review_events(self, profile_id: str, *, actor: UserActor, **kwargs: Any):
        from jc.services.operation_progress import stream_operation

        # Preserve authentication/ownership HTTP errors before sending SSE headers.
        await self._profiles.get(profile_id, actor=actor)
        await release_db_connection(self._db)
        return stream_operation(
            lambda: self.review_for_export(profile_id, actor=actor, **kwargs), profile_id,
            rollback_db=self._db.rollback, operation="export_review", label="导出前质检", log=logger,
            timeout_seconds=settings.jc_export_review_timeout_seconds + 30,
        )

    async def review_for_export(
        self,
        profile_id: str,
        *,
        actor: UserActor,
        elevation_level: str = "elevated",
        locale: str = TRACK_ZH,
        draft_id: str | None = None,
    ) -> dict:
        report("read")
        profile_resp = await self._profiles.get(profile_id, actor=actor)
        track = normalize_track(locale)
        draft: ResumeDraft | None = None
        if draft_id:
            found = await self._resumes.get_draft_by_id(draft_id)
            if found is None or found.profile_id != profile_id:
                raise NotFoundError("没找到这份优化稿，请重新生成预览。", code="draft_not_found")
            draft = found
        if draft is None:
            wanted = TRACK_BILINGUAL if is_bilingual_track(track) else track
            draft = await self._resumes.get_latest_draft(
                profile_id, elevation_level=elevation_level, locale=wanted
            )
        if draft is None:
            draft = await self._resumes.get_latest_draft(
                profile_id, elevation_level=elevation_level
            )
        if draft is None:
            raise NotFoundError("还没有可导出的优化稿，请先生成优化预览。")
        draft_id = draft.id
        report("read", done=True)
        report("rules")
        # Deterministic screening checks run before the model call so they are available
        # even if the reviewer fails: "will this be read" and "is this honest" are
        # different questions, and the user needs the first one either way.
        hints = await self._job_hints(profile_id, draft.job_id)
        draft_sections = dict(draft.sections or {})
        try:
            diagnostics = diagnose(
                draft_sections, job_keywords=hints.keywords or None
            ).to_dict()
        except Exception as exc:  # noqa: BLE001
            logger.warning("export review diagnostics failed", exc_info=exc)
            diagnostics = {
                "estimated_pages": 0,
                "total_chars": 0,
                "bullet_count": 0,
                "longest_bullet_chars": 0,
                "keyword_coverage": {
                    "total": 0,
                    "present": 0,
                    "missing": [],
                    "skills_only": [],
                },
                "notes": [],
            }
        # "Did the document keep my career" is a different question from both honesty
        # and readability, and it is the one users actually complain about. Measured
        # here against the confirmed profile, never used to block the download.
        try:
            coverage = audit_coverage(draft_sections, profile_resp.payload).to_dict()
        except Exception as exc:  # noqa: BLE001
            logger.warning("export review coverage failed", exc_info=exc)
            coverage = {
                "source_highlights": 0,
                "covered": 0,
                "draft_bullets": 0,
                "ratio": 1.0,
                "projects_missing": False,
                "dropped": [],
                "notes": [],
            }
        report("rules", done=True)
        report("model")
        try:
            result = await self._review_draft(draft)
        except Exception as exc:  # noqa: BLE001 — must not 500 the download screen
            logger.warning("export review_for_export failed", exc_info=exc)
            await self._db.rollback()
            result = self._review_unavailable_payload(
                notes="自动质检服务暂时不可用，本次没有核对简历内容。"
            )
            # "The reviewer is down" is exactly when the user most needs to know the
            # writer was also down. These two findings need no model, so losing the
            # reviewer must not lose them as well.
            result["issues"] = self._with_delivery_issues(
                result.get("issues") or [],
                (draft_sections.get("zh_sections") or {})
                if normalize_track(draft.locale) == TRACK_BILINGUAL
                else draft_sections,
            )
        report("model", status="done" if result.get("reviewed") else "unavailable")
        report("save")
        # _review_draft releases the pooled MySQL connection during the review model call,
        # so the ORM object must be re-loaded in a fresh transaction before writing.
        draft = await self._resumes.get_draft_by_id(draft_id)
        if draft is None:
            raise NotFoundError("优化稿已不存在，请重新生成优化预览。")
        draft.reviewer_status = self._reviewer_status(result)
        draft.reviewer_notes = result.get("notes")
        await self._db.commit()
        report("save", done=True)
        return {
            "draft_id": draft_id,
            **result,
            "diagnostics": diagnostics,
            "coverage": coverage,
        }

    async def list_tracks(
        self,
        profile_id: str,
        *,
        actor: Actor,
        elevation_level: str = "elevated",
    ) -> dict[str, Any]:
        profile_resp = await self._profiles.get(profile_id, actor=actor)
        payload = profile_resp.payload
        source = payload.meta.source_locale or profile_resp.locale or TRACK_ZH
        zh = await self._resumes.get_latest_draft(
            profile_id, elevation_level=elevation_level, locale=TRACK_ZH
        )
        en = await self._resumes.get_latest_draft(
            profile_id, elevation_level=elevation_level, locale=TRACK_EN
        )
        bilingual = await self._resumes.get_latest_draft(
            profile_id, elevation_level=elevation_level, locale=TRACK_BILINGUAL
        )
        status_map = payload.meta.i18n_status or {}

        def mono(draft: ResumeDraft | None, key: str) -> dict[str, Any]:
            if draft is not None:
                return {
                    "status": "ready",
                    "draft_id": draft.id,
                    "reviewer_status": draft.reviewer_status,
                }
            i18n_st = status_map.get(key, "pending")
            known = i18n_st if i18n_st in {"pending", "failed", "stale"} else "pending"
            return {"status": known, "draft_id": None}

        zh_state = mono(zh, TRACK_ZH)
        en_state = mono(en, TRACK_EN)
        if zh and en:
            bi_state: dict[str, Any] = {
                "status": "ready",
                "draft_id": bilingual.id if bilingual else None,
                "reason": None,
            }
        else:
            bi_state = {
                "status": "blocked",
                "draft_id": None,
                "reason": "en_not_ready" if not en else "zh_not_ready",
            }
        return {
            "source_locale": source,
            "tracks": {TRACK_ZH: zh_state, TRACK_EN: en_state, TRACK_BILINGUAL: bi_state},
        }

    async def localize(
        self,
        profile_id: str,
        *,
        actor: Actor,
        source_locale: str | None = None,
    ) -> dict[str, Any]:
        await self._profiles.get(profile_id, actor=actor)
        row = await ProfileStore(self._db).get_by_id(profile_id)
        if row is None:
            raise NotFoundError("档案不存在或已删除。", code="profile_not_found")
        payload = ProfilePayload.model_validate(row.payload or {})
        if source_locale:
            payload.meta.source_locale = normalize_track(source_locale)
            row.locale = payload.meta.source_locale
            row.payload = payload.model_dump(mode="json")
            await self._db.commit()
        await self.prepare_tracks(profile_id, elevation_level="conservative")
        return await self.list_tracks(profile_id, actor=actor, elevation_level="conservative")

    async def ensure_i18n(self, profile_id: str) -> None:
        row = await ProfileStore(self._db).get_by_id(profile_id)
        if row is None:
            return
        payload = ProfilePayload.model_validate(row.payload or {})
        source = detect_profile_source_locale(payload)
        has_source = source in payload.i18n
        target = other_monolingual(source)
        has_target = target in payload.i18n
        if has_source and has_target and payload.meta.i18n_status.get(target) == "ready":
            return
        await self.prepare_tracks(profile_id, elevation_level="conservative")

    async def prepare_tracks(
        self, profile_id: str, *, elevation_level: str = "conservative"
    ) -> None:
        row = await ProfileStore(self._db).get_by_id(profile_id)
        if row is None:
            return
        payload = ProfilePayload.model_validate(row.payload or {})
        source = detect_profile_source_locale(payload)
        payload.meta.source_locale = source
        row.locale = source
        i18n = dict(payload.i18n)
        i18n[source] = project_i18n_pack(payload)
        target = other_monolingual(source)
        status = dict(payload.meta.i18n_status)
        status[source] = "ready"
        status[target] = "pending"
        payload.i18n = i18n
        payload.meta.i18n_status = status
        # Bump version on every payload write: intake already snapshotted v1; a second
        # write at the same version hits ix_jc_profile_snapshot_profile_version.
        with bind_snapshot_source("track_prepare"):
            row.version += 1
            row.payload = payload.model_dump(mode="json")
            await self._db.commit()

        try:
            pack = await self._localizer.translate(payload, target_locale=target)
            payload = ProfilePayload.model_validate(row.payload or {})
            i18n = dict(payload.i18n)
            i18n[target] = pack
            status = dict(payload.meta.i18n_status)
            status[target] = "ready"
            payload.i18n = i18n
            payload.meta.i18n_status = status
            with bind_snapshot_source("track_prepare"):
                row.version += 1
                row.payload = payload.model_dump(mode="json")
                await self._db.commit()
        except Exception:  # noqa: BLE001
            payload = ProfilePayload.model_validate(row.payload or {})
            status = dict(payload.meta.i18n_status)
            status[target] = "failed"
            payload.meta.i18n_status = status
            with bind_snapshot_source("track_prepare"):
                row.version += 1
                row.payload = payload.model_dump(mode="json")
                await self._db.commit()
            return

        payload = ProfilePayload.model_validate(row.payload or {})
        profile_version = row.version
        missing: list[str] = []
        for loc in (TRACK_ZH, TRACK_EN):
            existing = await self._resumes.get_latest_draft(
                profile_id, elevation_level=elevation_level, locale=loc
            )
            if existing is None:
                missing.append(loc)
        if not missing:
            return

        # Generate every missing track with no open transaction: each call runs for
        # minutes and a remote MySQL server would drop the idle pooled connection.
        await release_db_connection(self._db)
        generated: list[tuple[str, dict, list]] = []
        for loc in missing:
            sections, elevation_map = await self._elevator.build_sections(
                payload, elevation_level=elevation_level, locale=loc
            )
            generated.append((loc, sections, elevation_map))

        for loc, sections, elevation_map in generated:
            draft = ResumeDraft(
                id=new_id("rdft"),
                profile_id=profile_id,
                profile_version=profile_version,
                job_id=None,
                elevation_level=elevation_level,
                locale=loc,
                template_id=template_id_for_locale(loc),
                sections=sections,
                elevation_map=elevation_map,
                reviewer_status=ReviewerStatus.PENDING,
                reviewer_notes=None,
                exported_at=None,
            )
            await self._resumes.create_draft(draft)
        await self._db.commit()

    @staticmethod
    def _job_context_hash(hints: JobHints) -> str:
        return hashlib.sha256(json.dumps(asdict(hints), ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _writer_failed(sections: dict[str, Any]) -> bool:
        """Whether this draft is the writer-down fallback rather than a written document.

        `source_layout` only. `structure_guarded` is excluded on purpose: there the
        writer did run and produced prose, and only the blocks whose paragraph
        boundaries it changed were restored — regenerating costs another call without
        being any more likely to succeed.

        Note a draft generated with `JC_LLM_ENABLED=false` carries no `generation` key at
        all, so it is not caught here. That matters: treating it as permanently stale
        would make every preview regenerate forever in a deployment that has the writer
        deliberately switched off.
        """
        generation = sections.get("generation")
        return isinstance(generation, dict) and generation.get("mode") == "source_layout"

    async def _is_stale_for_profile(
        self,
        draft: ResumeDraft,
        *,
        profile_id: str,
        actor: Actor,
    ) -> bool:
        """Does the cached draft match the current profile version and writing options?

        `preview()` serves the latest stored draft whenever the template matches, so
        that a re-open of the page does not re-run the writer. That caching is right
        for "just looking again" but wrong for "I changed the framing angle and
        expect a new document" -- changing `role_family` or `framing_emphases` saves
        to the profile (`updateWritingOptions`) and asks the frontend to reload the
        preview, but a GET that only checked `template_id` kept handing back the old
        draft, so switching angles visibly did nothing.

        Compares against what `elevate()` would resolve *now*, the same two calls it
        makes, rather than trusting anything cached on the draft itself -- the draft's
        own `sections.role_family`/`framing_emphases` are what the writer actually used,
        which already reflects a previous resolution and would make this check compare
        a value against itself.
        """
        sections = draft.sections if isinstance(draft.sections, dict) else {}
        if self._writer_failed(sections):
            # Not a draft of this profile so much as a record that the writer was down.
            # Serving it from cache means a transient gateway failure makes the profile's
            # own wording the permanent "optimized" resume: the user reopens the preview,
            # gets the identical unoptimized document, and concludes the optimizer is
            # useless. Costs one writer attempt per preview while the outage lasts, which
            # is the better side of that trade.
            return True
        profile_resp = await self._profiles.get(profile_id, actor=actor)
        if draft.profile_version != profile_resp.version:
            return True
        stamped_family = sections.get("role_family")
        stamped_emphases = sections.get("framing_emphases")
        hints = await self._job_hints(profile_id, draft.job_id)
        if draft.job_id and sections.get("job_context_hash") != self._job_context_hash(hints):
            return True
        if stamped_family is None and stamped_emphases is None:
            # Pre-dates this field existing on the draft. Treat as fresh rather than
            # forcing a regeneration of every resume ever written before this check
            # shipped -- the cost of being wrong here is a missed refresh, not a
            # wrong one, and the user can always hit "重新生成".
            return False
        payload = profile_resp.payload
        current_family = resolve_role_family(
            override=payload.preferences.role_family,
            job_category=hints.role_category,
            job_title=hints.title,
            profile_titles=tuple(e.title for e in payload.experiences[:2]),
        )
        current_emphases = resolve_emphases(
            payload.preferences.framing_emphases, role_family=current_family
        )
        return (
            stamped_family != current_family or stamped_emphases != current_emphases
        )

    async def _ensure_draft(
        self,
        profile_id: str,
        *,
        actor: Actor,
        elevation_level: str,
        locale: str = TRACK_ZH,
        template_id: str | None = None,
        job_id: str | None = None,
    ) -> ResumeDraft:
        resp = await self.elevate(
            profile_id,
            actor=actor,
            elevation_level=elevation_level,
            locale=locale,
            template_id=template_id,
            job_id=job_id,
        )
        draft = await self._resumes.get_draft_by_id(resp.id)
        if draft is None:
            raise NotFoundError("没找到这份优化稿，请重新生成预览。", code="draft_not_found")
        return draft

    async def _elevate_bilingual(
        self,
        profile_id: str,
        *,
        actor: Actor,
        elevation_level: str,
        job_id: str | None = None,
    ) -> ResumeDraftResponse:
        draft = await self._ensure_bilingual_draft(
            profile_id, actor=actor, elevation_level=elevation_level, job_id=job_id
        )
        return self._to_draft_response(draft)

    async def _ensure_bilingual_draft(
        self,
        profile_id: str,
        *,
        actor: Actor,
        elevation_level: str,
        force: bool = False,
        job_id: str | None = None,
    ) -> ResumeDraft:
        zh = await self._resumes.get_latest_draft(
            profile_id, elevation_level=elevation_level, locale=TRACK_ZH, job_id=job_id
        )
        en = await self._resumes.get_latest_draft(
            profile_id, elevation_level=elevation_level, locale=TRACK_EN, job_id=job_id
        )
        # Decide before either writer releases the transaction and expires ORM rows.
        refresh_zh = force or zh is None or await self._is_stale_for_profile(
            zh, profile_id=profile_id, actor=actor
        )
        refresh_en = force or en is None or await self._is_stale_for_profile(
            en, profile_id=profile_id, actor=actor
        )
        zh_id = zh.id if zh else None
        en_id = en.id if en else None
        if refresh_zh:
            zh = await self._ensure_draft(
                profile_id, actor=actor, elevation_level=elevation_level, locale=TRACK_ZH, job_id=job_id
            )
            zh_id = zh.id
        if refresh_en:
            en = await self._ensure_draft(
                profile_id, actor=actor, elevation_level=elevation_level, locale=TRACK_EN, job_id=job_id
            )
            en_id = en.id
        # Generation may roll back/expire a previously loaded sibling draft.
        zh = await self._resumes.get_draft_by_id(zh_id)
        en = await self._resumes.get_draft_by_id(en_id)
        if zh is None or en is None:
            raise NotFoundError("双语优化稿未生成完整，请重新生成预览。", code="draft_not_found")
        # Read the opt-in off the live profile rather than off the zh draft: the draft
        # only records that a photo *was* drawable for the Chinese track, not whether
        # the user agreed to ship it abroad. Fetched once and reused for the version
        # stamp below.
        profile_resp = await self._profiles.get(profile_id, actor=actor)
        photo = profile_resp.payload.contact.photo
        show_photo = bool(photo and photo.renders_for_locale(TRACK_BILINGUAL))
        sections = compose_bilingual_sections(
            zh.sections,
            en.sections,
            zh_draft_id=zh.id,
            en_draft_id=en.id,
            show_photo=show_photo,
        )
        existing = await self._resumes.get_latest_draft(
            profile_id, elevation_level=elevation_level, locale=TRACK_BILINGUAL, job_id=job_id
        )
        if (
            existing is not None
            and existing.sections.get("zh_draft_id") == zh.id
            and existing.sections.get("en_draft_id") == en.id
            # Toggling the bilingual photo opt-in changes nothing about the two
            # monolingual drafts, so the id pair still matches and a cached wrapper
            # would be served with the old photo state. Comparing the rendered
            # outcome is what makes the switch take effect on the next preview.
            and ("photo_data_uri" in (existing.sections.get("header") or {})) == show_photo
        ):
            return existing
        draft = ResumeDraft(
            id=new_id("rdft"),
            profile_id=profile_id,
            profile_version=profile_resp.version,
            job_id=job_id,
            elevation_level=elevation_level,
            locale=TRACK_BILINGUAL,
            template_id="zh-en-bilingual",
            sections=sections,
            elevation_map=[],
            reviewer_status=ReviewerStatus.PENDING,
            reviewer_notes=None,
            exported_at=None,
        )
        await self._resumes.create_draft(draft)
        await self._db.flush()
        await self._db.refresh(draft)
        await self._db.commit()
        return draft

    async def _review_draft(self, draft: ResumeDraft) -> dict[str, Any]:
        from jc.stores.profile_store import ProfileStore
        profile = await ProfileStore(self._db).get_by_id(draft.profile_id)
        source_profile = profile.payload if profile else None
        # Snapshot everything the reviewer needs, then release the pooled MySQL connection:
        # a remote server drops an idle transaction long before a slow review call returns.
        draft_id = draft.id
        locale = draft.locale
        sections = dict(draft.sections or {})
        # The playbook the draft was written against must be the one it is reviewed
        # against, otherwise a non-quantified role gets written correctly and then
        # blocked by engineering expectations at the gate.
        role_family = self._draft_role_family(sections, source_profile)
        await release_db_connection(self._db)
        try:
            async with asyncio.timeout(settings.jc_export_review_timeout_seconds):
                return await self._review_snapshot(locale, sections, source_profile, role_family)
        except TimeoutError:
            logger.warning("Resume review timed out for draft %s", draft_id)
            check_sections = (
                (sections.get("zh_sections") or {}) if locale == TRACK_BILINGUAL else sections
            )
            issues = self._with_delivery_issues(
                self._with_structure_issues(
                    self._with_invariant_issues([], check_sections, source_profile),
                    check_sections, role_family,
                ),
                check_sections,
            )
            issues.append({
                "code": "reviewer_timeout", "severity": "warning",
                "message": "自动质检超时，未完成模型核对；可以重试检查或自行确认后导出。",
            })
            return self._review_payload(
                passed=False, available=False,
                notes="自动质检超时，未完成模型核对。规则检查结果仍可查看。",
                issues=issues,
            )

    async def _review_snapshot(
        self, locale: str, sections: dict[str, Any],
        source_profile: dict[str, Any] | None, role_family: str,
    ) -> dict[str, Any]:
        if locale == TRACK_BILINGUAL:
            zh_sec = sections.get("zh_sections") or {}
            en_sec = sections.get("en_sections") or {}
            # Each track is a draft in its own right and stamps its own family. Use the
            # track's stamp where present so a wrapper built from drafts generated under
            # different preferences still reviews each one against what wrote it.
            # Structured concurrency also cancels/awaits the sibling if a track
            # raises unexpectedly; no paid call may outlive its request.
            async with asyncio.TaskGroup() as tasks:
                zh_task = tasks.create_task(self._reviewer.review(
                    sections=zh_sec,
                    source_profile=source_profile,
                    role_family=self._track_role_family(zh_sec, role_family),
                ))
                en_task = tasks.create_task(self._reviewer.review(
                    sections=en_sec,
                    source_profile=source_profile,
                    role_family=self._track_role_family(en_sec, role_family),
                ))
            zh_review, en_review = zh_task.result(), en_task.result()
            # The invariant audit reads the 中文 track (the English track restates the
            # same facts), so it is attached to the zh half rather than run twice.
            issues = [
                {**issue, "track": TRACK_ZH}
                for issue in self._with_delivery_issues(
                    self._with_structure_issues(
                        self._with_invariant_issues(zh_review.issues, zh_sec, source_profile),
                        zh_sec,
                        self._track_role_family(zh_sec, role_family),
                    ),
                    zh_sec,
                )
            ] + [
                {**issue, "track": TRACK_EN}
                for issue in self._with_delivery_issues(en_review.issues, en_sec)
            ]
            # Either track failing to produce a verdict means we have no verdict for
            # the pair; see `_review_payload` for why that is not a failure.
            available = zh_review.available and en_review.available
            passed = (
                zh_review.status == ReviewerStatus.PASSED
                and en_review.status == ReviewerStatus.PASSED
            )
            notes = "；".join(n for n in [zh_review.notes, en_review.notes] if n)
            return self._review_payload(
                passed=passed,
                available=available,
                notes=notes or None,
                issues=issues,
            )
        review = await self._reviewer.review(
            sections=sections, source_profile=source_profile, role_family=role_family
        )
        issues = self._with_delivery_issues(
            self._with_structure_issues(
                self._with_invariant_issues(review.issues, sections, source_profile),
                sections,
                role_family,
            ),
            sections,
        )
        return self._review_payload(
            passed=review.status == ReviewerStatus.PASSED,
            available=review.available,
            notes=review.notes,
            issues=issues,
        )

    @staticmethod
    def _review_unavailable_payload(notes: str) -> dict[str, Any]:
        return ResumeService._review_payload(
            passed=True,
            available=False,
            notes=notes,
            issues=[
                {
                    "code": "reviewer_unavailable",
                    "severity": "warning",
                    "message": "Reviewer raised before returning a verdict",
                }
            ],
        )

    @staticmethod
    def _reviewer_status(result: dict[str, Any]) -> ReviewerStatus:
        """Persist what the reviewer concluded, not whether the export proceeded.

        `PENDING` is the honest record for "no verdict": a draft nobody checked must not
        be stored as having passed, and storing it as FAILED would later read as if the
        draft had been rejected on its merits.
        """
        status = result.get("status")
        if status == "passed":
            return ReviewerStatus.PASSED
        if status == "failed":
            return ReviewerStatus.FAILED
        return ReviewerStatus.PENDING

    @staticmethod
    def _review_payload(
        *,
        passed: bool,
        available: bool,
        notes: str | None,
        issues: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Shape the reviewer verdict for the API, separating *verdict* from *advice*.

        Three states, not two:

        - `passed`      — reviewed, nothing blocking.
        - `failed`      — reviewed, something to fix. Advisory as of V1: the findings
                          are shown and the user acknowledges them, because a false
                          positive (merging two highlights breaks attribution) used to
                          lock people out of their own document with no way forward.
        - `unavailable` — no verdict at all (gateway down, LLM off, unreadable
                          response). The user did not cause it and cannot fix it, so it
                          must not read as an accusation and must not withhold the file.

        `can_export` stays in the contract for older clients but is now always true;
        the gate the UI actually honours is `blocking_issue_count` plus an explicit
        acknowledgement. See `TECH-RESUME-WRITING.md` §6.3.1.
        """
        if not available:
            status = "unavailable"
        elif passed:
            status = "passed"
        else:
            status = "failed"
        blocking = [
            issue
            for issue in issues
            if str(issue.get("severity") or issue.get("code") or "error").strip().lower()
            != "warning"
        ]
        return {
            "status": status,
            "notes": notes,
            "issues": issues,
            "reviewed": available,
            "blocking_issue_count": len(blocking),
            # Export is never withheld by the reviewer. Kept for contract stability.
            "can_export": True,
        }

    @staticmethod
    def _with_invariant_issues(
        issues: list[dict[str, Any]],
        sections: dict[str, Any],
        source_profile: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Append deterministic unsupported-content findings the reviewer did not raise.

        The reviewer is the gate, and it reads intent in a way arithmetic cannot. But it
        is a model call, so "fabrication is caught" has been an assumption about model
        behaviour with nothing behind it. `writing_invariants` can prove a narrower claim
        without a model: this number, this ownership verb, appears nowhere in the profile.

        Deliberately **additive and advisory**:

        - These are appended as `warning`, so they cannot block a download. A
          deterministic blocker would fire on legitimate writing (merging two highlights
          breaks attribution) and lock users out of their own document — the failure
          already fixed once in `ResumeReviewer._has_blocking_issue`.
        - Findings the reviewer already reported for the same bullet are dropped, so the
          user does not read the same defect twice in different words.
        """
        if not source_profile:
            return list(issues)
        try:
            payload = ProfilePayload.model_validate(source_profile)
        except Exception:  # noqa: BLE001 — a malformed payload is the reviewer's problem
            return list(issues)

        already = {
            str(issue.get("field") or "").strip()
            for issue in issues
            if str(issue.get("field") or "").strip()
        }
        out = list(issues)
        from jc.domain.claim_constraints import retracted_claim_findings

        for finding in retracted_claim_findings(sections, payload):
            if not any(i.get("code") == finding["code"] and i.get("field") == finding["field"] for i in out):
                out.append({"severity": "warning", **finding})
        for finding in audit_additions(sections, payload).fabrications:
            if finding.field_path in already:
                continue
            out.append(
                {
                    "severity": "warning",
                    "code": f"invariant_{finding.kind}",
                    "field": finding.field_path,
                    "message": f"{finding.detail}如果确实发生过，把它补进档案再重新生成。",
                }
            )
        return out

    #: Placeholders the deterministic builder writes into a block with no source
    #: highlights. They are ours, not the model's, so they never reach the reviewer's
    #: "placeholder text" rule — which reads the draft as if a model wrote all of it.
    _PENDING_PLACEHOLDERS = ("（待补充经历要点）", "(Add experience highlights)")

    @classmethod
    def _with_delivery_issues(
        cls,
        issues: list[dict[str, Any]],
        sections: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Report what this file *is* before the user sends it to an employer.

        Two defects neither the reviewer nor the structure audit can see, because both
        read the draft as a document rather than asking how it was produced:

        1. **The AI writer never ran.** `generation.mode == "source_layout"` means the
           writer chain failed and the document is the profile's own wording, laid out.
           The preview panel says so; the export screen did not read the field at all,
           so a failed optimization downloaded under the same filename as a successful
           one. That is what makes "优化效果不好" indistinguishable from "优化没有发生".
        2. **A placeholder is on the page.** `（待补充经历要点）` is written by our own
           builder for a role with no highlights, so the reviewer's placeholder rule
           never sees it as model output. Shipping it to an employer is strictly worse
           than shipping a shorter resume.

        `warning`, consistent with every other deterministic finding here: a structural
        judgement must not lock a user out of their own document (see
        `_with_invariant_issues`). The point is that the export screen can no longer be
        silent about it — the user decides, but from here on they are told.
        """
        out = list(issues)
        generation = sections.get("generation")
        mode = (generation or {}).get("mode") if isinstance(generation, dict) else None
        if mode in {"source_layout", "structure_guarded"}:
            known = {str(i.get("code") or "") for i in out}
            if "generation_not_optimized" not in known:
                out.append(
                    {
                        "severity": "warning",
                        "code": "generation_not_optimized",
                        "field": "generation.mode",
                        "message": (
                            str((generation or {}).get("warning") or "").strip()
                            or "AI 写作未完成，当前内容按档案原文排版。"
                        )
                        + "导出前建议回到优化预览点「重新生成」。",
                    }
                )
        for key, label in (("experience_blocks", "经历"), ("project_blocks", "项目")):
            for index, block in enumerate(sections.get(key) or []):
                if not isinstance(block, dict):
                    continue
                for b_index, bullet in enumerate(block.get("bullets") or []):
                    if not isinstance(bullet, str):
                        continue
                    if bullet.strip() not in cls._PENDING_PLACEHOLDERS:
                        continue
                    out.append(
                        {
                            "severity": "warning",
                            "code": "placeholder_bullet",
                            "field": f"{key}[{index}].bullets[{b_index}]",
                            "message": (
                                f"这段{label}还是占位文字「{bullet.strip()}」，会原样印进导出文件。"
                                "请补充这段经历的要点，或在档案里删掉这段经历。"
                            ),
                        }
                    )
        return out

    @staticmethod
    def _with_structure_issues(
        issues: list[dict[str, Any]],
        sections: dict[str, Any],
        role_family: str | None,
    ) -> list[dict[str, Any]]:
        """Append document-level defects the reviewer is not asked to judge.

        The reviewer reads for honesty and sentence quality. Structure — a missing scope
        line, a role whose first bullet is its weakest, a summary that never states a
        conclusion — is measurable without a model, and these are exactly the defects
        that make a factually perfect resume fail a screen.

        `warning` without exception, for the same reason as the invariant findings: a
        structural preference must never be able to lock a user out of their own
        document. Deduplicated against what the reviewer already said about the same
        field so the user does not read one defect twice.
        """
        already = {
            str(issue.get("field") or "").strip()
            for issue in issues
            if str(issue.get("field") or "").strip()
        }
        out = list(issues)
        for item in audit_structure(sections, role_family=role_family).issues:
            if item.field_path in already:
                continue
            already.add(item.field_path)
            out.append(
                {
                    "severity": "warning",
                    "code": f"structure_{item.code}",
                    "field": item.field_path,
                    "message": item.message,
                }
            )
        # Unmet blueprint requirements last: they are the broadest statements ("分量与
        # 经历不相称") and would otherwise bury the specific findings above them.
        # Deduplicated by code rather than field, because several requirements legitimately
        # point at the same field while saying different things about it.
        seen_codes = {str(i.get("code") or "") for i in out}
        for item in evaluate_blueprint(sections, role_family=role_family).unmet_issues():
            if item["code"] in seen_codes:
                continue
            seen_codes.add(item["code"])
            out.append(item)
        return out

    @staticmethod
    def _track_role_family(track: dict[str, Any], fallback: str) -> str:
        stamped = track.get("role_family")
        if isinstance(stamped, str) and stamped.strip():
            return stamped.strip()
        return fallback

    @staticmethod
    def _draft_role_family(
        sections: dict[str, Any],
        source_profile: dict[str, Any] | None,
    ) -> str:
        """Recover the family a draft was written against.

        Drafts written before this field existed, and bilingual wrappers that carry no
        family of their own, fall back to the user's stored preference and then to the
        profile's own titles.
        """
        stamped = sections.get("role_family")
        if isinstance(stamped, str) and stamped.strip():
            return stamped.strip()
        if sections.get("track") == "bilingual":
            for key in ("zh_sections", "en_sections"):
                nested = sections.get(key)
                if isinstance(nested, dict):
                    nested_family = nested.get("role_family")
                    if isinstance(nested_family, str) and nested_family.strip():
                        return nested_family.strip()
        profile = source_profile or {}
        prefs = profile.get("preferences") if isinstance(profile, dict) else None
        override = prefs.get("role_family") if isinstance(prefs, dict) else None
        experiences = profile.get("experiences") if isinstance(profile, dict) else None
        titles: tuple[str | None, ...] = ()
        if isinstance(experiences, list):
            titles = tuple(
                exp.get("title") for exp in experiences[:2] if isinstance(exp, dict)
            )
        return resolve_role_family(override=override, profile_titles=titles)

    async def _job_hints(self, profile_id: str, job_id: str | None) -> JobHints:
        if not job_id:
            return JobHints()
        from jc.stores.job_store import JobStore

        job = await JobStore(self._db).get_by_id(job_id)
        if job is None or job.profile_id != profile_id:
            return JobHints()
        req = job.requirements or {}
        keywords = list(req.get("keywords") or []) + list(req.get("must_have_skills") or [])
        report = job.fit_report if isinstance(job.fit_report, dict) else {}
        return JobHints(
            keywords=[str(k) for k in keywords if str(k).strip()],
            title=job.title,
            role_category=job.role_category,
            gaps=[str(g) for g in (job.fit_gaps or []) if str(g).strip()],
            elevate_hints=[
                str(h) for h in (report.get("elevate_hints") or []) if str(h).strip()
            ],
        )

    async def get_export(self, export_id: str, *, actor: UserActor) -> ExportJobResponse:
        job = await self._resumes.get_export_job(export_id)
        if job is None or job.user_id != actor.user_id:
            raise NotFoundError("没找到这次导出任务，请重新导出。", code="export_job_not_found")
        url = download_url_for_key(job.storage_key) if job.storage_key else None
        return ExportJobResponse(
            id=job.id,
            status=job.status,
            format=job.format,
            download_url=url,
            error_message=job.error_message,
        )

    def _with_live_photo(
        self,
        sections: dict[str, Any],
        payload: Any,
        *,
        locale: str,
    ) -> dict[str, Any]:
        """Re-resolve the headshot against the live profile before rendering.

        Applied on the preview and on every export so the two cannot disagree. Three
        things were wrong without it: `_normalize_sections` rebuilt the header from a
        text-field whitelist and silently dropped `photo_data_uri`, so the preview
        never showed a photo; export rendered the stored draft verbatim and kept it,
        so the photo appeared for the first time in the downloaded file; and because a
        draft is a snapshot, toggling the switch did nothing until the draft was
        regenerated.

        The bilingual document needs both headers written. Its top-level `header` is a
        flattened copy of the zh one, but `render_html` passes `zh_sections` to the
        macro, so writing only the copy would leave the page unchanged -- the same
        two-places rule `compose_bilingual_sections` already follows for stripping.
        """
        photo = None
        try:
            contact = payload.contact if hasattr(payload, "contact") else None
            photo = getattr(contact, "photo", None)
        except Exception:  # noqa: BLE001
            photo = None
        # Resolve once: each call re-reads the object out of storage.
        uri = photo_data_uri(photo, locale=locale)
        if sections.get("track") == "bilingual" or locale == TRACK_BILINGUAL:
            out = set_header_photo(sections, uri)
            zh = out.get("zh_sections")
            if isinstance(zh, dict):
                out["zh_sections"] = set_header_photo(zh, uri)
            return out
        return set_header_photo(sections, uri)

    def _normalize_sections(
        self,
        sections: dict[str, Any],
        profile_payload: Any,
        *,
        locale: str = TRACK_ZH,
    ) -> dict[str, Any]:
        if sections.get("track") == "bilingual" or locale == TRACK_BILINGUAL:
            # Legacy bilingual caches need the same confirmed-wording repair as
            # single-language drafts; the wrapper itself is not a source text track.
            out = dict(sections)
            for key, track in (("zh_sections", TRACK_ZH), ("en_sections", TRACK_EN)):
                child = sections.get(key)
                if isinstance(child, dict):
                    out[key] = self._normalize_sections(child, profile_payload, locale=track)
            return out
        builder = ResumeDraftBuilder()
        payload = (
            profile_payload
            if isinstance(profile_payload, ProfilePayload)
            else ProfilePayload.model_validate(profile_payload)
        )
        baseline, _ = builder.build(payload, elevation_level="conservative", locale=locale)
        out = dict(sections)
        for key in (
            "header",
            "summary",
            "education_blocks",
            "skills",
            "section_order",
            # Structure is computed at generation time and read by the UI. Dropping it
            # here would make the composition invisible on every re-render of a stored
            # draft, which is most of the times the user looks at one.
            "structure",
        ):
            out.setdefault(key, baseline.get(key))
        if not out.get("experience_blocks"):
            out["experience_blocks"] = baseline.get("experience_blocks") or []
        header = out.get("header") or {}
        if not isinstance(header, dict):
            header = {}
        baseline_header = baseline.get("header") or {}
        pending = "Name pending" if locale.startswith("en") else "姓名待填"
        out["header"] = {
            "name": header.get("name") or baseline_header.get("name") or pending,
            "headline": header.get("headline") or baseline_header.get("headline") or "",
            "contact_line": header.get("contact_line") or baseline_header.get("contact_line") or "",
        }
        return preserve_confirmed(out, payload, baseline)

    @staticmethod
    def _to_draft_response(
        draft: ResumeDraft, *, sections: dict[str, Any] | None = None
    ) -> ResumeDraftResponse:
        """`sections` overrides the stored snapshot for render-time resolutions.

        Used by the preview so the structured-cards view, which reads the header off
        this response rather than off the rendered HTML, sees the same headshot the
        A4 preview and the export do. Defaults to the stored draft so no other caller
        has to think about it.
        """
        return ResumeDraftResponse(
            id=draft.id,
            profile_id=draft.profile_id,
            profile_version=draft.profile_version,
            elevation_level=draft.elevation_level,
            locale=draft.locale,
            template_id=draft.template_id,
            sections=draft.sections if sections is None else sections,
            elevation_map=draft.elevation_map,
            reviewer_status=draft.reviewer_status,
            created_at=draft.created_at,
        )
