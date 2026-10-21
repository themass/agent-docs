"""Resolve session-owned image references; never accept arbitrary URLs or object keys.

The MCP tool requests a frontend crop, not a silent profile mutation. The existing
photo upload service remains the sole owner of normalization and profile binding.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from sqlalchemy import select

from jc.authz import RunScope, require_owned_profile
from jc.exceptions import AppError, NotFoundError
from jc.models.agent import AgentSession
from jc.models.agent_message import AgentMessage
from jc.storage_backend import get_storage_backend
from jc.storage_keys import storage_key


async def session_images(scope: RunScope, message_id: str | None = None) -> list[dict[str, Any]]:
    await require_owned_profile(scope, scope.profile_id)
    session = await scope.db.get(AgentSession, scope.session_id)
    if (
        session is None
        or session.user_id != scope.user_id
        or session.profile_id != scope.profile_id
    ):
        raise NotFoundError("未找到当前会话的图片。", code="photo_source_not_found")
    stmt = (
        select(AgentMessage)
        .where(
            AgentMessage.session_id == session.id,
            AgentMessage.role == "user",
            AgentMessage.event_type == "message",
        )
        .order_by(AgentMessage.created_at.desc(), AgentMessage.id.desc())
    )
    if message_id:
        stmt = stmt.where(AgentMessage.id == message_id)
    rows = (await scope.db.execute(stmt.limit(100))).scalars()
    for row in rows:
        try:
            attachments = json.loads(row.payload_json or "{}").get("attachments", [])
        except (ValueError, AttributeError):
            continue
        if not isinstance(attachments, list):
            continue
        candidates = []
        for index, att in enumerate(attachments):
            if not isinstance(att, dict) or att.get("kind") != "image":
                continue
            key = att.get("storage_key")
            prefix = storage_key("agent", session.id, "attachments", f"{row.id}-{index}")
            if not isinstance(key, str) or key not in [
                prefix + ext for ext in (".jpg", ".jpeg", ".png", ".webp")
            ]:
                continue
            candidates.append(
                {
                    "message_id": row.id,
                    "attachment_index": index,
                    "name": str(att.get("name") or "photo.jpg")[:120],
                    "storage_key": key,
                }
            )
        if candidates:
            return candidates
        if any(isinstance(att, dict) and att.get("kind") == "image" for att in attachments):
            raise NotFoundError(
                "这条消息的图片未成功保存或格式不支持，请重新发送照片。",
                code="photo_source_not_found",
            )
    raise NotFoundError(
        "未找到已保存的聊天图片，请重新发送 JPG、PNG 或 WebP 照片。", code="photo_source_not_found"
    )


async def request_photo_crop(
    scope: RunScope, *, message_id: str | None = None, attachment_index: int | None = None
) -> dict[str, Any]:
    images = await session_images(scope, message_id)
    public = [{k: v for k, v in image.items() if k != "storage_key"} for image in images]
    if attachment_index is None and len(images) > 1:
        return {
            "status": "photo_selection_required",
            "images": public,
            "message": (
                "本条消息有多张图片，请向用户确认使用哪张，"
                "再用对应 message_id 和 attachment_index 调用。"
            ),
        }
    selected = next(
        (
            image
            for image in public
            if attachment_index is None or image["attachment_index"] == attachment_index
        ),
        None,
    )
    if selected is None:
        raise NotFoundError("这张图片不在指定消息中，请重新选择。", code="photo_source_not_found")
    return {
        "status": "photo_crop_required",
        "profile_id": scope.profile_id,
        "session_id": scope.session_id,
        **selected,
        "message": (
            "已提供裁剪入口，尚未设置头像。请用户点击裁剪并保存，"
            "是否在简历显示由用户选择；不要声称已保存。"
        ),
    }


async def read_photo_source(
    scope: RunScope, *, message_id: str, attachment_index: int
) -> tuple[bytes, str]:
    images = await session_images(scope, message_id)
    selected = next(
        (image for image in images if image["attachment_index"] == attachment_index), None
    )
    if selected is None:
        raise NotFoundError("未找到这张聊天图片。", code="photo_source_not_found")
    try:
        raw = await asyncio.to_thread(
            get_storage_backend().get_object_bytes, selected["storage_key"]
        )
    except FileNotFoundError:
        raise NotFoundError(
            "图片文件已不存在，请重新发送照片。", code="photo_source_not_found"
        ) from None
    if len(raw) > 20 * 1024 * 1024:
        raise AppError("图片超过 20MB，请压缩后重新发送。", code="photo_source_too_large")
    suffix = selected["storage_key"].rsplit(".", 1)[-1]
    return raw, {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }[suffix]
