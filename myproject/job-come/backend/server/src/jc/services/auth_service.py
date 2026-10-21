"""Authentication and session orchestration."""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from agentkit.common.crypto import hash_password, verify_password
from agentkit.common.ids import new_id
from agentkit.redis.session import RedisSessionStore
from agentkit.web.auth import Actor, GuestActor, UserActor
from sqlalchemy.ext.asyncio import AsyncSession

from jc.capabilities import GUEST_CAPABILITIES, USER_CAPABILITIES
from jc.config import settings
from jc.exceptions import AppError, AuthError, ConflictError
from jc.models.enums import UserRole
from jc.models.user import User
from jc.redis_client import get_redis, get_session_store
from jc.schemas.auth import (
    AccountResponse,
    AuthContextResponse,
    AuthSuccessResponse,
    MergeConflictResponse,
    RegisterRequest,
    ResolveMergeRequest,
    UpdateAccountRequest,
    UserContext,
)
from jc.services.email_service import EmailService
from jc.services.guest_migration_service import ClaimResult, GuestMigrationService
from jc.services.profile_service import ProfileService
from jc.stores.email_verification_store import EmailVerificationStore
from jc.stores.guest_session_store import GuestSessionStore
from jc.stores.password_reset_store import PasswordResetStore
from jc.stores.profile_store import ProfileStore
from jc.stores.user_store import UserStore
from jc.utils.security_tokens import generate_token


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
            guest_ttl_days=settings.jc_guest_ttl_days,
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
                raise AuthError("登录状态已失效，请重新登录。", code="session_invalid")
            profile_id = await self._profile_service.resolve_active_profile_id(actor.user_id)
            profile = await self._profiles.get_by_id(profile_id) if profile_id else None
            capabilities = USER_CAPABILITIES
            if user.role == UserRole.ADMIN:
                capabilities = capabilities + ("admin",)
            return AuthContextResponse(
                actor="user",
                user=self._to_user_context(user),
                capabilities=list(capabilities),
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
                raise AuthError("登录状态已失效，请重新登录。", code="session_invalid")
            await self._sessions.touch(session_id)
            return UserActor(user_id=session.user_id, session_id=session_id)
        if guest_session_id:
            guest = await self._guests.get(guest_session_id)
            if guest is not None:
                await self._guests.touch(guest)
                return GuestActor(guest_session_id=guest.id)
        raise AuthError("需要先创建访客会话。", code="guest_required")

    async def register(
        self,
        body: RegisterRequest,
        *,
        guest_session_id: str | None,
    ) -> tuple[SessionIssue, ClaimResult]:
        existing = await self._users.get_by_email(body.email)
        if existing is not None:
            raise ConflictError(
                "这个邮箱已经注册过了，直接登录或用「忘记密码」找回。",
                code="email_taken",
            )

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
            raise AuthError("邮箱或密码不正确，请重新输入。", code="invalid_credentials")

        session_issue = await self._issue_session(user)
        claim = await self._migration.claim(guest_session_id, user.id)
        await self._db.commit()
        return session_issue, claim

    async def logout(self, session_id: str) -> None:
        await self._sessions.delete(session_id)

    async def request_password_reset(self, email: str) -> None:
        """Succeeds whether or not the address exists, to avoid email enumeration.

        A missing account is deliberately indistinguishable from a sent mail. A missing
        *SMTP config* is not: nobody is waiting on an inbox we never wrote to, and
        telling them to go check it strands them. That one is reported.
        """
        if not self._email.smtp_configured():
            raise AppError(
                "邮件服务还没配置好，暂时发不出重置邮件，请联系我们。",
                code="email_not_configured",
            )

        user = await self._users.get_by_email(email)
        if user is None:
            return

        plain_token = generate_token()
        await self._password_resets.invalidate_active_for_user(user.id)
        await self._password_resets.create(
            user_id=user.id,
            plain_token=plain_token,
            ttl_hours=settings.jc_password_reset_ttl_hours,
        )
        await self._db.commit()

        reset_url = (
            f"{settings.jc_public_url.rstrip('/')}/auth/reset-password"
            f"?token={plain_token}"
        )
        await self._email.send_password_reset(to_email=user.email, reset_url=reset_url)

    async def reset_password(self, token: str, new_password: str) -> None:
        row = await self._password_resets.get_valid(token)
        if row is None:
            raise AppError("重置链接无效或已过期，请重新发起找回密码。", code="invalid_token")

        user = await self._users.get_by_id(row.user_id)
        if user is None:
            raise AppError("重置链接无效或已过期，请重新发起找回密码。", code="invalid_token")

        await self._users.update_password(user, hash_password(new_password))
        await self._password_resets.mark_used(row)
        await self._db.commit()

    async def send_email_verification(self, user_id: str) -> None:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise AuthError("登录状态已失效，请重新登录。", code="session_invalid")
        if user.email_verified_at is not None:
            return
        if not self._email.smtp_configured():
            raise AppError(
                "邮件服务还没配置好，暂时无法发送验证邮件。",
                code="email_not_configured",
            )

        plain_token = generate_token()
        verification_code = f"{secrets.randbelow(10_000):04d}"
        ttl_seconds = settings.jc_email_verify_ttl_hours * 3600
        await self._email_verifications.issue(
            user_id=user.id,
            plain_token=plain_token,
            verification_code=verification_code,
            ttl_seconds=ttl_seconds,
        )
        verify_url = (
            f"{settings.jc_public_url.rstrip('/')}/auth/verify-email"
            f"?token={plain_token}"
        )
        await self._email.send_email_verification(
            to_email=user.email,
            verify_url=verify_url,
            verification_code=verification_code,
        )

    async def verify_email(self, token: str) -> None:
        user_id = await self._email_verifications.consume_token(token)
        if user_id is None:
            raise AppError("验证链接无效或已过期，请重新发送验证邮件。", code="invalid_token")

        user = await self._users.get_by_id(user_id)
        if user is None:
            raise AppError("验证链接无效或已过期，请重新发送验证邮件。", code="invalid_token")
        if user.email_verified_at is not None:
            return

        await self._users.mark_email_verified(user)
        await self._db.commit()

    async def verify_email_code(self, user_id: str, code: str) -> None:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise AuthError("登录状态已失效，请重新登录。", code="session_invalid")
        if user.email_verified_at is not None:
            return

        result = await self._email_verifications.verify_code(
            user_id=user.id,
            verification_code=code,
            max_attempts=settings.jc_email_verify_max_attempts,
        )
        if result == "expired":
            raise AppError(
                "验证码已过期，请重新发送验证邮件。",
                code="verification_expired",
            )
        if result == "locked":
            raise AppError(
                "验证码输错次数过多，请重新发送验证邮件。",
                code="verification_locked",
            )
        if result == "invalid":
            raise AppError(
                "验证码不正确，请检查邮件里的 4 位数字。",
                code="invalid_verification_code",
            )

        await self._users.mark_email_verified(user)
        await self._db.commit()

    async def get_account(self, user_id: str) -> AccountResponse:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise AuthError("登录状态已失效，请重新登录。", code="session_invalid")
        return self._to_account_response(user)

    async def update_account(self, user_id: str, body: UpdateAccountRequest) -> AccountResponse:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise AuthError("登录状态已失效，请重新登录。", code="session_invalid")

        values = body.model_dump(exclude_unset=True)
        if "display_name" in values:
            display_name = values["display_name"]
            values["display_name"] = display_name.strip() or None if display_name else None
        if values:
            await self._users.update_meta(user, **values)
            await self._db.commit()
        return self._to_account_response(user)

    async def change_password(self, user_id: str, current_password: str, new_password: str) -> None:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise AuthError("登录状态已失效，请重新登录。", code="session_invalid")
        if not verify_password(current_password, user.password_hash):
            raise AppError("当前密码不正确。", code="invalid_password")
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
    def _to_account_response(user: User) -> AccountResponse:
        meta = user.meta
        return AccountResponse(
            **AuthService._to_user_context(user).model_dump(),
            locale=meta.locale if meta else "zh-CN",
            default_elevation_level=meta.default_elevation_level if meta else "elevated",
        )

    @staticmethod
    def _to_user_context(user: User) -> UserContext:
        display_name = user.meta.display_name if user.meta else None
        return UserContext(
            id=user.id,
            email=user.email,
            email_verified=user.email_verified_at is not None,
            display_name=display_name,
            role=user.role,
        )
