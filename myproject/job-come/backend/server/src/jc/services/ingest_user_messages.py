"""User-visible ingest messages — no vendor/model/stack traces (those go to logs)."""

USER_LLM_PARSE_UNAVAILABLE = (
    "智能解析暂时不可用，已为您生成可编辑草稿。请核对内容并补充经历，或稍后重新上传。"
)

USER_LLM_DISABLED = "当前未开启智能解析，已生成占位草稿，请手动填写或完善简历信息。"

USER_PARSE_INCOMPLETE = "解析结果可能不完整，请核对下方经历与要点，或请舟卡帮您补全。"

USER_UPLOAD_PARSE_FAILED = "简历处理失败，请稍后重试；若问题持续请联系支持。"

USER_DOC_LEGACY_FORMAT = (
    "当前不支持旧版 .doc 格式，请在 Word 中「另存为」.docx 后重新上传。"
)

_KNOWN_MESSAGES = frozenset(
    {
        USER_LLM_PARSE_UNAVAILABLE,
        USER_LLM_DISABLED,
        USER_PARSE_INCOMPLETE,
        USER_UPLOAD_PARSE_FAILED,
        USER_DOC_LEGACY_FORMAT,
    }
)

_TECHNICAL_MARKERS = (
    "litellm",
    "openaiexception",
    "serviceunavailable",
    "all models failed",
    "request id",
    "yuai_",
    "jc_llm_api",
    "详情：",
    "ingest_fast",
    "distributor",
    "openai/",
    "无可用渠道",
)


def public_parse_error(raw: str | None, *, ingest_mode: str | None = None) -> str | None:
    """Strip legacy/technical parse_error text before sending to clients."""
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    if text in _KNOWN_MESSAGES:
        return text
    lowered = text.lower()
    if any(marker in lowered for marker in _TECHNICAL_MARKERS):
        if ingest_mode in {"mock_fallback", "mock_no_text"}:
            return USER_LLM_PARSE_UNAVAILABLE
        return USER_PARSE_INCOMPLETE
    if len(text) > 160:
        return USER_PARSE_INCOMPLETE
    return text
