"""Multimodal input: one way to put an image in front of a model.

Before this, the OpenAI multimodal content format was hand-assembled in two places —
resume OCR (`jc.services.profile_vision`) and agent chat attachments
(`jc.agent.message_content`) — each with its own base64 handling and its own vision
call. Two copies of a wire format is a bug waiting for the day one of them is fixed.

The split of responsibility here:

- `ImageRef` is the single way an image enters the system, whether it arrived as raw
  bytes from an upload or as a browser `data:` URL from a chat attachment.
- `image_part` / `build_vision_content` own the wire format.
- `describe_image` is the one-image-to-text path used when a downstream agent is
  text-only.

Routing, retries, failover and audit are *not* here. They belong to `LLMRouter` and
the `vision` scenario in `routing.yaml`, and this module calls through it like every
other model user. The only thing this owns is the shape of a multimodal message.
"""

from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ImageRef:
    """An image ready to be sent to a model, as a URL the provider accepts.

    Raw bytes become a `data:` URL at construction rather than at send time, so the
    encoding exists in exactly one place and callers cannot forget the mime type.
    """

    url: str
    label: str | None = None

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
        *,
        mime: str | None = None,
        file_name: str | None = None,
        label: str | None = None,
    ) -> ImageRef:
        resolved = mime
        if not resolved and file_name:
            resolved = mimetypes.guess_type(file_name)[0]
        resolved = resolved or "image/png"
        encoded = base64.standard_b64encode(raw).decode("ascii")
        return cls(url=f"data:{resolved};base64,{encoded}", label=label or file_name)

    @classmethod
    def from_data_url(cls, data_url: str, *, label: str | None = None) -> ImageRef:
        return cls(url=data_url, label=label)


def image_part(image: ImageRef) -> dict[str, Any]:
    """One OpenAI-style image content part."""
    return {"type": "image_url", "image_url": {"url": image.url}}


def text_part(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def build_vision_content(
    *,
    intro: str,
    images: list[ImageRef],
    part_labels: bool = False,
) -> list[dict[str, Any]]:
    """Interleave an instruction with images as multimodal content parts.

    `part_labels` inserts `--- Part n ---` before each image. That matters for
    multi-page documents: without it a model reading a 3-page resume has no way to
    say which page a field came from, and merges them in the wrong order.
    """
    content: list[dict[str, Any]] = [text_part(intro)]
    for idx, image in enumerate(images, start=1):
        if part_labels:
            content.append(text_part(f"--- Part {idx} ---"))
        content.append(image_part(image))
    return content


def content_has_images(message_content: str | list[dict[str, Any]]) -> bool:
    if isinstance(message_content, list):
        return any(part.get("type") == "image_url" for part in message_content)
    return False


async def describe_image(image: ImageRef, *, purpose: str) -> str:
    """Transcribe one image to text for a text-only consumer.

    Deliberately one call per image: a failed page then degrades to a note about
    that page instead of losing the whole batch, which is what a single
    all-images-at-once call would do.
    """
    from jc.llm.call_context import llm_context
    from jc.llm.router import get_llm_router

    router = get_llm_router()
    response = await router.acompletion(
        "vision",
        log_context=llm_context("agent_message_vision"),
        messages=[
            {
                "role": "user",
                "content": build_vision_content(intro=purpose, images=[image]),
            }
        ],
        temperature=0.1,
    )
    return router.content_from_response(response)
