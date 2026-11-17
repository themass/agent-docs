"""Scene registry for direct uploads (ADR-011 §4).

One place where "what may be uploaded, how big, under which content types"
is answered. sign validates against it; bind re-checks the byte count against
the same cap it signed for, so a scene cap cannot drift between the two ends.

Caps are ceilings on RAW bytes, not on what the client was told to compress
to: the client-side profiles (ADR-011 §5) target well below these, the scene
cap is the reject line for everything else.
"""

from __future__ import annotations

from dataclasses import dataclass

from jc.exceptions import AppError


class MediaSceneError(AppError):
    """Unknown scene or content type outside the scene's whitelist."""

    def __init__(self, message: str, *, code: str = "invalid_media_request") -> None:
        super().__init__(message, code=code)


@dataclass(frozen=True, slots=True)
class MediaScene:
    name: str
    max_bytes: int
    #: Explicit whitelist, not a prefix rule — `image/svg+xml` must not ride in
    # on an `image/` prefix (it is script-bearing).
    content_types: frozenset[str]


MB = 1024 * 1024

#: Extension is derived from the whitelisted contentType, never from the
# client's file name — the key must not carry user-supplied path segments.
_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic"})
_AUDIO_TYPES = frozenset(
    {"audio/webm", "audio/ogg", "audio/opus", "audio/mp4", "audio/aac", "audio/mpeg", "audio/wav"}
)
_DOC_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "text/plain",
    }
)

_EXT_BY_MIME = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/heic": "heic",
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/opus": "ogg",
    "audio/mp4": "m4a",
    "audio/aac": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
    "text/plain": "txt",
}

SCENES: dict[str, MediaScene] = {
    # 8 MB is today's inline ceiling; ADR-011 §4 lowers to 2 MB only after the
    # new path is observed, so exactly one variable changes at a time.
    "chat-image": MediaScene("chat-image", 8 * MB, _IMAGE_TYPES),
    "chat-audio": MediaScene("chat-audio", 8 * MB, _AUDIO_TYPES),
    # profile-source covers both document resumes and photo resumes; documents
    # are never compressed, photos get the OCR profile before they are signed.
    "profile-source": MediaScene("profile-source", 15 * MB, _IMAGE_TYPES | _DOC_TYPES),
}


def resolve_scene(name: str) -> MediaScene:
    try:
        return SCENES[name]
    except KeyError:
        allowed = ", ".join(sorted(SCENES))
        raise MediaSceneError(
            f"不支持的上传场景 {name!r}，可用场景：{allowed}。",
            code="invalid_scene",
        ) from None


def extension_for(content_type: str) -> str:
    try:
        return _EXT_BY_MIME[content_type]
    except KeyError:
        raise MediaSceneError("不支持的文件类型。", code="unsupported_content_type") from None
