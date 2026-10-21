"""Admin user directory — read-only aggregation over users, profiles, sessions."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from jc.exceptions import NotFoundError
from jc.models.user import User
from jc.schemas.admin_user import (
    AdminUserDetailResponse,
    AdminUserListItem,
    AdminUserListResponse,
    AdminUserProfileSummary,
)
from jc.schemas.profile import ProfileResponse
from jc.stores.agent_store import AgentStore
from jc.stores.profile_store import ProfileStore
from jc.stores.user_store import UserStore


def _to_list_item(user: User, *, profile_count: int, session_count: int) -> AdminUserListItem:
    return AdminUserListItem(
        id=user.id,
        email=user.email,
        role=user.role,
        status=user.status,
        display_name=user.meta.display_name if user.meta else None,
        email_verified=user.email_verified_at is not None,
        profile_count=profile_count,
        session_count=session_count,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


class AdminUserService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._users = UserStore(db)
        self._profiles = ProfileStore(db)
        self._sessions = AgentStore(db)

    async def list_users(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        sort_by: str | None = None,
        sort_dir: str | None = None,
    ) -> AdminUserListResponse:
        rows, total, sorted_by, sorted_dir = await self._users.list_all(
            limit=min(limit, 200),
            offset=offset,
            search=search,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
        user_ids = [u.id for u in rows]
        profile_counts = await self._profiles.profile_counts_by_user(user_ids)
        session_counts = await self._sessions.session_counts_by_user(user_ids)
        users = [
            _to_list_item(
                u,
                profile_count=profile_counts.get(u.id, 0),
                session_count=session_counts.get(u.id, 0),
            )
            for u in rows
        ]
        return AdminUserListResponse(
            users=users,
            total=total,
            limit=limit,
            offset=offset,
            sort_by=sorted_by,
            sort_dir=sorted_dir,
        )

    async def get_user(self, user_id: str) -> AdminUserDetailResponse:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("用户不存在或已删除。", code="user_not_found")
        profiles = await self._profiles.list_for_user(user_id)
        profile_count = len(profiles)
        session_counts = await self._sessions.session_counts_by_user([user_id])
        meta = user.meta
        return AdminUserDetailResponse(
            **_to_list_item(
                user,
                profile_count=profile_count,
                session_count=session_counts.get(user_id, 0),
            ).model_dump(),
            locale=meta.locale if meta else None,
            default_elevation_level=meta.default_elevation_level if meta else None,
            profiles=[
                AdminUserProfileSummary(
                    id=p.id,
                    status=p.status,
                    version=p.version,
                    locale=p.locale,
                    contact_name=p.contact_name,
                    summary_text=p.summary_text,
                    confirmed_at=p.confirmed_at,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
                for p in profiles
            ],
        )

    async def get_profile(self, profile_id: str) -> ProfileResponse:
        """Full structured profile, same shape the owner's own view gets.

        Admin has no separate "is this profile confirmed/visible" gate the
        owner-facing endpoint applies -- reading any non-deleted profile by id
        is exactly what this surface is for. Reuses `ProfileService`'s mapper
        so the two never drift into two different JSON shapes for the same row.
        """
        from jc.services.profile_service import ProfileService

        profile = await self._profiles.get_by_id(profile_id, with_sources=True)
        if profile is None:
            raise NotFoundError("简历档案不存在或已删除。", code="profile_not_found")
        return ProfileService._to_response(profile)
