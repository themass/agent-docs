"""Database column types — Postgres only.

There is no second dialect to stay compatible with, so these are thin: Postgres
`TEXT` has no length limit, which is exactly what a resume prompt, a full trace
payload or a generated draft needs. The named types stay instead of bare `Text`
so the column still says what it holds, and so a future switch to `JSONB` is one
edit here rather than fifteen at the call sites.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Text
from sqlalchemy.types import TypeDecorator

#: Unbounded text. A whole document, not a short string.
LongText = Text()


class JSONText(TypeDecorator[Any]):
    """A JSON document stored as text.

    Text rather than `JSONB` on purpose: every writer hands over a Python dict
    and every reader gets one back, so the database never looks inside. JSONB
    would buy indexability nothing queries, and it adds a second serialization
    path — psycopg encoding a `str` into a JSON *string literal* is a known trap.
    """

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
    """`JSONText` for documents that can be very large.

    Same storage as `JSONText` on Postgres; kept as a separate name because the
    call sites already say it and because "may exceed a page" is worth stating.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any | None, dialect: object) -> str | None:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value: str | None, dialect: object) -> Any:
        if value is None or value == "":
            return None
        return json.loads(value)


class UTCDateTime(TypeDecorator[datetime]):
    """`DateTime` that always round-trips as UTC-aware.

    The column is `TIMESTAMP WITH TIME ZONE`, so Postgres stores an instant and
    the offset survives. The conversions below guard the boundary: an aware
    value is normalized to UTC before it is sent (a caller that accidentally
    passes local time must not store the wrong instant), and a naive value
    coming back is labeled UTC rather than left ambiguous.

    Why it matters: FastAPI serializes a naive `datetime` via `.isoformat()`
    with no `Z`/offset, and `new Date(...)` in the browser reads an offset-less
    ISO string as *local* time — every admin list, trace and message timestamp
    rendered 8 hours fast in Asia/Shanghai until this existed.
    """

    impl = DateTime(timezone=True)
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
