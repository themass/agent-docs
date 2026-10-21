"""User persistence."""

from __future__ import annotations

from agentkit.common.ids import new_id
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jc.models.enums import ElevationLevel, UserStatus
from jc.models.user import User, UserMeta
from jc.stores.sorting import SortSpec

#: Sortable columns for the admin user directory. `display_name` lives on
#: `UserMeta`, which is why `list_all` always outer-joins it rather than joining
#: only when searching — the join is one-to-one so it cannot duplicate rows, and
#: a conditional join would make the sortable set depend on the filters.
#: `profile_count` / `session_count` are deliberately absent: they are counted
#: per page by the service, so sorting on them would order one page instead of
#: the directory and report a different "most active user" on every page.
USER_SORT = SortSpec(
    fields={
        "created_at": User.created_at,
        "updated_at": User.updated_at,
        "email": User.email,
        "role": User.role,
        "status": User.status,
        # The table's "邮箱验证" column renders from this timestamp, not from
        # `status`; sorting it groups the unverified accounts together.
        "email_verified_at": User.email_verified_at,
        "display_name": UserMeta.display_name,
    },
    default="created_at",
    tiebreaker=User.id,
)


class UserStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, user_id: str) -> User | None:
        stmt = (
            select(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .options(selectinload(User.meta))
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .where(User.email == email.lower(), User.deleted_at.is_(None))
            .options(selectinload(User.meta))
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def list_all(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        sort_by: str | None = None,
        sort_dir: str | None = None,
    ) -> tuple[list[User], int, str, str]:
        """Admin directory listing. `search` matches email or display name.

        Returns the resolved `(sort_by, sort_dir)` with the rows so the response
        can tell the table which header is actually sorted (see `USER_SORT`).
        """
        # `UserMeta` is joined unconditionally because `display_name` is both a
        # search target and a sort key. One-to-one, so it cannot fan rows out.
        base = (
            select(User)
            .outerjoin(UserMeta, UserMeta.user_id == User.id)
            .where(User.deleted_at.is_(None))
        )
        count_stmt = (
            select(func.count())
            .select_from(User)
            .outerjoin(UserMeta, UserMeta.user_id == User.id)
            .where(User.deleted_at.is_(None))
        )
        if search:
            pattern = f"%{search.lower()}%"
            condition = or_(User.email.like(pattern), UserMeta.display_name.like(pattern))
            base = base.where(condition)
            count_stmt = count_stmt.where(condition)
        order_by, field, direction = USER_SORT.order_by(sort_by, sort_dir)
        total = int((await self._db.execute(count_stmt)).scalar_one())
        stmt = (
            base.options(selectinload(User.meta))
            .order_by(*order_by)
            .offset(offset)
            .limit(limit)
        )
        rows = list((await self._db.execute(stmt)).scalars().all())
        return rows, total, field, direction

    async def get_by_ids(self, user_ids: list[str]) -> dict[str, User]:
        """Batch lookup for admin list views that need to annotate rows with
        the owning user's email/display name without an N+1 per row."""
        if not user_ids:
            return {}
        stmt = (
            select(User)
            .where(User.id.in_(user_ids), User.deleted_at.is_(None))
            .options(selectinload(User.meta))
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        return {u.id: u for u in rows}

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str | None = None,
    ) -> User:
        user = User(
            id=new_id("usr"),
            email=email.lower(),
            password_hash=password_hash,
            status=UserStatus.ACTIVE,
        )
        user.meta = UserMeta(
            user_id=user.id,
            display_name=display_name,
            default_elevation_level=ElevationLevel.ELEVATED,
        )
        self._db.add(user)
        await self._db.flush()
        return user

    async def update_password(self, user: User, password_hash: str) -> User:
        from datetime import UTC, datetime

        user.password_hash = password_hash
        user.password_changed_at = datetime.now(UTC)
        await self._db.flush()
        return user

    async def mark_email_verified(self, user: User) -> User:
        from datetime import UTC, datetime

        user.email_verified_at = datetime.now(UTC)
        await self._db.flush()
        return user

    async def get_or_create_meta(self, user_id: str) -> UserMeta:
        user = await self.get_by_id(user_id)
        if user is None:
            raise ValueError(f"User not found: {user_id}")
        if user.meta is None:
            user.meta = UserMeta(
                user_id=user_id,
                default_elevation_level=ElevationLevel.ELEVATED,
            )
            self._db.add(user.meta)
            await self._db.flush()
        return user.meta

    async def update_meta(
        self,
        user: User,
        *,
        display_name: str | None | object = ...,
        locale: str | object = ...,
        default_elevation_level: str | object = ...,
    ) -> User:
        """Update only explicitly supplied account-preference fields."""
        meta = user.meta
        if meta is None:
            meta = UserMeta(
                user_id=user.id,
                default_elevation_level=ElevationLevel.ELEVATED,
            )
            user.meta = meta
            self._db.add(meta)
        if display_name is not ...:
            meta.display_name = display_name if isinstance(display_name, str) else None
        if locale is not ...:
            meta.locale = str(locale)
        if default_elevation_level is not ...:
            meta.default_elevation_level = str(default_elevation_level)
        await self._db.flush()
        return user
