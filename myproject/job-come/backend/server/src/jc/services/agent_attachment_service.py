"""Chat attachments: keep the bytes out of the message row.

A voice clip and a photo both arrive from the browser as a `data:` URL, and the whole
base64 string used to be written into `jc_agent_message.payload_json`. That column is
MySQL `TEXT`, which holds 65,535 **bytes**. A single frame from the in-app camera
(1280x720 JPEG at q0.92, see `lib/camera-capture.ts`) is around 300 KB raw, so roughly
400 KB once base64 inflates it by 4/3 — about six times over the limit, and a photo
picked from a phone album is tens of times over.

Why no test caught it: the suite runs on SQLite, whose TEXT has no length limit. The
failure only exists on the real database, which is the same shape of defect as the
路径 one — a difference between the test environment and production that the tests are
structurally unable to see. So the guard here is a size check in code plus
`tests/test_agent_attachments.py`, not a column type.

The blob goes to object storage under a JC-owned key (`storage_keys.storage_key`),
exactly like resume sources and exports already do, and the message row keeps the key
plus a signed URL for playback. The live turn still gets the `data:` URL in memory,
because the vision model needs the bytes and uploading does not change that.

Voice clips additionally carry a `transcript`. There is no server-side speech-to-text in
this version: the browser recognizes the speech, and both the words and the recording
come up together. The words are what the model reads and what a replayed turn shows;
the recording is the archive you need when someone asks whether a number in their resume
was really said out loud. Storing one without the other makes both much less useful, so
they are written to the same row.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import logging
from dataclasses import dataclass

from jc.exceptions import AppError
from jc.schemas.agent import AgentAttachment
from jc.storage_backend import get_storage_backend
from jc.storage_client import download_url_for_key
from jc.storage_keys import storage_key

logger = logging.getLogger(__name__)

#: Per-attachment ceiling on decoded bytes. Chosen to cover a full-resolution phone
#: photo and a few minutes of opus audio while staying far enough below anything that
#: would make a chat turn slow to upload.
MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024

#: Ceiling on one message's attachments combined, so a dozen photos cannot add up to a
#: request the gateway drops without an explanation the user can act on.
MAX_MESSAGE_ATTACHMENT_BYTES = 24 * 1024 * 1024

#: What may be sent as a `data:` URL at all. A document arrives as `text_preview`
#: instead, so an executable or archive has no reason to be here.
ALLOWED_INLINE_PREFIXES = ("image/", "audio/")

_EXT_BY_MIME = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/heic": ".heic",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/opus": ".ogg",
    "audio/mp4": ".m4a",
    "audio/m4a": ".m4a",
    "audio/aac": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/wave": ".wav",
}


class AttachmentTooLargeError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="attachment_too_large")


class AttachmentRejectedError(AppError):
    def __init__(self, message: str, *, code: str = "attachment_rejected") -> None:
        super().__init__(message, code=code)


@dataclass(frozen=True, slots=True)
class DecodedBlob:
    """The bytes behind one `data:` URL, with the mime the browser declared."""

    raw: bytes
    mime: str

    @property
    def extension(self) -> str:
        return _EXT_BY_MIME.get(self.mime, ".bin")


def decode_data_url(data_url: str) -> DecodedBlob:
    """Parse `data:<mime>;base64,<payload>`.

    Only base64 payloads are accepted. A percent-encoded `data:` URL is legal in the
    spec but nothing in JC produces one, and accepting a second encoding would mean two
    paths to get bytes in.
    """
    if not data_url.startswith("data:"):
        raise AttachmentRejectedError("附件格式不支持，请重新选择文件。")
    try:
        header, payload = data_url[len("data:") :].split(",", 1)
    except ValueError:
        raise AttachmentRejectedError("附件内容不完整，请重新上传。") from None
    if ";base64" not in header:
        raise AttachmentRejectedError("附件格式不支持，请重新选择文件。")
    mime = header.split(";", 1)[0].strip().lower()
    if not mime.startswith(ALLOWED_INLINE_PREFIXES):
        raise AttachmentRejectedError("只支持图片和语音附件。")
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        raise AttachmentRejectedError("附件内容已损坏，请重新上传。") from None
    if not raw:
        raise AttachmentRejectedError("附件是空的，请重新上传。")
    return DecodedBlob(raw=raw, mime=mime)


def validate_inline_attachments(attachments: list[AgentAttachment]) -> None:
    """Reject oversized input before any model or storage call.

    Deliberately ahead of the turn rather than at persistence time: the user should be
    told their photo is too big before waiting through a vision call for it.
    """
    total = 0
    for att in attachments:
        if not att.data_url:
            continue
        blob = decode_data_url(att.data_url)
        size = len(blob.raw)
        if size > MAX_ATTACHMENT_BYTES:
            limit_mb = MAX_ATTACHMENT_BYTES // (1024 * 1024)
            raise AttachmentTooLargeError(
                f"「{att.label or att.name}」超过 {limit_mb} MB，请压缩后再发送。"
            )
        total += size
    if total > MAX_MESSAGE_ATTACHMENT_BYTES:
        limit_mb = MAX_MESSAGE_ATTACHMENT_BYTES // (1024 * 1024)
        raise AttachmentTooLargeError(f"这条消息的附件合计超过 {limit_mb} MB，请分几次发送。")


async def offload_for_persistence(
    attachments: list[AgentAttachment],
    *,
    session_id: str,
    message_id: str,
) -> list[dict[str, object]]:
    """Upload each inline blob and return rows safe to store in the message payload.

    The returned dicts never carry `data_url`. They carry `storage_key` (durable) and
    `download_url` (signed, short-lived), so replaying history re-signs from the key
    rather than depending on a URL that has since expired.

    An upload failure must not cost the user their message: the turn has already run
    and the answer is on its way, so a failed offload drops to a row without media
    rather than raising.

    Async because `put_object` is a blocking network call and this runs on the request
    loop. Uploading up to `MAX_MESSAGE_ATTACHMENT_BYTES` inline would stall *every*
    concurrent request for the duration, not just this user's — the one thing the chat
    path cannot afford, since it already serializes runs behind a process-wide lock.
    """
    rows: list[dict[str, object]] = []
    store = get_storage_backend()
    for index, att in enumerate(attachments):
        row: dict[str, object] = {
            "kind": att.kind,
            "name": att.name,
            "label": att.label,
            "mime_type": att.mime_type,
            "text_preview": att.text_preview,
        }
        # A voice clip without its transcript is an audio player nobody can search,
        # skim, or quote from. The words came from the browser and this row is the only
        # place they survive alongside the recording.
        if att.transcript:
            row["transcript"] = att.transcript
        if att.duration_ms is not None:
            row["duration_ms"] = att.duration_ms
        if att.data_url:
            try:
                blob = decode_data_url(att.data_url)
                key = storage_key(
                    "agent",
                    session_id,
                    "attachments",
                    f"{message_id}-{index}{blob.extension}",
                )
                await asyncio.to_thread(
                    store.put_object, key, blob.raw, content_type=blob.mime
                )
                row["storage_key"] = key
                row["size_bytes"] = len(blob.raw)
                try:
                    row["download_url"] = download_url_for_key(key)
                except Exception:  # noqa: BLE001
                    # Signing is a convenience; the key is the durable record and the
                    # bubble can be re-signed on the next read.
                    row["download_url"] = None
            except Exception as exc:  # noqa: BLE001
                # Deliberately not raised: the turn has already run and the answer is
                # on its way, so losing the archive must not lose the user's message.
                # But it must not be silent either — a storage outage used to leave a
                # row that was indistinguishable from "the user sent no media", which
                # is the one state nobody can debug after the fact. The exception type
                # and the key are logged; the blob itself never is.
                logger.warning(
                    "attachment offload failed",
                    extra={
                        "session_id": session_id,
                        "message_id": message_id,
                        "attachment_index": index,
                        "attachment_kind": att.kind,
                        "error_type": type(exc).__name__,
                    },
                )
                row["storage_key"] = None
                row["download_url"] = None
                # Lets the bubble say "录音没保存成功" instead of rendering a dead
                # player, and lets an operator count the damage with one query.
                row["storage_error"] = True
        rows.append(row)
    return rows


def resign_persisted_attachments(payload: dict[str, object] | None) -> dict[str, object] | None:
    """Refresh signed URLs when replaying history.

    Signed URLs expire (`JC_DOWNLOAD_URL_TTL_SEC`, 15 min by default) while a chat
    transcript does not, so a stored URL is only a cache. Reopening a two-day-old
    session must still show the photo.
    """
    if not payload:
        return payload
    raw = payload.get("attachments")
    if not isinstance(raw, list):
        return payload
    refreshed: list[object] = []
    for item in raw:
        if not isinstance(item, dict):
            refreshed.append(item)
            continue
        key = item.get("storage_key")
        if isinstance(key, str) and key:
            updated = dict(item)
            try:
                updated["download_url"] = download_url_for_key(key)
            except Exception:  # noqa: BLE001
                updated["download_url"] = None
            refreshed.append(updated)
        else:
            refreshed.append(item)
    return {**payload, "attachments": refreshed}
