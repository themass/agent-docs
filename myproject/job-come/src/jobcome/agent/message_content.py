"""Build LLM user messages with optional multimodal attachments."""

from __future__ import annotations

from typing import Any

from jobcome.config import settings
from jobcome.schemas.agent import AgentAttachment


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
            image_parts.append(
                {"type": "image_url", "image_url": {"url": att.data_url}},
            )
        elif att.text_preview:
            file_parts.append(f"[File: {att.name}]\n{att.text_preview[:4000]}")
        elif att.kind == "image":
            file_parts.append(f"[Image: {att.label or att.name}]")
        elif att.kind == "audio":
            file_parts.append(f"[Voice message: {att.label or att.name}]")
        else:
            file_parts.append(f"[File: {att.name}]")

    if file_parts:
        text = "\n\n".join([text] + file_parts) if text else "\n\n".join(file_parts)

    if not image_parts:
        return text or "(empty)"

    parts: list[dict[str, Any]] = [
        {"type": "text", "text": text or "请结合附图回答。"},
    ]
    parts.extend(image_parts)
    return parts


def message_has_images(message_content: str | list[dict[str, Any]]) -> bool:
    if isinstance(message_content, list):
        return any(p.get("type") == "image_url" for p in message_content)
    return False


async def flatten_message_for_text_agent(
    content: str,
    attachments: list[AgentAttachment],
) -> str:
    """Vision OCR fallback for harness / text-only backends."""
    built = build_user_message_content(content, attachments)
    if isinstance(built, str):
        return built

    if not settings.job_come_llm_enabled:
        return content or "(image attached)"

    from jobcome.llm.router import get_llm_router

    router = get_llm_router()
    extracts: list[str] = []
    for att in attachments:
        if att.kind != "image" or not att.data_url:
            continue
        try:
            response = await router.acompletion(
                "vision",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"Describe this image ({att.name}) for a job coaching agent. "
                                    "Include visible text, layout, and key facts."
                                ),
                            },
                            {"type": "image_url", "image_url": {"url": att.data_url}},
                        ],
                    }
                ],
                temperature=0.1,
            )
            extracts.append(f"[Image {att.name}]\n{router.content_from_response(response)}")
        except Exception as exc:  # noqa: BLE001
            extracts.append(f"[Image {att.name}] (vision unavailable: {exc})")

    text = content.strip()
    if extracts:
        block = "\n\n".join(extracts)
        return f"{text}\n\n{block}".strip() if text else block
    return text or "(empty)"
