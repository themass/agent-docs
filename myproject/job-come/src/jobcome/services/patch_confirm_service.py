"""Pending profile patch confirmations (Redis-backed)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from agentkit.common.ids import new_id

from jobcome.redis_client import get_redis

_TTL_SECONDS = 2 * 3600
_KEY_PREFIX = "jc:patch_confirm:"


@dataclass(slots=True)
class PendingPatchConfirm:
    confirm_id: str
    session_id: str
    user_id: str
    profile_id: str
    patch: dict[str, Any]
    preview: dict[str, Any]
    created_at: datetime


def _serialize(row: PendingPatchConfirm) -> str:
    return json.dumps(
        {
            "confirm_id": row.confirm_id,
            "session_id": row.session_id,
            "user_id": row.user_id,
            "profile_id": row.profile_id,
            "patch": row.patch,
            "preview": row.preview,
            "created_at": row.created_at.isoformat(),
        },
        ensure_ascii=False,
    )


def _deserialize(raw: str) -> PendingPatchConfirm:
    data = json.loads(raw)
    created = data.get("created_at")
    created_at = datetime.fromisoformat(created) if isinstance(created, str) else datetime.now(UTC)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return PendingPatchConfirm(
        confirm_id=str(data["confirm_id"]),
        session_id=str(data.get("session_id") or ""),
        user_id=str(data.get("user_id") or ""),
        profile_id=str(data.get("profile_id") or ""),
        patch=dict(data.get("patch") or {}),
        preview=dict(data.get("preview") or {}),
        created_at=created_at,
    )


async def create_pending(
    *,
    session_id: str,
    user_id: str,
    profile_id: str,
    patch: dict[str, Any],
    preview: dict[str, Any],
) -> PendingPatchConfirm:
    confirm_id = new_id("cfm")
    row = PendingPatchConfirm(
        confirm_id=confirm_id,
        session_id=session_id,
        user_id=user_id,
        profile_id=profile_id,
        patch=patch,
        preview=preview,
        created_at=datetime.now(UTC),
    )
    redis = get_redis()
    await redis.set(_KEY_PREFIX + confirm_id, _serialize(row), ex=_TTL_SECONDS)
    return row


async def get_pending(confirm_id: str) -> PendingPatchConfirm | None:
    redis = get_redis()
    raw = await redis.get(_KEY_PREFIX + confirm_id)
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return _deserialize(raw)


async def pop_pending(confirm_id: str) -> PendingPatchConfirm | None:
    row = await get_pending(confirm_id)
    if row is None:
        return None
    redis = get_redis()
    await redis.delete(_KEY_PREFIX + confirm_id)
    return row
