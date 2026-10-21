"""Turn a chat message plus its attachments into something a model can read.

Two consumers with different capabilities, which is why there are two functions:
`build_user_message_content` keeps images as native multimodal parts for a
vision-capable model, while `flatten_message_for_text_agent` transcribes them first
for the DeerFlow harness, whose chat model is text-only.

The wire format itself is not decided here — `jc.llm.vision` owns it.
"""

from __future__ import annotations

import re
from typing import Any

from jc.config import settings
from jc.llm.vision import ImageRef, content_has_images, describe_image, image_part, text_part
from jc.schemas.agent import AgentAttachment


def _image_ref(att: AgentAttachment) -> ImageRef:
    """A chat attachment already arrives as a browser `data:` URL."""
    return ImageRef.from_data_url(att.data_url or "", label=att.label or att.name)


#: What a voice clip with no words looks like. There is no server-side STT in this
#: version, so an unrecognized clip is genuinely unreadable; saying so lets the agent
#: ask the user to type the key points instead of answering a message it never heard.
AUDIO_UNREADABLE_SUFFIX = (
    "(no transcript available — this version cannot read audio; "
    "ask the user to type the key points)"
)


def audio_text_part(att: AgentAttachment, *, existing_text: str) -> str | None:
    """The line to add for a voice clip, or `None` when nothing needs adding.

    The browser does the speech-to-text and appends the words into the composer, so by
    the time a turn arrives the transcript is normally *already* the message text. Adding
    it again put the user's sentence in the prompt twice and in the stored row twice —
    which reads as the user repeating themselves and inflates every token count on the
    voice path.

    It is still added when the words are absent from the text, because the user can edit
    or clear the box after dictating, and then the clip is the only record of what they
    said.
    """
    said = (att.transcript or "").strip()
    if said:
        return None if said in existing_text else f"[语音转文字] {said}"
    return f"[Voice message: {att.label or att.name}] {AUDIO_UNREADABLE_SUFFIX}"


def build_user_message_content(
    content: str,
    attachments: list[AgentAttachment],
) -> str | list[dict[str, Any]]:
    """Return plain text or OpenAI-style multimodal content parts."""
    text = content.strip()
    file_parts: list[str] = []
    image_parts: list[dict[str, Any]] = []

    for att in attachments:
        if att.kind == "image" and att.data_url:
            image_parts.append(image_part(_image_ref(att)))
        elif att.text_preview:
            file_parts.append(f"[File: {att.name}]\n{att.text_preview[:4000]}")
        elif att.kind == "image":
            file_parts.append(f"[Image: {att.label or att.name}]")
        elif att.kind == "audio":
            spoken = audio_text_part(att, existing_text=text)
            if spoken:
                file_parts.append(spoken)
        else:
            file_parts.append(f"[File: {att.name}]")

    if file_parts:
        text = "\n\n".join([text] + file_parts) if text else "\n\n".join(file_parts)

    if not image_parts:
        return text or "(empty)"

    parts: list[dict[str, Any]] = [
        text_part(text or "请结合附图回答。"),
    ]
    parts.extend(image_parts)
    return parts


def message_has_images(message_content: str | list[dict[str, Any]]) -> bool:
    return content_has_images(message_content)


_PHOTO_INTENT = re.compile(
    r"头像|证件照|简历照|简历照片|设为.*照|设置为.*照|设成.*照|上传.*照",
    re.IGNORECASE,
)


def should_skip_vision_for_photo_tool(content: str, attachments: list[AgentAttachment]) -> bool:
    """Avatar turns use `jc_profile_photo_set` on the raw attachment — OCR is wasted latency."""
    text = content.strip()
    if not text or not attachments:
        return False
    if not all(att.kind == "image" for att in attachments):
        return False
    return bool(_PHOTO_INTENT.search(text))


async def flatten_message_for_text_agent(
    content: str,
    attachments: list[AgentAttachment],
) -> str:
    """Vision OCR fallback for harness / text-only backends."""
    built = build_user_message_content(content, attachments)
    if isinstance(built, str):
        return built

    if should_skip_vision_for_photo_tool(content, attachments):
        names = ", ".join(att.label or att.name or "image" for att in attachments)
        hint = (
            f"[Image attached: {names}. User asked to set this as the resume photo. "
            "Call jc_profile_photo_set with attachment_index; do not claim it is saved "
            "until the user finishes cropping in the UI.]"
        )
        text = content.strip()
        return f"{text}\n\n{hint}".strip() if text else hint

    if not settings.jc_llm_enabled:
        return content or "(image attached)"

    extracts: list[str] = []
    for att in attachments:
        if att.kind != "image" or not att.data_url:
            continue
        try:
            described = await describe_image(
                _image_ref(att),
                purpose=(
                    f"Describe this image ({att.name}) for a job coaching agent. "
                    "Include visible text, layout, and key facts."
                ),
            )
            extracts.append(f"[Image {att.name}]\n{described}")
        except Exception as exc:  # noqa: BLE001
            # One unreadable attachment must not cost the user their whole message:
            # the agent is told the image could not be read and answers the rest.
            extracts.append(f"[Image {att.name}] (vision unavailable: {exc})")

    text = content.strip()
    if extracts:
        block = "\n\n".join(extracts)
        return f"{text}\n\n{block}".strip() if text else block
    return text or "(empty)"
