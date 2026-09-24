"""Resume elevate and export."""

from __future__ import annotations

from typing import Any

from agentkit.common.ids import new_id
from agentkit.web.auth import Actor, UserActor
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.exceptions import AppError, NotFoundError
from jobcome.models.enums import ExportFormat, ExportJobStatus, ReviewerStatus
from jobcome.models.resume import ExportJob, ResumeDraft
from jobcome.resume_locale import (
    TRACK_BILINGUAL,
    TRACK_EN,
    TRACK_ZH,
    is_bilingual_track,
    normalize_track,
    other_monolingual,
    template_id_for_locale,
)
from jobcome.schemas.profile_payload import ProfilePayload
from jobcome.schemas.resume import (
    ElevatePreviewResponse,
    ExportJobResponse,
    ExportRequest,
    ResumeDraftResponse,
)
from jobcome.services.localize_service import LocalizeService
from jobcome.services.profile_i18n import (
    detect_profile_source_locale,
    project_i18n_pack,
)
from jobcome.services.profile_service import ProfileService
from jobcome.services.resume_draft_builder import ResumeDraftBuilder
from jobcome.services.resume_elevator import ResumeElevator
from jobcome.services.resume_render_engine import ResumeRenderEngine
from jobcome.services.resume_reviewer import ResumeReviewer
from jobcome.storage_backend import get_storage_backend
from jobcome.storage_client import download_url_for_key
from jobcome.stores.profile_store import ProfileStore
from jobcome.stores.resume_store import ResumeStore


