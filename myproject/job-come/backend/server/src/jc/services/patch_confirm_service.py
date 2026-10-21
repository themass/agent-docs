"""Durable write proposals. No TTL, Redis dependency, or destructive reads.

Caller owns transactions. A pending command and its decision survive API/MCP
restarts and work across instances sharing the database. Locking is session-local.
"""

from __future__ import annotations

import json
from typing import Any

from agentkit.common.ids import new_id
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jc.authz import RunScope
from jc.exceptions import ConflictError, NotFoundError
from jc.models.agent import AgentSession
from jc.models.agent_message import AgentMessage
from jc.models.profile_patch_confirm import ProfilePatchConfirm


async def supersede_pending_confirms(
    db: AsyncSession,
    *,
    session_id: str,
    profile_id: str,
    exclude_id: str | None = None,
) -> list[str]:
    """Retire older pending cards so users do not confirm a stale version_before."""
    rows = (
        await db.execute(
            select(ProfilePatchConfirm)
            .where(
                ProfilePatchConfirm.session_id == session_id,
                ProfilePatchConfirm.profile_id == profile_id,
                ProfilePatchConfirm.status == "pending",
            )
            .with_for_update()
        )
    ).scalars().all()
    retired: list[str] = []
    for row in rows:
        if exclude_id and row.id == exclude_id:
            continue
        row.status = "superseded"
        retired.append(row.id)
    return retired


async def create_pending(
    *,
    db: AsyncSession,
    session_id: str,
    user_id: str,
    profile_id: str,
    patch: dict[str, Any],
    preview: dict[str, Any],
) -> ProfilePatchConfirm:
    row = ProfilePatchConfirm(
        id=new_id("cfm"),
        session_id=session_id,
        user_id=user_id,
        profile_id=profile_id,
        patch=patch,
        preview=preview,
        status="pending",
    )
    db.add(row)
    await db.flush()
    await supersede_pending_confirms(
        db, session_id=session_id, profile_id=profile_id, exclude_id=row.id
    )
    return row


async def load_confirmation(scope: RunScope, confirm_id: str) -> ProfilePatchConfirm:
    # Serializes decisions for this session across instances, including recovery
    # of old commands not yet represented in the new table. Never process-global.
    owner = (
        await scope.db.execute(
            select(AgentSession.id)
            .where(
                AgentSession.id == scope.session_id,
                AgentSession.user_id == scope.user_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if owner is None:
        raise NotFoundError("会话不存在或不属于当前用户。", code="agent_session_not_found")
    row = (
        await scope.db.execute(
            select(ProfilePatchConfirm)
            .where(
                ProfilePatchConfirm.id == confirm_id,
                ProfilePatchConfirm.session_id == scope.session_id,
                ProfilePatchConfirm.user_id == scope.user_id,
                ProfilePatchConfirm.profile_id == scope.profile_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if row is not None:
        return row
    return await _recover_historical_card(scope, confirm_id)


async def _recover_historical_card(scope: RunScope, confirm_id: str) -> ProfilePatchConfirm:
    """Trust only server-persisted confirm events, never client-supplied patches.

    Old cards include patch + version_before. Recovery still goes through the
    normal ownership, validation and version CAS; it cannot overwrite newer edits.
    """
    messages = (
        (
            await scope.db.execute(
                select(AgentMessage)
                .where(
                    AgentMessage.session_id == scope.session_id,
                    AgentMessage.event_type.in_(["confirm", "confirm_applied", "confirm_rejected"]),
                )
                .order_by(AgentMessage.created_at, AgentMessage.id)
            )
        )
        .scalars()
        .all()
    )
    proposal = None
    for message in messages:
        try:
            payload = json.loads(message.payload_json or "{}")
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("confirm_id") == confirm_id:
            if message.event_type != "confirm":
                raise ConflictError(
                    "这条修改已经处理，请刷新会话查看结果。", code="confirmation_processed"
                )
            proposal = payload
        # Before this fix applied events omitted confirm_id. Do not guess which
        # proposal they consumed: profile-version CAS below provides the floor.
    if proposal is None or proposal.get("profile_id") != scope.profile_id:
        raise NotFoundError(
            "未找到这条修改，请让舟卡重新生成修改确认。", code="confirmation_not_found"
        )
    preview = proposal.get("preview")
    patch = proposal.get("patch")
    if (
        not isinstance(preview, dict)
        or type(preview.get("version_before")) is not int
        or not isinstance(patch, dict)
    ):
        raise ConflictError(
            "旧确认缺少版本信息，请让舟卡重新生成修改确认。", code="confirmation_unrecoverable"
        )
    row = ProfilePatchConfirm(
        id=confirm_id,
        session_id=scope.session_id,
        user_id=scope.user_id,
        profile_id=scope.profile_id,
        patch=patch,
        preview=preview,
        status="pending",
    )
    scope.db.add(row)
    await scope.db.flush()
    return row


async def hydrate_confirmation_event(scope: RunScope, event: dict[str, Any]) -> dict[str, Any]:
    """Expand a bounded model receipt into the exact owner-scoped UI proposal.

    Read-only: do not take the decision lock while the model is still streaming.
    """
    row = (await scope.db.execute(
        select(ProfilePatchConfirm).where(
            ProfilePatchConfirm.id == event.get("confirm_id"),
            ProfilePatchConfirm.session_id == scope.session_id,
            ProfilePatchConfirm.user_id == scope.user_id,
            ProfilePatchConfirm.profile_id == scope.profile_id,
        )
    )).scalar_one_or_none()
    if row is None:
        raise NotFoundError("未找到这条修改，请重新生成修改确认。", code="confirmation_not_found")
    return {**event, "profile_id": row.profile_id, "patch": row.patch, "preview": row.preview}
