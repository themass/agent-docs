"""Profile CRUD, upload, and confirm."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from agentkit.common.ids import new_id
from agentkit.web.auth import Actor, GuestActor, UserActor
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.resume_locale import other_monolingual
from jobcome.models.enums import OwnerKind, ParseStatus, ProfileStatus
from jobcome.models.profile import Profile, ProfileSource
from jobcome.schemas.profile import ProfileConfirmResponse, ProfileResponse, ProfileUpdateRequest
from jobcome.schemas.profile_payload import ProfilePayload
from jobcome.services.profile_i18n import detect_profile_source_locale
from jobcome.services.profile_ingest_service import IngestValidationError, ProfileIngestService
from jobcome.storage_backend import get_storage_backend
from jobcome.stores.profile_store import ProfileStore
from jobcome.stores.user_store import UserStore


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
        storage_key = f"profiles/{profile.id}/source/{source_id}{ext}"

        self._storage.put_object(storage_key, raw_bytes, content_type=content_type)

        source = ProfileSource(
            id=source_id,
            profile_id=profile.id,
            file_name=file_name,
            content_type=content_type,
            file_size=len(raw_bytes),
            storage_key=storage_key,
            parse_status=ParseStatus.PROCESSING,
            parse_error=None,
        )
        await self._profiles.add_source(source)

        try:
            result = await self._ingest.parse(
                file_name=file_name,
                content_type=content_type,
                raw_bytes=raw_bytes,
            )
            payload = result.payload
            payload.meta.ingest_mode = result.mode
            payload.meta.source_locale = detect_profile_source_locale(payload)
            profile.locale = payload.meta.source_locale
            self._apply_payload(profile, payload)
            source.parse_status = ParseStatus.DONE
            source.parse_error = result.warning
        except Exception as exc:  # noqa: BLE001 — persist failure on source row
            source.parse_status = ParseStatus.FAILED
            source.parse_error = str(exc)[:512]

        await self._db.commit()
        reloaded = await self._profiles.get_by_id(profile.id, with_sources=True)
        if reloaded is None:
            raise NotFoundError("Profile not found after upload")
        return self._to_response(reloaded)

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
        from jobcome.schemas.profile import ProfileSourceResponse

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
                    parse_error=s.parse_error,
                    created_at=s.created_at,
                )
                for s in sources
            ],
            contact_name=profile.contact_name,
            confirmed_at=profile.confirmed_at,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
