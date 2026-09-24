"""Structured product funnel events (JSON logs)."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("jobcome.events")


def log_product_event(
    event: str,
    *,
    trace_id: str | None = None,
    user_id: str | None = None,
    profile_id: str | None = None,
    session_id: str | None = None,
    **fields: Any,
) -> None:
    payload = {
        "event": event,
        "trace_id": trace_id,
        "user_id": user_id,
        "profile_id": profile_id,
        "session_id": session_id,
        **fields,
    }
    logger.info(json.dumps(payload, ensure_ascii=False))
