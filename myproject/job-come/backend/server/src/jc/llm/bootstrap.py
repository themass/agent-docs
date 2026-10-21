"""LiteLLM global configuration."""

from __future__ import annotations

import inspect
import logging
import os
import types

from jc.config import settings

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


def sync_llm_gateway_env() -> None:
    """Publish gateway credentials to os.environ for routing.yaml and DeerFlow YAML ($JC_LLM_*)."""
    text_base = settings.jc_llm_api_base
    text_key = settings.jc_llm_api_key
    vision_base = settings.jc_llm_vision_api_base or text_base
    vision_key = settings.jc_llm_vision_api_key or text_key
    for name, value in {
        "JC_LLM_API_BASE": text_base,
        "JC_LLM_API_KEY": text_key,
        "JC_LLM_VISION_API_BASE": vision_base,
        "JC_LLM_VISION_API_KEY": vision_key,
    }.items():
        if value:
            os.environ.setdefault(name, value)


def configure_litellm() -> None:
    """Apply process-wide LiteLLM defaults once at startup."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    from jc.llm.router import ensure_dotenv_loaded

    ensure_dotenv_loaded()
    sync_llm_gateway_env()
    # LiteLLM otherwise downloads its model-cost map while importing.  JC has no
    # general network capability, so always use LiteLLM's packaged backup map.
    # Operators may set this before startup only when they explicitly permit it.
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "true")
    import litellm

    litellm.drop_params = True
    if not _langfuse_legacy_sdk_compatible():
        _strip_legacy_langfuse_callbacks()
    # Audit is an observer on litellm, so it must be attached before the first
    # call. Both the deterministic services and the DeerFlow adapter go through
    # litellm, which is what lets one callback cover both paths.
    from jc.llm.audit_hook import register_audit_callback

    register_audit_callback()
    _CONFIGURED = True
