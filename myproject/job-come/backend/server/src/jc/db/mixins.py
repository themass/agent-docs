"""SQLAlchemy mixins."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from jc.db.types import UTCDateTime


class TimestampMixin:
    """`created_at`/`updated_at` with both a Python-side and a DB-side default.

    `server_default=func.now()` alone means the INSERT leaves these columns
    "expired" on the in-memory object — nothing populated them client-side,
    only the database knows the value. Reading `row.created_at` right after
    `session.add()` + `flush()` (before any further `await`) then triggers
    SQLAlchemy's implicit lazy-reload, which needs a greenlet context that a
    sync `model_dump()`/attribute access does not have. On SQLite (tests) this
    went unnoticed; on real async MySQL it surfaces as
    `MissingGreenlet: greenlet_spawn has not been called`.

    Adding `default=`/`onupdate=` (Python callables) means SQLAlchemy already
    has the value in hand before the row round-trips to the database, so no
    attribute is ever expired-and-reloaded — only `server_default` was the
    unsafe part, not the client-side timestamp.

    `server_default` stays as a floor for rows inserted outside the ORM
    (migrations backfilling data, manual SQL), not the primary source of
    truth for ORM-created rows.

    Column type is `UTCDateTime` (see `jc.db.types`), not a bare
    `DateTime(timezone=True)`: MySQL's `DATETIME` has no timezone concept, so
    a plain `DateTime(timezone=True)` column round-trips through `aiomysql`
    as a naive datetime no matter what gets written. `UTCDateTime` is the one
    place that re-attaches `tzinfo=UTC` on every read, which is what makes
    the API's `.isoformat()` output carry a `Z` suffix instead of silently
    being read back as local time by the browser.
    """

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
