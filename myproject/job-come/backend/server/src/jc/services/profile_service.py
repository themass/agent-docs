"""Profile CRUD, upload, and confirm."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agentkit.common.ids import new_id
from agentkit.web.auth import Actor, UserActor
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from jc.config import settings
from jc.db.profile_snapshot_hook import bind_snapshot_source
from jc.exceptions import ConflictError, ForbiddenError, NotFoundError
from jc.models.enums import OwnerKind, ParseStatus, ProfileStatus
from jc.models.profile import Profile, ProfileSource
from jc.resume_locale import other_monolingual
from jc.schemas.profile import ProfileConfirmResponse, ProfileResponse, ProfileUpdateRequest
from jc.schemas.profile_payload import ProfilePayload
from jc.services.ingest_user_messages import USER_UPLOAD_PARSE_FAILED, public_parse_error
from jc.services.profile_i18n import detect_profile_source_locale
from jc.services.profile_ingest_quality import has_profile_facts
from jc.services.profile_ingest_service import IngestValidationError, ProfileIngestService
from jc.storage_backend import get_storage_backend
from jc.storage_keys import storage_key
from jc.stores.profile_store import ProfileStore
from jc.stores.user_store import UserStore

logger = logging.getLogger(__name__)


class ParseClaimLost(RuntimeError):
    """The worker no longer owns this parse attempt; stale results must not commit."""


class ProfileService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._profiles = ProfileStore(db)
        self._users = UserStore(db)
        self._ingest = ProfileIngestService()
        self._storage = get_storage_backend()

    async def list_profiles(self, *, actor: UserActor) -> dict:
        meta = await self._users.get_or_create_meta(actor.user_id)
        rows = await self._profiles.list_for_user(actor.user_id)
        active_id = meta.active_profile_id
        if active_id and not any(p.id == active_id for p in rows):
            active_id = rows[0].id if rows else None
        if not active_id and rows:
            active_id = rows[0].id
        return {
            "active_profile_id": active_id,
            "profiles": [
                {
                    "id": p.id,
                    "status": p.status,
                    "contact_name": p.contact_name,
                    "summary_text": p.summary_text,
                    "updated_at": p.updated_at,
                    "is_active": p.id == active_id,
                }
                for p in rows
            ],
        }

    async def create_profile(self, *, actor: UserActor, locale: str = "zh-CN") -> ProfileResponse:
        profile = Profile(
            id=new_id("prof"),
            user_id=actor.user_id,
            guest_session_id=None,
            owner_kind=OwnerKind.USER,
            status=ProfileStatus.DRAFT,
            version=1,
            locale=locale,
            payload={},
        )
        profile = await self._profiles.create(profile)
        meta = await self._users.get_or_create_meta(actor.user_id)
        meta.active_profile_id = profile.id
        await self._db.commit()
        reloaded = await self._profiles.get_by_id(profile.id, with_sources=True)
        if reloaded is None:
            raise NotFoundError("档案不存在或已删除。", code="profile_not_found")
        return self._to_response(reloaded)

    async def activate_profile(self, profile_id: str, *, actor: UserActor) -> ProfileResponse:
        profile = await self._profiles.get_for_user(actor.user_id, profile_id)
        if profile is None:
            raise NotFoundError("档案不存在或已删除。", code="profile_not_found")
        meta = await self._users.get_or_create_meta(actor.user_id)
        meta.active_profile_id = profile.id
        await self._db.commit()
        reloaded = await self._profiles.get_by_id(profile.id, with_sources=True)
        if reloaded is None:
            raise NotFoundError("档案不存在或已删除。", code="profile_not_found")
        return self._to_response(reloaded)

    async def resolve_active_profile_id(self, user_id: str) -> str | None:
        meta = await self._users.get_or_create_meta(user_id)
        if meta.active_profile_id:
            owned = await self._profiles.get_for_user(user_id, meta.active_profile_id)
            if owned is not None:
                return owned.id
        active = await self._profiles.get_active_for_user(user_id)
        return active.id if active else None

    async def upload(
        self,
        *,
        actor: Actor,
        file_name: str,
        content_type: str | None,
        raw_bytes: bytes,
    ) -> ProfileResponse:
        self._ingest.validate_upload(file_name, content_type, len(raw_bytes))

        profile = await self._get_or_create_active_profile(actor)
        source_id = new_id("psrc")
        ext = Path(file_name).suffix.lower() or ".bin"
        object_key = storage_key("profiles", profile.id, "source", f"{source_id}{ext}")

        # Storage SDKs are synchronous; never block status polling and other
        # requests on an object-store upload.
        await asyncio.to_thread(
            self._storage.put_object, object_key, raw_bytes, content_type=content_type
        )

        source = ProfileSource(
            id=source_id,
            profile_id=profile.id,
            file_name=file_name,
            content_type=content_type,
            file_size=len(raw_bytes),
            storage_key=object_key,
            parse_status=ParseStatus.PROCESSING,
            parse_phase="queued",
            parse_error=None,
        )
        await self._profiles.add_source(source)
        await self._db.commit()
        reloaded = await self._profiles.get_by_id(profile.id, with_sources=True)
        if reloaded is None:
            raise NotFoundError(
                "上传已完成，但没找到对应的档案，请重新上传。",
                code="profile_not_found",
            )
        return self._to_response(reloaded)

    async def ingest_text(
        self,
        *,
        actor: Actor,
        raw_text: str,
        title: str | None = None,
    ) -> ProfileResponse:
        """Build a profile from text the user pasted or typed.

        The third way in, next to uploading a file and answering the interview. It
        exists because the other two both failed a real case: a user whose resume is in
        a WeChat message, or who would rather write a paragraph about what they did
        than hunt for a file. Until now they had to save a `.txt` first, which is an
        absurd thing to ask.

        Implemented by writing the text as a `.txt` source and handing it to the normal
        parse pipeline, rather than calling `ProfileStructurer` directly. That choice is
        deliberate: the upload path already owns parse status, phase reporting, the
        progress UI, failure copy, locale detection and the draft state the user then
        confirms. A second route into the structurer would have to reproduce all of it
        and would drift from it.
        """
        text = raw_text.strip()
        self._ingest.validate_text(text)

        profile = await self._get_or_create_active_profile(actor)
        source_id = new_id("psrc")
        object_key = storage_key("profiles", profile.id, "source", f"{source_id}.txt")
        raw_bytes = text.encode("utf-8")

        await asyncio.to_thread(
            self._storage.put_object, object_key, raw_bytes, content_type="text/plain"
        )

        source = ProfileSource(
            id=source_id,
            profile_id=profile.id,
            # Named so the user recognises it in the source list. A pasted block has no
            # filename, and 「粘贴的内容」 is what they will look for.
            file_name=f"{(title or '粘贴的内容').strip()[:80]}.txt",
            content_type="text/plain",
            file_size=len(raw_bytes),
            storage_key=object_key,
            parse_status=ParseStatus.PROCESSING,
            parse_phase="queued",
            parse_error=None,
        )
        await self._profiles.add_source(source)
        await self._db.commit()
        reloaded = await self._profiles.get_by_id(profile.id, with_sources=True)
        if reloaded is None:
            raise NotFoundError(
                "内容已保存，但没找到对应的档案，请重试。",
                code="profile_not_found",
            )
        return self._to_response(reloaded)

    async def _commit_parse_phase(
        self,
        source: ProfileSource,
        phase: str,
        profile_id: str,
        *,
        elapsed_sec: float | None = None,
        claim_token: str | None = None,
    ) -> None:
        source.parse_phase = phase
        if claim_token:
            lease_until = datetime.now(UTC) + timedelta(
                seconds=settings.jc_profile_parse_lease_seconds
            )
            result = await self._db.execute(
                update(ProfileSource)
                .where(
                    ProfileSource.id == source.id,
                    ProfileSource.parse_claim_token == claim_token,
                )
                .values(parse_phase=phase, parse_lease_until=lease_until)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                await self._db.rollback()
                raise ParseClaimLost(source.id)
        await self._db.commit()
        extra = f" elapsed_sec={elapsed_sec:.1f}" if elapsed_sec is not None else ""
        logger.info(
            "profile_parse profile_id=%s source_id=%s file=%s phase=%s%s",
            profile_id,
            source.id,
            source.file_name,
            phase,
            extra,
        )

    async def parse_stored_source(
        self, profile_id: str, source_id: str, *, claim_token: str | None = None
    ) -> bool:
        """Run LLM ingest for an uploaded source (background; may take minutes)."""
        import time

        parse_started = time.monotonic()
        profile = await self._profiles.get_by_id(profile_id, with_sources=True)
        if profile is None:
            logger.warning("parse_stored_source: profile missing %s", profile_id)
            return False
        source = next((s for s in profile.sources if s.id == source_id), None)
        if source is None:
            logger.warning("parse_stored_source: source missing %s", source_id)
            return False
        if source.parse_status == ParseStatus.DONE:
            logger.info("parse_stored_source: already done %s", source_id)
            return True

        await self._commit_parse_phase(
            source, "load_file", profile_id, elapsed_sec=time.monotonic() - parse_started,
            claim_token=claim_token,
        )

        try:
            raw_bytes = await asyncio.wait_for(
                asyncio.to_thread(self._storage.get_object_bytes, source.storage_key),
                timeout=min(30, settings.jc_ingest_timeout_seconds),
            )
        except Exception:
            logger.exception(
                "parse_stored_source: could not read object profile=%s source=%s",
                profile_id,
                source_id,
            )
            await self._finish_parse_failure(
                source, USER_UPLOAD_PARSE_FAILED, claim_token=claim_token
            )
            return False

        async def on_ingest_phase(phase: str) -> None:
            await self._commit_parse_phase(
                source,
                phase,
                profile_id,
                elapsed_sec=time.monotonic() - parse_started,
                claim_token=claim_token,
            )

        try:
            result = await asyncio.wait_for(
                self._ingest.parse(
                    file_name=source.file_name,
                    content_type=source.content_type,
                    raw_bytes=raw_bytes,
                    on_phase=on_ingest_phase,
                ),
                timeout=settings.jc_ingest_timeout_seconds + 30,
            )
            payload = result.payload
            payload.meta.ingest_mode = result.mode
            payload.meta.extraction_source = result.extraction_source
            payload.meta.source_locale = detect_profile_source_locale(payload)
            profile.locale = payload.meta.source_locale
            if claim_token:
                claimed = await self._db.execute(
                    update(ProfileSource)
                    .where(
                        ProfileSource.id == source.id,
                        ProfileSource.parse_claim_token == claim_token,
                    )
                    .values(
                        parse_status=ParseStatus.DONE,
                        parse_phase=None,
                        parse_error=result.warning,
                        parse_owner=None,
                        parse_claim_token=None,
                        parse_lease_until=None,
                    )
                    .execution_options(synchronize_session=False)
                )
                if claimed.rowcount != 1:
                    await self._db.rollback()
                    raise ParseClaimLost(source.id)
            else:
                source.parse_status = ParseStatus.DONE
                source.parse_phase = None
                source.parse_error = result.warning
            with bind_snapshot_source("intake"):
                self._apply_payload(profile, payload)
                # Every source-of-truth payload write gets a unique profile version.
                profile.version += 1
                await self._db.commit()
            return True
        except IngestValidationError as exc:
            logger.warning("Profile upload parse stopped profile_id=%s reason=%s", profile_id, exc)
            failure_message = str(exc)
        except TimeoutError:
            logger.error(
                "Profile upload parse timed out profile_id=%s file=%s",
                profile_id,
                source.file_name,
            )
            failure_message = USER_UPLOAD_PARSE_FAILED
        except Exception:
            logger.exception(
                "Profile upload parse failed profile_id=%s file=%s",
                profile_id,
                source.file_name,
            )
            failure_message = USER_UPLOAD_PARSE_FAILED

        # A failing final write can leave AsyncSession in a failed transaction. Roll
        # it back before persisting the terminal parse state in a fresh transaction.
        await self._db.rollback()
        await self._finish_parse_failure(source, failure_message, claim_token=claim_token)
        return False

    async def _finish_parse_failure(
        self,
        source: ProfileSource,
        message: str,
        *,
        claim_token: str | None,
    ) -> bool:
        if claim_token:
            result = await self._db.execute(
                update(ProfileSource)
                .where(
                    ProfileSource.id == source.id,
                    ProfileSource.parse_claim_token == claim_token,
                )
                .values(
                    parse_status=ParseStatus.FAILED,
                    parse_phase="failed",
                    parse_error=message,
                    parse_owner=None,
                    parse_claim_token=None,
                    parse_lease_until=None,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                await self._db.rollback()
                logger.warning("profile_parse source_id=%s phase=stale_failure_ignored", source.id)
                return False
        else:
            source.parse_status = ParseStatus.FAILED
            source.parse_phase = "failed"
            source.parse_error = message
        await self._db.commit()
        return True

    async def get(self, profile_id: str, *, actor: Actor) -> ProfileResponse:
        profile = await self._require_profile(profile_id, with_sources=True)
        self._assert_owner(profile, actor)
        return self._to_response(profile)

    async def update(
        self,
        profile_id: str,
        *,
        actor: Actor,
        body: ProfileUpdateRequest,
    ) -> ProfileResponse:
        profile = await self._require_profile(profile_id, with_sources=True)
        self._assert_owner(profile, actor)

        if body.expected_version is not None and profile.version != body.expected_version:
            raise ConflictError(
                "这份档案在别处被修改过了，请刷新后重新编辑。",
                code="version_conflict",
            )

        with bind_snapshot_source("manual_edit"):
            self._apply_payload(profile, body.payload)
            profile.version += 1
            await self._db.commit()

        reloaded = await self._profiles.get_by_id(profile.id, with_sources=True)
        if reloaded is None:
            raise NotFoundError("档案不存在或已删除。", code="profile_not_found")
        return self._to_response(reloaded)

    async def set_photo(
        self,
        profile_id: str,
        *,
        actor: Actor,
        raw: bytes,
        enabled: bool,
    ) -> ProfileResponse:
        """Store a cropped headshot and bind it to the profile.

        Bumps `version` like any other payload edit so a concurrent editor holding an
        `expected_version` finds out rather than overwriting the photo away, and runs
        under `bind_snapshot_source` so the resume version history records the change
        (a headshot appearing or disappearing is visible on the exported page, which
        is exactly what that history is for).
        """
        profile = await self._require_profile(profile_id, with_sources=True)
        self._assert_owner(profile, actor)

        from jc.services.profile_photo_service import store_profile_photo

        # Ahead of the transaction: a rejected image must not leave a version bump.
        photo = await store_profile_photo(raw, profile_id=profile.id, enabled=enabled)

        payload = ProfilePayload.model_validate(profile.payload or {})
        payload.contact.photo = photo
        with bind_snapshot_source("photo_set"):
            self._apply_payload(profile, payload)
            profile.version += 1
            await self._db.commit()

        reloaded = await self._profiles.get_by_id(profile.id, with_sources=True)
        if reloaded is None:
            raise NotFoundError("档案不存在或已删除。", code="profile_not_found")
        return self._to_response(reloaded)

    async def set_photo_enabled(
        self,
        profile_id: str,
        *,
        actor: Actor,
        enabled: bool,
        show_in_bilingual: bool | None = None,
    ) -> ProfileResponse:
        """Flip whether the stored headshot is rendered, keeping the upload intact.

        Turning the photo off deliberately does **not** clear `storage_key`: the switch
        is a display choice the user may reverse immediately, and re-uploading a photo
        they already cropped would be a pointless tax on changing their mind. Removal
        is `delete_photo`, which is a different intent.

        `show_in_bilingual` is `None` for "leave it as it is" rather than a plain
        `bool`, so the Chinese-resume switch can be toggled without the request having
        to restate the bilingual choice — a caller that only knows about one of the two
        cannot accidentally reset the other.
        """
        profile = await self._require_profile(profile_id, with_sources=True)
        self._assert_owner(profile, actor)

        payload = ProfilePayload.model_validate(profile.payload or {})
        if enabled and not payload.contact.photo.storage_key:
            raise NotFoundError(
                "还没有上传照片，请先上传再开启显示。", code="photo_not_uploaded"
            )
        next_bilingual = (
            payload.contact.photo.show_in_bilingual
            if show_in_bilingual is None
            else show_in_bilingual
        )
        if (
            payload.contact.photo.enabled == enabled
            and payload.contact.photo.show_in_bilingual == next_bilingual
        ):
            # Idempotent: no version bump for a no-op, so a double-clicked toggle does
            # not manufacture snapshot history or invalidate someone else's edit.
            return self._to_response(profile)

        payload.contact.photo = payload.contact.photo.model_copy(
            update={"enabled": enabled, "show_in_bilingual": next_bilingual}
        )
        with bind_snapshot_source("photo_toggle"):
            self._apply_payload(profile, payload)
            profile.version += 1
            await self._db.commit()

        reloaded = await self._profiles.get_by_id(profile.id, with_sources=True)
        if reloaded is None:
            raise NotFoundError("档案不存在或已删除。", code="profile_not_found")
        return self._to_response(reloaded)

    async def delete_photo(self, profile_id: str, *, actor: Actor) -> ProfileResponse:
        """Drop the headshot from the payload entirely.

        The stored object is intentionally left in place rather than deleted. Resume
        version history can restore an earlier payload that still references this key,
        and a restore that produced a broken image would be worse than an orphaned
        object -- object lifecycle is a storage-side retention concern, not something
        a user-facing delete should decide.
        """
        profile = await self._require_profile(profile_id, with_sources=True)
        self._assert_owner(profile, actor)

        payload = ProfilePayload.model_validate(profile.payload or {})
        if not payload.contact.photo.storage_key:
            return self._to_response(profile)

        from jc.schemas.profile_payload import ProfilePhoto

        payload.contact.photo = ProfilePhoto()
        with bind_snapshot_source("photo_delete"):
            self._apply_payload(profile, payload)
            profile.version += 1
            await self._db.commit()

        reloaded = await self._profiles.get_by_id(profile.id, with_sources=True)
        if reloaded is None:
            raise NotFoundError("档案不存在或已删除。", code="profile_not_found")
        return self._to_response(reloaded)

    async def confirm(self, profile_id: str, *, actor: Actor) -> ProfileConfirmResponse:
        profile = await self._require_profile(profile_id, with_sources=True)
        self._assert_owner(profile, actor)
        if profile.sources and profile.sources[0].parse_status in {
            ParseStatus.PENDING, ParseStatus.PROCESSING,
        }:
            raise ConflictError(
                "简历仍在解析，请等待解析完成后再确认。", code="profile_parse_in_progress"
            )
        payload = ProfilePayload.model_validate(profile.payload)
        if not has_profile_facts(payload):
            raise ConflictError(
                "档案尚无可确认的内容，请先完成解析或填写信息。", code="profile_empty"
            )

        now = datetime.now(UTC)
        profile.status = ProfileStatus.CONFIRMED
        profile.confirmed_at = now
        profile.version += 1
        payload.meta.confirmed_at = now
        with bind_snapshot_source("confirm"):
            profile.payload = payload.model_dump(mode="json")
            await self._db.commit()
        return ProfileConfirmResponse(
            id=profile.id,
            status=profile.status,
            version=profile.version,
            confirmed_at=now,
        )

    async def reopen(self, profile_id: str, *, actor: Actor) -> ProfileResponse:
        profile = await self._require_profile(profile_id, with_sources=True)
        self._assert_owner(profile, actor)

        profile.status = ProfileStatus.DRAFT
        profile.confirmed_at = None
        profile.version += 1
        payload = ProfilePayload.model_validate(profile.payload)
        payload.meta.confirmed_at = None
        with bind_snapshot_source("reopen"):
            profile.payload = payload.model_dump(mode="json")
            await self._db.commit()
        reloaded = await self._profiles.get_by_id(profile.id, with_sources=True)
        if reloaded is None:
            raise NotFoundError("档案不存在或已删除。", code="profile_not_found")
        return self._to_response(reloaded)

    async def _get_or_create_active_profile(self, actor: Actor) -> Profile:
        if isinstance(actor, UserActor):
            existing_id = await self.resolve_active_profile_id(actor.user_id)
            if existing_id:
                existing = await self._profiles.get_by_id(existing_id)
                if existing is not None:
                    return existing
            profile = Profile(
                id=new_id("prof"),
                user_id=actor.user_id,
                guest_session_id=None,
                owner_kind=OwnerKind.USER,
                status=ProfileStatus.DRAFT,
                version=1,
                locale="zh-CN",
                payload={},
            )
            return await self._profiles.create(profile)

        if actor.guest_session_id == "gst_anonymous":
            raise ForbiddenError("需要先创建访客会话。", code="guest_session_required")

        existing = await self._profiles.get_active_for_guest(actor.guest_session_id)
        if existing is not None:
            return existing
        profile = Profile(
            id=new_id("prof"),
            user_id=None,
            guest_session_id=actor.guest_session_id,
            owner_kind=OwnerKind.GUEST,
            status=ProfileStatus.DRAFT,
            version=1,
            locale="zh-CN",
            payload={},
        )
        return await self._profiles.create(profile)

    async def _require_profile(self, profile_id: str, *, with_sources: bool = False) -> Profile:
        profile = await self._profiles.get_by_id(profile_id, with_sources=with_sources)
        if profile is None:
            raise NotFoundError("档案不存在或已删除。", code="profile_not_found")
        return profile

    @staticmethod
    def _assert_owner(profile: Profile, actor: Actor) -> None:
        if isinstance(actor, UserActor):
            if profile.user_id != actor.user_id:
                raise ForbiddenError("这份档案不属于当前账号。", code="forbidden")
            return
        if profile.guest_session_id != actor.guest_session_id:
            raise ForbiddenError("这份档案不属于当前账号。", code="forbidden")

    @staticmethod
    def _apply_payload(profile: Profile, payload: ProfilePayload) -> None:
        source = payload.meta.source_locale or profile.locale or "zh-CN"
        payload.meta.source_locale = source
        target = other_monolingual(source)
        status = dict(payload.meta.i18n_status)
        if status.get(target) == "ready":
            status[target] = "stale"
            payload.meta.i18n_status = status
        profile.payload = payload.model_dump(mode="json")
        profile.locale = source
        profile.contact_name = payload.contact.name
        profile.summary_text = (payload.summary or "")[:512] or None

    @staticmethod
    def _to_response(profile: Profile) -> ProfileResponse:
        from jc.schemas.profile import ProfileSourceResponse

        payload = ProfilePayload.model_validate(profile.payload or {})
        # The persisted `download_url` is expected to be expired; the key is the durable
        # record. Re-signed here rather than at each call site because this is the one
        # function every profile read returns through.
        from jc.services.profile_photo_service import resign_photo

        resigned = resign_photo(payload.contact.photo)
        if resigned is not None:
            payload.contact.photo = resigned
        sources = sorted(profile.sources, key=lambda s: s.created_at, reverse=True)
        return ProfileResponse(
            id=profile.id,
            status=profile.status,
            version=profile.version,
            locale=profile.locale,
            payload=payload,
            sources=[
                ProfileSourceResponse(
                    id=s.id,
                    file_name=s.file_name,
                    content_type=s.content_type,
                    file_size=s.file_size,
                    storage_key=s.storage_key,
                    parse_status=s.parse_status,
                    parse_phase=s.parse_phase,
                    parse_error=public_parse_error(
                        s.parse_error,
                        ingest_mode=payload.meta.ingest_mode,
                    ),
                    created_at=s.created_at,
                    updated_at=s.updated_at,
                )
                for s in sources
            ],
            contact_name=profile.contact_name,
            confirmed_at=profile.confirmed_at,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
