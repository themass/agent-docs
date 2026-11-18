"""Chat attachments: keep the bytes out of the message row.

A voice clip and a photo both arrive from the browser as a `data:` URL, and the whole
base64 string used to be written straight into the message row. One frame from the
in-app camera (1280x720 JPEG at q0.92, see `lib/camera-capture.ts`) is around 300 KB
raw — roughly 400 KB once base64 inflates it by 4/3 — and an album photo is tens of
times that. Keeping bytes in a ledger row makes every transcript read drag the image
along with it.

The guard is a size check in code plus `tests/test_agent_attachments.py`, not a column
type: Postgres `TEXT` is unbounded, so the database will happily accept payloads that
would make the ledger unusable to read.

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
from typing import TYPE_CHECKING

from jc.exceptions import AppError
from jc.schemas.agent import AgentAttachment
from jc.storage_backend import get_storage_backend
from jc.storage_client import download_url_for_key
from jc.storage_keys import storage_key

if TYPE_CHECKING:
    from agentkit.web.auth import Actor
    from sqlalchemy.ext.asyncio import AsyncSession

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


def _looks_like(mime: str, raw: bytes) -> bool:
    """True when the bytes are consistent with the mime the browser declared.

    Magic bytes only — no parser. Enough to refuse the case production saw on
    2026-11-18 (SVG bytes posted as `image/jpeg`, stored in the ledger as a
    46-byte "photo"), without pretending to validate files a browser produced.
    An unrecognised mime passes: the allow-list already gates the categories,
    and falsely rejecting a phone's exotic audio is worse than storing bytes
    nothing renders.
    """
    if mime == "image/jpeg":
        return raw[:3] == b"\xff\xd8\xff"
    if mime == "image/png":
        return raw[:8] == b"\x89PNG\r\n\x1a\n"
    if mime == "image/gif":
        return raw[:6] in (b"GIF87a", b"GIF89a")
    if mime == "image/webp":
        return raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"
    if mime == "image/heic":
        # Any ISO base-media container: brands vary by encoder, and a browser
        # would only declare heic for a real HEIC/HEIF anyway.
        return raw[4:8] == b"ftyp"
    if mime == "audio/webm":
        return raw[:4] == b"\x1a\x45\xdf\xa3"
    if mime in ("audio/ogg", "audio/opus"):
        return raw[:4] == b"OggS"
    if mime in ("audio/mp4", "audio/m4a", "audio/aac"):
        return raw[4:8] == b"ftyp" or (len(raw) >= 2 and raw[0] == 0xFF and raw[1] & 0xF0 == 0xF0)
    if mime in ("audio/mpeg", "audio/mp3"):
        return raw[:3] == b"ID3" or (len(raw) >= 2 and raw[0] == 0xFF and raw[1] & 0xE0 == 0xE0)
    if mime in ("audio/wav", "audio/wave"):
        return raw[:4] == b"RIFF" and raw[8:12] == b"WAVE"
    return True


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
    if not _looks_like(mime, raw):
        raise AttachmentRejectedError("附件内容与声明的类型不一致，请重新选择文件。")
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


#: Which upload scene guards which attachment kind (ADR-011 §4). A `file`
# attachment never goes direct: documents arrive as text_preview, and there is
# no scene that accepts arbitrary bytes.
_DIRECT_SCENE_BY_KIND = {"image": "chat-image", "audio": "chat-audio"}


async def prepare_direct_attachments(
    attachments: list[AgentAttachment],
    *,
    db: AsyncSession,
    actor: Actor,
    session_id: str,
) -> list[AgentAttachment]:
    """Bind every direct-upload key, then hand back model-ready copies.

    This runs in the route body, BEFORE the SSE headers go out — the P1-1 rule
    applies to the direct path as much as to inline bytes: a foreign, expired,
    never-uploaded or fake-content key must come back as 4xx JSON, never as a
    200 stream that dies on the first event.

    What one direct attachment costs: one bind (ownership + scene + TTL +
    HEAD size, which is the only place the REAL byte size of a direct upload is
    ever learned) and one readback. The bytes come back inlined as a `data:`
    URL on an in-memory copy — every existing consumer (vision parts, OCR
    flatten, the photo tool) reads `data_url`, and the model hop needs base64
    no matter which transport delivered the bytes (ADR-011 "边界先说死").
    Persistence then sees BOTH fields and stores the bound key instead of
    re-PUTting the same bytes (`plan_attachment_rows` / `upload_pending_attachments`).

    The content type of a hydrated copy is the server-side one recorded at
    sign time, so a client cannot get its spoofed `mime_type` into the ledger
    by lying about a key it legitimately holds. The magic-bytes sniff that
    closed P1-2 for the inline path runs here on the readback for the direct
    path, which otherwise would never have passed through `decode_data_url`.

    The transaction is deliberately left uncommitted: `stream_message` commits
    it with the user row. A rejection before that rolls the bind back, the
    media row stays ISSUED, and the GC reclaims the object — a refused upload
    leaves nothing behind but a bucket object with a known owner and an age.
    """
    if not any(att.object_key for att in attachments):
        return attachments

    from jc.services.media_service import MediaService

    media = MediaService(db)
    prepared: list[AgentAttachment] = []
    total = 0
    for att in attachments:
        if not att.object_key:
            if att.data_url:
                total += len(decode_data_url(att.data_url).raw)
            prepared.append(att)
            continue
        scene = _DIRECT_SCENE_BY_KIND.get(att.kind)
        if scene is None:  # schema validator blocks `file`; belt for future kinds
            raise AttachmentRejectedError("该类型附件不支持直传，请重新选择文件。")
        bound = await media.bind(
            actor=actor, object_key=att.object_key, scene=scene, bound_ref=f"agsn:{session_id}"
        )
        raw = await asyncio.to_thread(get_storage_backend().get_object_bytes, att.object_key)
        if not raw:
            raise AttachmentRejectedError("附件是空的，请重新上传。")
        if not _looks_like(bound.content_type, raw):
            raise AttachmentRejectedError("附件内容与声明的类型不一致，请重新选择文件。")
        if len(raw) > MAX_ATTACHMENT_BYTES:
            limit_mb = MAX_ATTACHMENT_BYTES // (1024 * 1024)
            raise AttachmentTooLargeError(
                f"「{att.label or att.name}」超过 {limit_mb} MB，请压缩后再发送。"
            )
        total += len(raw)
        encoded = base64.b64encode(raw).decode("ascii")
        prepared.append(
            att.model_copy(
                update={
                    "data_url": f"data:{bound.content_type};base64,{encoded}",
                    "mime_type": bound.content_type,
                }
            )
        )
    if total > MAX_MESSAGE_ATTACHMENT_BYTES:
        limit_mb = MAX_MESSAGE_ATTACHMENT_BYTES // (1024 * 1024)
        raise AttachmentTooLargeError(f"这条消息的附件合计超过 {limit_mb} MB，请分几次发送。")
    return prepared


def plan_attachment_rows(
    attachments: list[AgentAttachment],
    *,
    session_id: str,
    message_id: str,
) -> list[dict[str, object]]:
    """Mint the storage key for every attachment that needs one — WITHOUT uploading.

    B-1 §2.2 (key first). The keys are deterministic (`storage_key(...)` derives
    them from `message_id` and the index), so they can be written into the user
    message row and committed before a single byte leaves the process. That order
    is what makes a crash between "row exists" and "object exists" recoverable:

    * old order (PUT, then row): a dead worker left a bucket object nobody
      references, under an `agent/` prefix the GC cannot even enumerate — an
      invisible, permanent leak;
    * new order (row, then PUT): a dead worker leaves a row naming a key with no
      object, which is one SQL query to count and which history already knows how
      to render (`storage_error`).

    `storage_pending` is the marker the upload step clears. It is deliberately
    distinct from `storage_error` (a settled failure): a row that still says
    pending never got its upload step at all, while a row with `storage_error`
    says the upload was attempted and failed.
    """
    rows: list[dict[str, object]] = []
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
        if att.object_key:
            # Direct upload (ADR-011 §6-C): `prepare_direct_attachments` bound
            # this key and inlined the bytes for the model. The bucket already
            # holds the object under a key this actor was issued — copying it
            # again under an agent/ key would double-store every photo and
            # make the media ledger lie about what is live.
            key = att.object_key
            row["storage_key"] = key
            try:
                blob = decode_data_url(att.data_url or "")
                row["size_bytes"] = len(blob.raw)
            except Exception:  # noqa: BLE001
                # Hydrated copies always decode; if that invariant ever breaks,
                # the key is still the durable record — size just stays unknown.
                pass
            try:
                row["download_url"] = download_url_for_key(key)
            except Exception:  # noqa: BLE001
                row["download_url"] = None
        elif att.data_url:
            # The key is decided now, the bytes later (see `upload_pending_attachments`).
            try:
                blob = decode_data_url(att.data_url)
            except Exception:  # noqa: BLE001
                # `validate_inline_attachments` already rejected anything
                # undecodable, so this row would only be reached for a payload
                # that changed under us. Record the failure on the row rather
                # than raising: the user's turn must still go out.
                row["storage_key"] = None
                row["download_url"] = None
                row["storage_error"] = True
                rows.append(row)
                continue
            key = storage_key(
                "agent",
                session_id,
                "attachments",
                f"{message_id}-{index}{blob.extension}",
            )
            row["storage_key"] = key
            row["size_bytes"] = len(blob.raw)
            row["storage_pending"] = True
        rows.append(row)
    return rows


async def upload_pending_attachments(
    attachments: list[AgentAttachment],
    rows: list[dict[str, object]],
    *,
    session_id: str,
    message_id: str,
) -> list[dict[str, object]]:
    """PUT the planned attachment objects and return rows with `storage_pending` settled.

    Returns NEW row dicts and deliberately does not mutate the ones it was given.
    That copy is load-bearing, not stylistic: those dicts are already inside the
    committed payload, so an in-place edit changes the ORM's own loaded value.
    The follow-up `payload = {**payload, "attachments": rows}` then compares equal
    to what SQLAlchemy last flushed, the dirty check finds nothing, no UPDATE is
    issued, and `storage_pending` stays `true` in the database forever — which
    replay renders as "this upload never finished" for a file that uploaded fine.

    An upload failure must not cost the user their message: the row already exists
    and the turn has already been acknowledged, so a failed PUT drops to
    `storage_error` (the bubble says "录音没保存成功") rather than raising.

    Async because `put_object` is a blocking network call and this runs on the
    request loop. Uploading up to `MAX_MESSAGE_ATTACHMENT_BYTES` inline would stall
    *every* concurrent request for the duration, not just this user's.
    """
    store = get_storage_backend()
    settled: list[dict[str, object]] = []
    for index, (att, row) in enumerate(zip(attachments, rows, strict=False)):
        if not row.get("storage_pending"):
            settled.append(row)
            continue
        # A fresh dict per row: see the docstring — mutating the committed one is
        # invisible to the session's dirty check and the state never persists.
        row = dict(row)
        key = row.get("storage_key")
        try:
            if not isinstance(key, str) or not key:
                raise ValueError("planned row lost its key")
            blob = decode_data_url(att.data_url or "")
            await asyncio.to_thread(store.put_object, key, blob.raw, content_type=blob.mime)
            try:
                row["download_url"] = download_url_for_key(key)
            except Exception:  # noqa: BLE001
                # Signing is a convenience; the key is the durable record and the
                # bubble can be re-signed on the next read.
                row["download_url"] = None
            row.pop("storage_pending", None)
            settled.append(row)
        except Exception as exc:  # noqa: BLE001
            # Deliberately not raised: the turn has already been acknowledged, so
            # losing the archive must not lose the user's message. But it must not
            # be silent either — a storage outage used to leave a row that was
            # indistinguishable from "the user sent no media", which is the one
            # state nobody can debug after the fact. The exception type and the
            # key are logged; the blob itself never is.
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
            # A settled failure, not a pending write: this is what the bubble reads
            # to say "录音没保存成功" instead of rendering a dead player.
            row["storage_error"] = True
            row.pop("storage_pending", None)
            settled.append(row)
    return settled


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
        updated = dict(item)
        if updated.get("storage_pending"):
            # A row still marked pending belongs to a turn whose upload step never
            # ran to completion (B-1 §2.2) — most often because the worker died
            # between the row commit and the PUT. The bubble knows only one way to
            # say "this recording was not saved", and that is exactly what this is,
            # so the wire projects it as such. No frontend change, and no dead
            # player: `attachmentSrc` never invents a URL for it.
            #
            # Deliberately does NOT sign a URL: the key exists but the object behind
            # it very likely does not, and a signed link to nothing is worse than no
            # link — the bubble would render a broken image instead of saying the
            # upload did not finish.
            updated["storage_error"] = True
            updated["download_url"] = None
            # The marker itself is server-internal bookkeeping (a write that has
            # not settled). Once it is projected as `storage_error` it has no
            # business on the wire: two flags for one fact invites a client that
            # checks the wrong one.
            updated.pop("storage_pending", None)
            refreshed.append(updated)
            continue
        key = updated.get("storage_key")
        if isinstance(key, str) and key:
            try:
                updated["download_url"] = download_url_for_key(key)
            except Exception:  # noqa: BLE001
                updated["download_url"] = None
        refreshed.append(updated)
    return {**payload, "attachments": refreshed}
