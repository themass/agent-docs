"""Profile headshot: accept a cropped image, store it, and own the on/off switch.

Division of labour with the frontend
------------------------------------
The crop happens in the browser (`components/resume/PhotoCropDialog.tsx`) and this
module receives the already-cropped result. That split is deliberate: framing a face
is a direct-manipulation gesture with immediate visual feedback, so the user should
see exactly what they will get while dragging. A server-side "smart crop" would
guess, and a guess about where someone's face sits in their own headshot is the kind
of wrong that is both very visible and impossible to argue with.

What the server still owns, because the browser cannot be trusted with it:

- **Re-encoding.** Whatever arrives is decoded and written back out as JPEG at a
  bounded size. This normalises away EXIF orientation (a phone portrait that renders
  sideways in the PDF is the single most common headshot complaint), strips metadata
  that may carry GPS coordinates from the original capture, and guarantees the
  exporter receives a format it can actually draw.
- **Dimension ceiling.** A resume headshot is printed around 25mm wide. Anything past
  `MAX_EDGE_PX` is bytes nobody sees, in a payload that gets signed and fetched on
  every export.
- **Decode-bomb refusal.** `Image.open` is lazy, so a hostile file can declare an
  enormous canvas in a few kilobytes. `MAX_DECODED_PIXELS` is checked against the
  declared size *before* `load()` touches the pixel data.

Nothing here writes the profile row. The caller holds the transaction, so storing the
object and mutating the payload cannot half-succeed in two different places.
"""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Any

from jc.exceptions import AppError
from jc.schemas.profile_payload import ProfilePhoto
from jc.storage_backend import get_storage_backend
from jc.storage_client import download_url_for_key
from jc.storage_keys import storage_key

logger = logging.getLogger(__name__)

#: Ceiling on the uploaded (already-cropped) bytes. A cropped headshot is small; this
#: is generous enough for a high-DPI crop off a modern phone camera and still far
#: below anything that would make the upload itself feel slow.
MAX_UPLOAD_BYTES = 6 * 1024 * 1024

#: Longest edge kept after re-encoding. 1024px covers a 25mm print at well over
#: 600dpi, so the print quality ceiling is the printer, not this number.
MAX_EDGE_PX = 1024

#: Refused before pixels are decoded. 50MP is past any real phone camera while still
#: cheap to reject, which is what makes it a usable decompression-bomb guard.
MAX_DECODED_PIXELS = 50_000_000

#: Formats worth accepting from a file picker. HEIC is absent on purpose: Pillow needs
#: an extra plugin for it, and the browser already hands us a canvas-encoded JPEG or
#: PNG after the crop, so a HEIC original has been converted before it ever arrives.
ALLOWED_INPUT_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})

_OUTPUT_MIME = "image/jpeg"
_OUTPUT_QUALITY = 88


class PhotoRejectedError(AppError):
    def __init__(self, message: str, *, code: str = "photo_rejected") -> None:
        super().__init__(message, code=code)


def _normalise_image(raw: bytes) -> tuple[bytes, int, int]:
    """Decode, orient, bound, and re-encode to JPEG. Returns (bytes, width, height).

    Runs entirely on CPU with no network, so the caller offloads it to a thread rather
    than blocking the request loop on a megapixel decode.
    """
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        image = Image.open(io.BytesIO(raw))
    except UnidentifiedImageError:
        raise PhotoRejectedError("这个文件不是能识别的图片，请换一张（JPG / PNG / WebP）。") from None
    except Exception:  # noqa: BLE001
        raise PhotoRejectedError("图片读取失败，请换一张试试。") from None

    with image:
        if (image.format or "").upper() not in ALLOWED_INPUT_FORMATS:
            raise PhotoRejectedError("只支持 JPG、PNG 和 WebP 格式的照片。")

        # Checked against the *declared* dimensions, before `load()`/`exif_transpose`
        # allocate anything -- that ordering is the whole point of the guard.
        width, height = image.size
        if width <= 0 or height <= 0:
            raise PhotoRejectedError("图片尺寸无效，请换一张试试。")
        if width * height > MAX_DECODED_PIXELS:
            raise PhotoRejectedError("照片分辨率过高，请先压缩或裁剪后再上传。")

        # Applies the EXIF orientation tag and drops it, so downstream renderers that
        # ignore EXIF (most PDF/DOCX paths) still draw the photo upright.
        oriented = ImageOps.exif_transpose(image) or image
        try:
            # Alpha cannot survive JPEG; compositing onto white matches how a resume
            # page will show it anyway, and is less surprising than a black halo.
            if oriented.mode in {"RGBA", "LA", "P"}:
                converted = oriented.convert("RGBA")
                from PIL import Image as _Image

                backdrop = _Image.new("RGB", converted.size, (255, 255, 255))
                backdrop.paste(converted, mask=converted.split()[-1])
                oriented = backdrop
            elif oriented.mode != "RGB":
                oriented = oriented.convert("RGB")

            oriented.thumbnail((MAX_EDGE_PX, MAX_EDGE_PX))
            buffer = io.BytesIO()
            oriented.save(buffer, format="JPEG", quality=_OUTPUT_QUALITY, optimize=True)
        except PhotoRejectedError:
            raise
        except Exception:  # noqa: BLE001
            raise PhotoRejectedError("图片处理失败，请换一张试试。") from None

        return buffer.getvalue(), oriented.width, oriented.height


