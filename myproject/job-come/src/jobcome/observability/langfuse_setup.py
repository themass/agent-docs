"""Langfuse + LiteLLM observability bootstrap."""

from __future__ import annotations

import logging
import os

from jobcome.config import settings
from jobcome.llm.bootstrap import _langfuse_legacy_sdk_compatible, _strip_legacy_langfuse_callbacks

logger = logging.getLogger(__name__)
_CONFIGURED = False

# LiteLLM callback for Langfuse Cloud v4+ (OTLP, no legacy SDK v2 API).
LANGFUSE_OTEL_CALLBACK = "langfuse_otel"


def setup_langfuse_callbacks() -> bool:
    """Register LiteLLM Langfuse OTel callbacks when keys are present."""
    global _CONFIGURED
    if _CONFIGURED:
        return True
    public = settings.langfuse_public_key
    secret = settings.langfuse_secret_key
    if not public or not secret:
        return False

    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", public)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", secret)
    if settings.langfuse_host:
        os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)

    try:
        import litellm

        # Legacy `langfuse` callback breaks with langfuse SDK 4.x; always prefer OTel.
        if not _langfuse_legacy_sdk_compatible():
            _strip_legacy_langfuse_callbacks()
            logger.info(
                "Legacy LiteLLM langfuse callback removed (SDK 4.x); using langfuse_otel instead."
            )

        success = list(litellm.success_callback or [])
        failure = list(litellm.failure_callback or [])
        if LANGFUSE_OTEL_CALLBACK not in success:
            success.append(LANGFUSE_OTEL_CALLBACK)
        if LANGFUSE_OTEL_CALLBACK not in failure:
            failure.append(LANGFUSE_OTEL_CALLBACK)
        litellm.success_callback = success
        litellm.failure_callback = failure
        _CONFIGURED = True
        logger.info("Langfuse OTel callbacks enabled for LiteLLM (%s)", settings.langfuse_host)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Langfuse setup failed: %s", exc)
        return False
