"""Authentication and session orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from agentkit.common.crypto import hash_password, verify_password
from agentkit.common.ids import new_id
from agentkit.redis.session import RedisSessionStore
from agentkit.web.auth import Actor, GuestActor, UserActor
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.capabilities import GUEST_CAPABILITIES, USER_CAPABILITIES
from jobcome.config import settings
from jobcome.exceptions import AppError, AuthError, ConflictError
from jobcome.models.user import User
from jobcome.redis_client import get_redis, get_session_store
from jobcome.schemas.auth import (
    AuthContextResponse,
    AuthSuccessResponse,
    MergeConflictResponse,
    RegisterRequest,
    ResolveMergeRequest,
    UserContext,
)
from jobcome.services.email_service import EmailService
from jobcome.services.guest_migration_service import ClaimResult, GuestMigrationService
from jobcome.services.profile_service import ProfileService
from jobcome.stores.email_verification_store import EmailVerificationStore
from jobcome.stores.guest_session_store import GuestSessionStore
from jobcome.stores.password_reset_store import PasswordResetStore
from jobcome.stores.profile_store import ProfileStore
from jobcome.stores.user_store import UserStore
from jobcome.utils.security_tokens import generate_token


@dataclass(frozen=True, slots=True)
class SessionIssue:
    session_id: str
    user: User


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._users = UserStore(db)
        self._guests = GuestSessionStore(
            db,
            redis=get_redis(),
            guest_ttl_days=settings.job_come_guest_ttl_days,
        )
        self._profiles = ProfileStore(db)
        self._profile_service = ProfileService(db)
        self._migration = GuestMigrationService(db)
        self._password_resets = PasswordResetStore(db)
        self._email_verifications = EmailVerificationStore(get_redis())
        self._email = EmailService()
        self._sessions: RedisSessionStore = get_session_store()

    async def ensure_guest_session(self, guest_session_id: str | None) -> tuple[str, bool]:
        """Return (guest_session_id, created)."""
        if guest_session_id:
            guest = await self._guests.get(guest_session_id)
            if guest is not None:
                await self._guests.touch(guest)
                return guest.id, False
        guest = await self._guests.create()
        return guest.id, True

    async def build_context(
        self,
        *,
        actor: Actor,
        merge_conflict: MergeConflictResponse | None = None,
    ) -> AuthContextResponse:
        if isinstance(actor, UserActor):
            user = await self._users.get_by_id(actor.user_id)
            if user is None:
                raise AuthError("Session user not found", code="session_invalid")
            profile_id = await self._profile_service.resolve_active_profile_id(actor.user_id)
            profile = await self._profiles.get_by_id(profile_id) if profile_id else None
            return AuthContextResponse(
                actor="user",
                user=self._to_user_context(user),
                capabilities=list(USER_CAPABILITIES),
                active_profile_id=profile.id if profile else None,
                merge_conflict=merge_conflict.model_dump() if merge_conflict else None,
            )

        profile = await self._profiles.get_active_for_guest(actor.guest_session_id)
        return AuthContextResponse(
            actor="guest",
            user=None,
            capabilities=list(GUEST_CAPABILITIES),
            active_profile_id=profile.id if profile else None,
            merge_conflict=None,
        )

    async def open_guest_session(self) -> str:
        guest_id, created = await self.ensure_guest_session(None)
        if created:
            await self._db.commit()
        return guest_id

    async def resolve_actor(
        self,
        *,
        session_id: str | None,
        guest_session_id: str | None,
    ) -> Actor:
        if session_id:
            session = await self._sessions.get(session_id)
            if session is None:
                raise AuthError("Invalid session", code="session_invalid")
            await self._sessions.touch(session_id)
            return UserActor(user_id=session.user_id, session_id=session_id)
        if guest_session_id:
            guest = await self._guests.get(guest_session_id)
            if guest is not None:
                await self._guests.touch(guest)
                return GuestActor(guest_session_id=guest.id)
        raise AuthError("Guest session required", code="guest_required")

    async def register(
        self,
        body: RegisterRequest,
        *,
        guest_session_id: str | None,
    ) -> tuple[SessionIssue, ClaimResult]:
        existing = await self._users.get_by_email(body.email)
        if existing is not None:
            raise ConflictError("Email already registered", code="email_taken")

        user = await self._users.create(
            email=body.email,
            password_hash=hash_password(body.password),
            display_name=body.display_name,
        )
        session_issue = await self._issue_session(user)
        claim = await self._migration.claim(guest_session_id, user.id)
        await self._db.commit()
        await self._send_verification_email_safe(user)
        return session_issue, claim

    async def login(
        self,
        email: str,
        password: str,
        *,
        guest_session_id: str | None,
    ) -> tuple[SessionIssue, ClaimResult]:
        user = await self._users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthError("Invalid email or password", code="invalid_credentials")

        session_issue = await self._issue_session(user)
        claim = await self._migration.claim(guest_session_id, user.id)
        await self._db.commit()
        return session_issue, claim

    async def logout(self, session_id: str) -> None:
        await self._sessions.delete(session_id)

    async def request_password_reset(self, email: str) -> None:
        """Always succeeds from caller's perspective (no email enumeration)."""
        user = await self._users.get_by_email(email)
        if user is None or not self._email.smtp_configured():
            return

        plain_token = generate_token()
        await self._password_resets.invalidate_active_for_user(user.id)
        await self._password_resets.create(
            user_id=user.id,
            plain_token=plain_token,
            ttl_hours=settings.job_come_password_reset_ttl_hours,
        )
        await self._db.commit()

        reset_url = (
            f"{settings.job_come_public_url.rstrip('/')}/auth/reset-password"
            f"?token={plain_token}"
        )
        await self._email.send_password_reset(to_email=user.email, reset_url=reset_url)

    async def reset_password(self, token: str, new_password: str) -> None:
        row = await self._password_resets.get_valid(token)
        if row is None:
            raise AppError("Invalid or expired reset token", code="invalid_token")

        user = await self._users.get_by_id(row.user_id)
        if user is None:
            raise AppError("Invalid or expired reset token", code="invalid_token")

        await self._users.update_password(user, hash_password(new_password))
        await self._password_resets.mark_used(row)
        await self._db.commit()

    async def send_email_verification(self, user_id: str) -> None:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise AuthError("User not found", code="session_invalid")
        if user.email_verified_at is not None:
            return
        if not self._email.smtp_configured():
            raise AppError("Email is not configured", code="email_not_configured")

        plain_token = generate_token()
        ttl_seconds = settings.job_come_email_verify_ttl_hours * 3600
        await self._email_verifications.save(
            user_id=user.id,
            plain_token=plain_token,
            ttl_seconds=ttl_seconds,
        )
        verify_url = (
            f"{settings.job_come_public_url.rstrip('/')}/auth/verify-email"
            f"?token={plain_token}"
        )
        await self._email.send_email_verification(to_email=user.email, verify_url=verify_url)

    async def verify_email(self, token: str) -> None:
        user_id = await self._email_verifications.consume(token)
        if user_id is None:
            raise AppError("Invalid or expired verification token", code="invalid_token")

        user = await self._users.get_by_id(user_id)
        if user is None:
            raise AppError("Invalid or expired verification token", code="invalid_token")

        await self._users.mark_email_verified(user)
        await self._db.commit()

    async def change_password(self, user_id: str, current_password: str, new_password: str) -> None:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise AuthError("User not found", code="session_invalid")
        if not verify_password(current_password, user.password_hash):
            raise AppError("Current password is incorrect", code="invalid_password")
        await self._users.update_password(user, hash_password(new_password))
        await self._db.commit()

    async def _send_verification_email_safe(self, user: User) -> None:
        if not self._email.smtp_configured() or user.email_verified_at is not None:
            return
        try:
            await self.send_email_verification(user.id)
        except Exception:
            pass

    async def resolve_merge(
        self,
        user_id: str,
        body: ResolveMergeRequest,
        *,
        guest_session_id: str | None,
    ) -> ClaimResult:
        if not guest_session_id:
            profile_id = await self._profile_service.resolve_active_profile_id(user_id)
            profile = await self._profiles.get_by_id(profile_id) if profile_id else None
            return ClaimResult(
                active_profile_id=profile.id if profile else None,
                merge_conflict=None,
            )
        claim = await self._migration.resolve(user_id, guest_session_id, body.choice)
        await self._db.commit()
        return claim

    async def _issue_session(self, user: User) -> SessionIssue:
        session_id = new_id("sess")
        await self._sessions.create(session_id, user.id)
        return SessionIssue(session_id=session_id, user=user)

    @staticmethod
    def to_success_response(
        session_issue: SessionIssue,
        claim: ClaimResult,
    ) -> AuthSuccessResponse:
        return AuthSuccessResponse(
            user=AuthService._to_user_context(session_issue.user),
            active_profile_id=claim.active_profile_id,
            merge_conflict=claim.merge_conflict,
        )

    @staticmethod
    def _to_user_context(user: User) -> UserContext:
        display_name = user.meta.display_name if user.meta else None
        return UserContext(
            id=user.id,
            email=user.email,
            email_verified=user.email_verified_at is not None,
            display_name=display_name,
        )