async def store_profile_photo(
    raw: bytes,
    *,
    profile_id: str,
    enabled: bool,
) -> ProfilePhoto:
    """Normalise and upload a headshot, returning the payload fragment to persist.

    `enabled` is passed in rather than defaulted here so the caller can express both
    "upload and show it" (the user ticked the box in the crop dialog) and "upload but
    keep it off" without this function having an opinion about product defaults.

    An upload failure *does* raise, unlike chat attachments: there the turn had already
    run and the answer was in flight, so losing the archive was better than losing the
    reply. Here the upload is the entire operation -- reporting success with no stored
    object would leave the user looking at a photo that vanishes on reload.
    """
    if not raw:
        raise PhotoRejectedError("照片是空的，请重新选择。")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise PhotoRejectedError("照片太大了，请裁剪后再上传（上限 6MB）。")

    normalised, width, height = await asyncio.to_thread(_normalise_image, raw)

    # Fixed filename per profile: a headshot is a single-valued field, so replacing it
    # should replace the object rather than accumulate one orphan per re-crop.
    key = storage_key("profile", profile_id, "photo", "headshot.jpg")
    store = get_storage_backend()
    try:
        await asyncio.to_thread(
            store.put_object, key, normalised, content_type=_OUTPUT_MIME
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "profile photo upload failed",
            extra={"profile_id": profile_id, "error_type": type(exc).__name__},
        )
        raise PhotoRejectedError(
            "照片没能保存成功，请稍后再试。", code="photo_storage_failed"
        ) from exc

    return ProfilePhoto(
        storage_key=key,
        download_url=_safe_sign(key),
        mime_type=_OUTPUT_MIME,
        width=width,
        height=height,
        enabled=enabled,
    )


def _safe_sign(key: str) -> str | None:
    """Sign for immediate display; `None` on failure since the key is the durable part."""
    try:
        return download_url_for_key(key)
    except Exception:  # noqa: BLE001
        return None


def resign_photo(photo: ProfilePhoto | None) -> ProfilePhoto | None:
    """Refresh the signed URL when a stored profile is read back.

    Mirrors `agent_attachment_service.resign_persisted_attachments`: the persisted
    `download_url` is expected to be stale, so every read path re-signs from the key
    instead of trusting what was written. Returns the same object untouched when there
    is nothing to sign, so callers can apply it unconditionally.
    """
    if photo is None or not photo.storage_key:
        return photo
    return photo.model_copy(update={"download_url": _safe_sign(photo.storage_key)})

def set_header_photo(sections: dict[str, Any], uri: str | None) -> dict[str, Any]:
    """Return `sections` with the header carrying exactly `uri`, or no photo at all.

    Pure and absolute in both directions: a `None` *removes* any inherited
    `photo_data_uri` rather than leaving it alone. That matters because the drafts
    these sections come from are snapshots -- one generated while the switch was on
    keeps the key forever -- so "no photo" has to be something this function can
    actively assert, not just decline to add.

    Shallow-copies down to `header` and never mutates the argument: the input is
    usually a persisted row's `sections`, and writing a render-time decision into it
    would bake today's switch state into storage.
    """
    out = dict(sections)
    header = out.get("header")
    header = dict(header) if isinstance(header, dict) else {}
    if uri:
        header["photo_data_uri"] = uri
    else:
        header.pop("photo_data_uri", None)
    out["header"] = header
    return out


def apply_photo_to_sections(
    sections: dict[str, Any],
    photo: ProfilePhoto | None,
    *,
    locale: str | None = None,
) -> dict[str, Any]:
    """Resolve the live profile's headshot for `locale` and write it onto the header.

    The single entry point for "does this rendered resume carry a photo", so preview
    and every export format cannot disagree. They used to: preview rebuilt the header
    from a whitelist of text fields and dropped `photo_data_uri` entirely, while
    export rendered the stored draft verbatim and kept it -- so the photo was
    invisible while it was still fixable and appeared only in the downloaded file.

    Resolved against the live profile rather than read out of the draft snapshot on
    purpose. A snapshot is the right model for *written* content, because the user
    approved that wording; the headshot is a contact field behind a switch, and
    someone who flips that switch expects the next preview and the next download to
    follow, not to have to regenerate the draft first.
    """
    return set_header_photo(sections, photo_data_uri(photo, locale=locale))


def photo_data_uri(photo: ProfilePhoto | None, *, locale: str | None = None) -> str | None:
    """Fetch the stored headshot and return it as a `data:` URI, or `None`.

    `locale` is required by every real caller even though it is keyword-optional:
    whether a headshot belongs on the page is a property of the output track, not
    of the upload (`ProfilePhoto.renders_for_locale`). It defaults to `None`, which
    normalises to the Chinese track, so an older caller keeps today's behaviour
    rather than silently losing the photo.

    Export renders **must** inline the bytes rather than reference the signed URL.
    `ResumeRenderEngine.render_pdf` installs `page.route("**/*", route.abort())`
    before setting content, so every outbound request from the print page is
    refused -- a remote `<img src>` would silently produce a resume with a blank
    box where the face should be. The HTML export has a second, independent reason:
    it is advertised as a self-contained single file that "opens correctly from
    mail, disk or a personal site", which a short-lived signed URL would break a
    few minutes after download.

    Returns `None` on any failure (not renderable, object missing, storage down) so
    an export never fails over a decorative element. The template treats `None` as
    "no photo", which is also the default state, so the page stays correct.
    """
    if photo is None or not photo.storage_key:
        return None
    if not photo.renders_for_locale(locale):
        return None
    try:
        raw = get_storage_backend().get_object_bytes(photo.storage_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "profile photo fetch for render failed",
            extra={
                "storage_key": photo.storage_key,
                "error_type": type(exc).__name__,
            },
        )
        return None
    if not raw:
        return None
    import base64

    mime = photo.mime_type or _OUTPUT_MIME
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
