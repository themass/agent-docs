"""Direct-upload issuance ledger (ADR-011).

One row per `POST /media/sign`: the key is minted here, before the browser has
put a single byte into the bucket, so the row is the only server-side fact that
says "this key was issued to this actor for this scene". Bind validates against
it; GC sweeps by it.

`created_at` (from `TimestampMixin`) is the issuance instant the ADR calls
`issued_at` — same value, and a second column with identical content is a
drift hazard, not a feature.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from jc.db.base import Base
from jc.db.mixins import TimestampMixin
from jc.db.types import UTCDateTime


class MediaUpload(Base, TimestampMixin):
    __tablename__ = "jc_media_upload"

    object_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    scene: Mapped[str] = mapped_column(String(32), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    #: What the client said the object would be, checked against the scene cap
    # at sign time. Advisory only — presigned PUT cannot bind Content-Length.
    declared_size: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Real byte count from the bind-time HEAD; NULL until bound.
    actual_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    #: The business object that consumed this upload (message id, source id).
    bound_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bound_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    __table_args__ = (
        # GC's two queries: due expirations, and per-actor audit lookups.
        Index("ix_jc_media_upload_state_expires", "state", "expires_at"),
        Index("ix_jc_media_upload_actor", "actor_id", "created_at"),
    )
