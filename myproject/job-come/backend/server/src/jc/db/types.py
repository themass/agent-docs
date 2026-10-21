"""Database column types."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.types import TypeDecorator

# Prompts and model responses routinely exceed MySQL TEXT (64 KB), and CJK costs
# 3 bytes per character in utf8mb4 — a 20k-character resume prompt already does not
# fit. Payload columns must use this variant, not a bare Text.
LongText = Text().with_variant(LONGTEXT, "mysql")


class JSONText(TypeDecorator[Any]):
    """Store JSON documents in TEXT/LONGTEXT for MySQL 5.6 compatibility."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any | None, dialect: object) -> str | None:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value: str | None, dialect: object) -> Any:
        if value is None or value == "":
            return {}
        return json.loads(value)


class JSONLongText(TypeDecorator[Any]):
    """Store JSON documents in LONGTEXT — for payloads that can exceed 64 KB.

    `JSONText` above is `Text` (64 KB), which is enough for small structured
    fields (tags, progress counters) but not for a full agent-trace event: a
    `tool_result` payload or a `run_context` system prompt is exactly the kind
    of content `LongText` (see above) exists to hold, and this is its JSON
    counterpart — same MySQL variant, JSON (de)serialization on top.
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "mysql":
            return dialect.type_descriptor(LONGTEXT())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Any | None, dialect: object) -> str | None:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value: str | None, dialect: object) -> Any:
        if value is None or value == "":
            return None
        return json.loads(value)


class UTCDateTime(TypeDecorator[datetime]):
    """`DateTime` that always round-trips as UTC-aware, regardless of driver.

    MySQL's `DATETIME` column has no timezone concept at all: whatever gets
    written is stored as a bare wall-clock value, and `aiomysql` reads it back
    as a *naive* `datetime` no matter what SQLAlchemy column type requested it
    (`DateTime(timezone=True)` only changes DDL on dialects that support a
    real `TIMESTAMP WITH TIME ZONE`; MySQL is not one of them). Every writer
    in this codebase (`TimestampMixin`, `bind_snapshot_source`, etc.) stores
    `datetime.now(UTC)`, so the *value* is always UTC — the problem is purely
    that the naive datetime coming back from the driver has lost the label
    saying so.

    That loss is not cosmetic. FastAPI/Pydantic serializes a naive `datetime`
    via `.isoformat()` with no `Z`/offset suffix (e.g. `2026-10-19T08:30:00`).
    `JSON.parse` + `new Date(...)` on the frontend treats an offset-less ISO
    string as *local* time, not UTC, so a UTC instant gets displayed as if it
    already were wall-clock time in the browser's timezone — every admin
    list, trace, and message timestamp in the UI showed up offset by exactly
    the browser's UTC offset (8 hours fast in Asia/Shanghai) until this type
    existed.

    `process_bind_param` strips tzinfo before handing the value to the MySQL
    driver (a MySQL `DATETIME` cannot store an offset; passing an aware value
    through unchanged works today only by accident of driver behavior) but
    first converts to UTC so a caller that accidentally passes a non-UTC
    aware datetime does not silently store the wrong wall-clock value.
    `process_result_value` re-attaches `tzinfo=UTC` on the way out, which is
    safe precisely because every write path already guarantees UTC going in.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(UTC)
        return value.replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            return value.astimezone(UTC)
        return value.replace(tzinfo=UTC)