def compose_bilingual_sections(
    zh_sections: dict[str, Any],
    en_sections: dict[str, Any],
    *,
    zh_draft_id: str,
    en_draft_id: str,
) -> dict[str, Any]:
    return {
        "track": "bilingual",
        "locale": TRACK_BILINGUAL,
        "zh_draft_id": zh_draft_id,
        "en_draft_id": en_draft_id,
        "zh_sections": zh_sections,
        "en_sections": en_sections,
        "header": zh_sections.get("header") or {},
        "summary": zh_sections.get("summary"),
        "experience_blocks": zh_sections.get("experience_blocks") or [],
        "education_blocks": zh_sections.get("education_blocks") or [],
        "skills_block": zh_sections.get("skills_block") or {},
        "section_order": ["summary", "experience", "education", "skills"],
    }


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
                profile_id, actor=actor, elevation_level=elevation_level
            )
        template_id = template_id or template_id_for_locale(track)
        profile_resp = await self._profiles.get(profile_id, actor=actor)
        payload = profile_resp.payload
        job_keywords, job_title = await self._job_hints(profile_id, job_id)
        sections, elevation_map = await self._elevator.build_sections(
            payload,
            elevation_level=elevation_level,
            locale=track,
            job_keywords=job_keywords,
            job_title=job_title,
        )
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

    async def preview(
        self,
        profile_id: str,
        *,
        actor: Actor,
        elevation_level: str,
        locale: str = TRACK_ZH,
        job_id: str | None = None,
    ) -> ElevatePreviewResponse:
        track = normalize_track(locale)
        if is_bilingual_track(track):
            draft = await self._ensure_bilingual_draft(
                profile_id, actor=actor, elevation_level=elevation_level
            )
        elif job_id:
            draft_resp = await self.elevate(
                profile_id,
                actor=actor,
                elevation_level=elevation_level,
                locale=track,
                job_id=job_id,
            )
            draft = await self._resumes.get_draft_by_id(draft_resp.id)
            if draft is None:
                raise NotFoundError("Draft not found")
        else:
            template_id = template_id_for_locale(track)
            draft = await self._resumes.get_latest_draft(
                profile_id, elevation_level=elevation_level, locale=track
            )
            if draft is None or draft.template_id != template_id:
                draft_resp = await self.elevate(
                    profile_id,
                    actor=actor,
                    elevation_level=elevation_level,
                    locale=track,
                    template_id=template_id,
                )
                draft = await self._resumes.get_draft_by_id(draft_resp.id)
                if draft is None:
                    raise NotFoundError("Draft not found")
        profile_resp = await self._profiles.get(profile_id, actor=actor)
        sections = self._normalize_sections(draft.sections, profile_resp.payload, locale=draft.locale)
        html = self._renderer.render_html(sections, template_id=draft.template_id)
        return ElevatePreviewResponse(draft=self._to_draft_response(draft), html=html)

    async def export(
        self,
        profile_id: str,
        *,
        actor: UserActor,
        body: ExportRequest,
    ) -> ExportJobResponse:
        await self._profiles.get(profile_id, actor=actor)
        track = normalize_track(body.locale)
        template_id = body.template_id or template_id_for_locale(track)

        draft: ResumeDraft | None = None
        if body.draft_id:
            draft = await self._resumes.get_draft_by_id(body.draft_id)
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
            raise NotFoundError("No resume draft to export")

        review_result = await self._review_draft(draft)
        draft.reviewer_status = (
            ReviewerStatus.PASSED if review_result["can_export"] else ReviewerStatus.FAILED
        )
        draft.reviewer_notes = review_result.get("notes")
        if not review_result["can_export"]:
            await self._db.commit()
            raise AppError(
                review_result.get("notes") or "导出前审稿未通过，请根据提示修改档案后重试。",
                code="reviewer_failed",
            )

        job = ExportJob(
            id=new_id("expj"),
            user_id=actor.user_id,
            profile_id=profile_id,
            resume_draft_id=draft.id,
            format=body.format.value,
            locale=track,
            status=ExportJobStatus.PROCESSING,
        )
        await self._resumes.create_export_job(job)

        try:
            html = self._renderer.render_html(draft.sections, template_id=draft.template_id)
            if body.format == ExportFormat.PDF:
                try:
                    content = self._renderer.render_pdf(html)
                    ext = "pdf"
                    content_type = "application/pdf"
                except RuntimeError:
                    content = html.encode("utf-8")
                    ext = "html"
                    content_type = "text/html; charset=utf-8"
            else:
                content = self._renderer.render_docx(draft.sections)
                ext = "docx"
                content_type = (
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            storage_key = f"profiles/{profile_id}/export/{job.id}.{ext}"
            self._storage.put_object(storage_key, content, content_type=content_type)
            await self._resumes.mark_export_done(job, storage_key=storage_key)
            job_id = job.id
            job_status = job.status
            job_format = job.format
            download_url = download_url_for_key(storage_key)
            await self._db.commit()
            return ExportJobResponse(
                id=job_id,
                status=job_status,
                format=job_format,
                download_url=download_url,
            )
        except Exception as exc:  # noqa: BLE001
            await self._resumes.mark_export_failed(job, str(exc))
            job_id = job.id
            job_status = job.status
            job_format = job.format
            error_message = str(exc)[:512]
            await self._db.commit()
            return ExportJobResponse(
                id=job_id,
                status=job_status,
                format=job_format,
                error_message=error_message,
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
        await self._profiles.get(profile_id, actor=actor)
        track = normalize_track(locale)
        draft: ResumeDraft | None = None
        if draft_id:
            found = await self._resumes.get_draft_by_id(draft_id)
            if found is not None and found.profile_id == profile_id:
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
        result = await self._review_draft(draft)
        draft.reviewer_status = (
            ReviewerStatus.PASSED if result["can_export"] else ReviewerStatus.FAILED
        )
        draft.reviewer_notes = result.get("notes")
        await self._db.commit()
        return {"draft_id": draft.id, **result}

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
            return {"status": i18n_st if i18n_st in {"pending", "failed", "stale"} else "pending", "draft_id": None}

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
            raise NotFoundError("Profile not found")
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

    async def prepare_tracks(self, profile_id: str, *, elevation_level: str = "conservative") -> None:
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
            row.payload = payload.model_dump(mode="json")
            await self._db.commit()
        except Exception:  # noqa: BLE001
            payload = ProfilePayload.model_validate(row.payload or {})
            status = dict(payload.meta.i18n_status)
            status[target] = "failed"
            payload.meta.i18n_status = status
            row.payload = payload.model_dump(mode="json")
            await self._db.commit()
            return

        payload = ProfilePayload.model_validate(row.payload or {})
        for loc in (TRACK_ZH, TRACK_EN):
            existing = await self._resumes.get_latest_draft(
                profile_id, elevation_level=elevation_level, locale=loc
            )
            if existing is not None:
                continue
            sections, elevation_map = await self._elevator.build_sections(
                payload, elevation_level=elevation_level, locale=loc
            )
            draft = ResumeDraft(
                id=new_id("rdft"),
                profile_id=profile_id,
                profile_version=row.version,
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

    async def _ensure_draft(
        self,
        profile_id: str,
        *,
        actor: Actor,
        elevation_level: str,
        locale: str = TRACK_ZH,
        template_id: str | None = None,
    ) -> ResumeDraft:
        resp = await self.elevate(
            profile_id,
            actor=actor,
            elevation_level=elevation_level,
            locale=locale,
            template_id=template_id,
        )
        draft = await self._resumes.get_draft_by_id(resp.id)
        if draft is None:
            raise NotFoundError("Draft not found")
        return draft

    async def _elevate_bilingual(
        self,
        profile_id: str,
        *,
        actor: Actor,
        elevation_level: str,
    ) -> ResumeDraftResponse:
        draft = await self._ensure_bilingual_draft(
            profile_id, actor=actor, elevation_level=elevation_level
        )
        return self._to_draft_response(draft)

    async def _ensure_bilingual_draft(
        self,
        profile_id: str,
        *,
        actor: Actor,
        elevation_level: str,
    ) -> ResumeDraft:
        zh = await self._resumes.get_latest_draft(
            profile_id, elevation_level=elevation_level, locale=TRACK_ZH
        )
        en = await self._resumes.get_latest_draft(
            profile_id, elevation_level=elevation_level, locale=TRACK_EN
        )
        if zh is None:
            zh = await self._ensure_draft(
                profile_id, actor=actor, elevation_level=elevation_level, locale=TRACK_ZH
            )
        if en is None:
            en = await self._ensure_draft(
                profile_id, actor=actor, elevation_level=elevation_level, locale=TRACK_EN
            )
        sections = compose_bilingual_sections(
            zh.sections, en.sections, zh_draft_id=zh.id, en_draft_id=en.id
        )
        existing = await self._resumes.get_latest_draft(
            profile_id, elevation_level=elevation_level, locale=TRACK_BILINGUAL
        )
        if (
            existing is not None
            and existing.sections.get("zh_draft_id") == zh.id
            and existing.sections.get("en_draft_id") == en.id
        ):
            return existing
        profile_resp = await self._profiles.get(profile_id, actor=actor)
        draft = ResumeDraft(
            id=new_id("rdft"),
            profile_id=profile_id,
            profile_version=profile_resp.version,
            job_id=None,
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
        if draft.locale == TRACK_BILINGUAL:
            zh_sec = draft.sections.get("zh_sections") or {}
            en_sec = draft.sections.get("en_sections") or {}
            zh_review = await self._reviewer.review(sections=zh_sec)
            en_review = await self._reviewer.review(sections=en_sec)
            issues = [
                {**issue, "track": TRACK_ZH} for issue in zh_review.issues
            ] + [{**issue, "track": TRACK_EN} for issue in en_review.issues]
            can_export = (
                zh_review.status == ReviewerStatus.PASSED
                and en_review.status == ReviewerStatus.PASSED
            )
            notes = "；".join(n for n in [zh_review.notes, en_review.notes] if n)
            status = "passed" if can_export else "failed"
            return {"status": status, "notes": notes or None, "issues": issues, "can_export": can_export}
        review = await self._reviewer.review(sections=draft.sections)
        return {
            "status": review.status.value,
            "notes": review.notes,
            "issues": review.issues,
            "can_export": review.status == ReviewerStatus.PASSED,
        }

    async def _job_hints(
        self, profile_id: str, job_id: str | None
    ) -> tuple[list[str] | None, str | None]:
        if not job_id:
            return None, None
        from jobcome.stores.job_store import JobStore

        job = await JobStore(self._db).get_by_id(job_id)
        if job is None or job.profile_id != profile_id:
            return None, None
        req = job.requirements or {}
        keywords = list(req.get("keywords") or []) + list(req.get("must_have_skills") or [])
        return keywords, job.title

    async def get_export(self, export_id: str, *, actor: UserActor) -> ExportJobResponse:
        job = await self._resumes.get_export_job(export_id)
        if job is None or job.user_id != actor.user_id:
            raise NotFoundError("Export job not found")
        url = download_url_for_key(job.storage_key) if job.storage_key else None
        return ExportJobResponse(
            id=job.id,
            status=job.status,
            format=job.format,
            download_url=url,
            error_message=job.error_message,
        )

    def _normalize_sections(
        self,
        sections: dict[str, Any],
        profile_payload: Any,
        *,
        locale: str = TRACK_ZH,
    ) -> dict[str, Any]:
        if sections.get("track") == "bilingual" or locale == TRACK_BILINGUAL:
            return sections
        builder = ResumeDraftBuilder()
        payload = (
            profile_payload
            if isinstance(profile_payload, ProfilePayload)
            else ProfilePayload.model_validate(profile_payload)
        )
        baseline, _ = builder.build(payload, elevation_level="conservative", locale=locale)
        out = dict(sections)
        for key in ("header", "summary", "education_blocks", "skills", "section_order"):
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
        return out

    @staticmethod
    def _to_draft_response(draft: ResumeDraft) -> ResumeDraftResponse:
        return ResumeDraftResponse(
            id=draft.id,
            profile_id=draft.profile_id,
            profile_version=draft.profile_version,
            elevation_level=draft.elevation_level,
            locale=draft.locale,
            template_id=draft.template_id,
            sections=draft.sections,
            elevation_map=draft.elevation_map,
            reviewer_status=draft.reviewer_status,
            created_at=draft.created_at,
        )
