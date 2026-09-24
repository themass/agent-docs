"""Tests for LiteLLM / Langfuse bootstrap."""

from jobcome.llm.bootstrap import (
    _langfuse_legacy_sdk_compatible,
    _patch_langfuse_version_shim,
    _strip_legacy_langfuse_callbacks,
    configure_litellm,
)
from jobcome.observability.langfuse_setup import LANGFUSE_OTEL_CALLBACK, setup_langfuse_callbacks


def test_langfuse_version_shim_for_litellm() -> None:
    _patch_langfuse_version_shim()
    import langfuse

    assert hasattr(langfuse, "version")
    assert langfuse.version.__version__


def test_configure_litellm_sets_drop_params() -> None:
    configure_litellm()
    import litellm

    assert litellm.drop_params is True


def test_strip_legacy_langfuse_callbacks_keeps_otel() -> None:
    import litellm

    litellm.success_callback = ["langfuse", LANGFUSE_OTEL_CALLBACK, "other"]
    _strip_legacy_langfuse_callbacks()
    assert "langfuse" not in (litellm.success_callback or [])
    assert LANGFUSE_OTEL_CALLBACK in (litellm.success_callback or [])


def test_langfuse_legacy_compat_probe_is_bool() -> None:
    assert isinstance(_langfuse_legacy_sdk_compatible(), bool)


def test_setup_langfuse_callbacks_uses_otel(monkeypatch) -> None:
    import litellm

    from jobcome.config import settings

    monkeypatch.setattr(settings, "langfuse_public_key", "pk-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-test")
    litellm.success_callback = []
    litellm.failure_callback = []
    # Reset module guard so setup runs again.
    import jobcome.observability.langfuse_setup as mod

    mod._CONFIGURED = False
    assert setup_langfuse_callbacks() is True
    assert LANGFUSE_OTEL_CALLBACK in (litellm.success_callback or [])
    assert LANGFUSE_OTEL_CALLBACK in (litellm.failure_callback or [])
