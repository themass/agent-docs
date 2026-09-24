"""LiteLLM global configuration."""

from __future__ import annotations

import inspect
import logging
import types

logger = logging.getLogger(__name__)

_CONFIGURED = False


def _patch_langfuse_version_shim() -> None:
    """LiteLLM legacy callback expects langfuse.version; langfuse 4.x exposes _version only."""
    try:
        import langfuse
    except ImportError:
        return
    if hasattr(langfuse, "version"):
        return
    try:
        from langfuse._version import __version__ as langfuse_version
    except Exception:  # noqa: BLE001
        return
    langfuse.version = types.SimpleNamespace(__version__=langfuse_version)


def _langfuse_legacy_sdk_compatible() -> bool:
    """Return True only when litellm's legacy `langfuse` SDK callback can init."""
    _patch_langfuse_version_shim()
    try:
        from langfuse import Langfuse

        params = inspect.signature(Langfuse.__init__).parameters
        # litellm 1.99 legacy callback passes sdk_integration; langfuse 4.x removed it.
        return "sdk_integration" in params
    except Exception:  # noqa: BLE001
        return False


def _strip_legacy_langfuse_callbacks() -> None:
    """Remove legacy `langfuse` callback only; keep `langfuse_otel`."""
    import litellm

    for attr in ("success_callback", "failure_callback", "callbacks"):
        current = getattr(litellm, attr, None)
        if not current:
            continue
        if isinstance(current, list):
            filtered = [item for item in current if item != "langfuse"]
            setattr(litellm, attr, filtered)
        elif current == "langfuse":
            setattr(litellm, attr, [])


def configure_litellm() -> None:
    """Apply process-wide LiteLLM defaults once at startup."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    import litellm

    litellm.drop_params = True
    if not _langfuse_legacy_sdk_compatible():
        _strip_legacy_langfuse_callbacks()
    _CONFIGURED = True
