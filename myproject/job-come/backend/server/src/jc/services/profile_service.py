"""Profile CRUD, upload, and confirm."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

from agentkit.common.ids import new_id
from agentkit.web.auth import Actor, UserActor
from sqlalchemy.ext.asyncio import AsyncSession

from jc.exceptions import ConflictError, ForbiddenError, NotFoundError
from jc.models.enums import OwnerKind, ParseStatus, ProfileStatus
from jc.models.profile import Profile, ProfileSource
from jc.resume_locale import other_monolingual
from jc.schemas.profile import ProfileConfirmResponse, ProfileResponse, ProfileUpdateRequest
from jc.schemas.profile_payload import ProfilePayload
from jc.services.ingest_user_messages import USER_UPLOAD_PARSE_FAILED, public_parse_error
from jc.services.profile_i18n import detect_profile_source_locale
from jc.services.profile_ingest_service import ProfileIngestService
from jc.storage_backend import get_storage_backend
from jc.storage_keys import storage_key
from jc.stores.profile_store import ProfileStore
from jc.stores.user_store import UserStore

logger = logging.getLogger(__name__)

_PARSE_STORED_TIMEOUT_SEC = 480


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
            raise NotFoundError("Profile not found")
        return self._to_response(reloaded)

    async def activate_profile(self, profile_id: str, *, actor: UserActor) -> ProfileResponse:
        profile = await self._profiles.get_for_user(actor.user_id, profile_id)
        if profile is None:
            raise NotFoundError("Profile not found")
        meta = await self._users.get_or_create_meta(actor.user_id)
        meta.active_profile_id = profile.id
        await self._db.commit()
        reloaded = await self._profiles.get_by_id(profile.id, with_sources=True)
        if reloaded is None:
            raise NotFoundError("Profile not found")
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

        self._storage.put_object(object_key, raw_bytes, content_type=content_type)

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
            raise NotFoundError("Profile not found after upload")
        return self._to_response(reloaded)

    async def _commit_parse_phase(self, source: ProfileSource, phase: str, profile_id: str) -> None:
        source.parse_phase = phase
        await self._db.commit()
        logger.info(
            "profile_parse profile_id=%s source_id=%s file=%s phase=%s",
            profile_id,
            source.id,
            source.file_name,
            phase,
        )

    async def parse_stored_source(self, profile_id: str, source_id: str) -> bool:
        """Run LLM ingest for an uploaded source (background; may take minutes)."""
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

        await self._commit_parse_phase(source, "load_file", profile_id)

        try:
            raw_bytes = self._storage.get_object_bytes(source.storage_key)
        except Exception:
            logger.exception(
                "parse_stored_source: could not read object profile=%s source=%s",
                profile_id,
                source_id,
            )
            source.parse_status = ParseStatus.FAILED
            source.parse_phase = "failed"
            source.parse_error = USER_UPLOAD_PARSE_FAILED
            await self._db.commit()
            return False

        async def on_ingest_phase(phase: str) -> None:
            await self._commit_parse_phase(source, phase, profile_id)

        try:
            result = await asyncio.wait_for(
                self._ingest.parse(
                    file_name=source.file_name,
                    content_type=source.content_type,
                    raw_bytes=raw_bytes,
                    on_phase=on_ingest_phase,
                ),
                timeout=_PARSE_STORED_TIMEOUT_SEC,
            )
            payload = result.payload
            payload.meta.ingest_mode = result.mode
            payload.meta.extraction_source = result.extraction_source
            payload.meta.source_locale = detect_profile_source_locale(payload)
            profile.locale = payload.meta.source_locale
            self._apply_payload(profile, payload)
            source.parse_status = ParseStatus.DONE
            source.parse_phase = None
            source.parse_error = result.warning
            await self._db.commit()
            return True
        except TimeoutError:
            logger.error(
                "Profile upload parse timed out profile_id=%s file=%s",
                profile_id,
                source.file_name,
            )
            if source.parse_status != ParseStatus.DONE:
                source.parse_status = ParseStatus.FAILED
                source.parse_phase = "failed"
                source.parse_error = USER_UPLOAD_PARSE_FAILED
        except Exception:
            logger.exception(
                "Profile upload parse failed profile_id=%s file=%s",
                profile_id,
                source.file_name,
            )
            if source.parse_status != ParseStatus.DONE:
                source.parse_status = ParseStatus.FAILED
                source.parse_phase = "failed"
                source.parse_error = USER_UPLOAD_PARSE_FAILED

        await self._db.commit()
        return source.parse_status == ParseStatus.DONE

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
                "Profile was modified by another session",
                code="version_conflict",
            )

        self._apply_payload(profile, body.payload)
        profile.version += 1
        await self._db.commit()

        reloaded = await self._profiles.get_by_id(profile.id, with_sources=True)
        if reloaded is None:
            raise NotFoundError("Profile not found")
        return self._to_response(reloaded)

    async def confirm(self, profile_id: str, *, actor: Actor) -> ProfileConfirmResponse:
        profile = await self._require_profile(profile_id)
        self._assert_owner(profile, actor)

        now = datetime.now(UTC)
        profile.status = ProfileStatus.CONFIRMED
        profile.confirmed_at = now
        profile.version += 1
        payload = ProfilePayload.model_validate(profile.payload)
        payload.meta.confirmed_at = now
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
        profile.payload = payload.model_dump(mode="json")

        await self._db.commit()
        reloaded = await self._profiles.get_by_id(profile.id, with_sources=True)
        if reloaded is None:
            raise NotFoundError("Profile not found")
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
            raise ForbiddenError("Guest session required", code="guest_session_required")

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
            raise NotFoundError("Profile not found", code="profile_not_found")
        return profile

    @staticmethod
    def _assert_owner(profile: Profile, actor: Actor) -> None:
        if isinstance(actor, UserActor):
            if profile.user_id != actor.user_id:
                raise ForbiddenError("Not your profile", code="forbidden")
            return
        if profile.guest_session_id != actor.guest_session_id:
            raise ForbiddenError("Not your profile", code="forbidden")

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
