"""Agent chat reply language (product UI stays Chinese; this is model output)."""

from __future__ import annotations

DEFAULT_REPLY_LOCALE = "zh-CN"


def normalize_reply_locale(locale: str | None) -> str:
    raw = (locale or DEFAULT_REPLY_LOCALE).strip().lower().replace("_", "-")
    if raw.startswith("en"):
        return "en-US"
    return DEFAULT_REPLY_LOCALE


def reply_language_instruction(locale: str | None) -> str:
    if normalize_reply_locale(locale) == "en-US":
        return (
            "You MUST reply in English only. Do not mix Chinese except when quoting "
            "resume or JD text the user provided."
        )
    return (
        "你必须全程使用简体中文回复。禁止中英夹杂成段，禁止用英文自我介绍或英文错误套话。"
        "公司名、产品名、技术栈可保留英文原文。"
    )
