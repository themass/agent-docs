"""Database column types."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator


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
