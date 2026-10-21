"""Shared fixtures for tests that exercise a real `litellm.Router`.

Why a fake gateway and not a fake litellm
-----------------------------------------
These tests used to replace the whole ``litellm`` module with a
``SimpleNamespace(acompletion=...)``. That made them pass while testing nothing
of what JC now relies on: the failover chain, the cooldown state, and the
post-call rule that turns an unusable 200 into a failed attempt all live inside
``litellm.Router``. A stub router has none of them, so the chain order, the
number of attempts, and the audit row would all have been the test's own
invention.

So the seam moves one level down. The real ``Router`` is built from a real
``routing.yaml``, and only the outermost HTTP call is faked - through litellm's
own ``mock_response``, which still runs the full wrapper: provider resolution,
post-call rules, failure callbacks, usage accounting.
"""

from __future__ import annotations

import os

os.environ.setdefault("JC_BOOTSTRAP_SKIP_REEXEC", "1")
# `test_evaluate_writing_script.py` loads `scripts/evaluate_writing.py` by path at
# *collection* time (module-level `ew = _load()`), and that script's first import is
# `lib.bootstrap.ensure_project_env()`, which calls `os.execv` to re-exec under the
# monorepo venv's interpreter whenever the running interpreter is not already it (see
# that module's docstring). Collection happens inside pytest's own process, so an
# unguarded `execv` there replaces the *pytest process itself* with the re-exec'd
# script — which hangs or exits on its own, silently eating whatever else pytest was
# about to run with zero output and no error. Setting this before any test module
# imports anything makes `ensure_project_env()` a no-op for the whole suite,
# regardless of which interpreter invoked pytest; a developer or CI job running the
# full `tests/` directory should never have the collector's own process replaced out
# from under it.

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def _never_read_the_developers_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must not inherit real credentials from `backend/server/.env`.

    `ensure_dotenv_loaded()` loads that file with `override=False`, so a test that
    does `monkeypatch.delenv("JC_LLM_API_KEY")` to assert "this endpoint is not
    configured" had the key put straight back by the next router call. The assertion
    then held or failed depending on whether the machine running the suite happened to
    have a gateway configured — green on CI, red on a developer box, and a test that
    proves nothing either way.

    This is also why the defect it masked lived so long: the dotenv path was computed
    one directory too shallow, so the file was never found and these tests passed for
    the wrong reason.
    """
    monkeypatch.setattr("jc.llm.router.ensure_dotenv_loaded", lambda: None)


@pytest.fixture(autouse=True)
def _isolate_router_cache() -> Iterator[None]:
    """Routers are cached per scenario, so a test's chain must not outlive it."""
    from jc.llm import transport

    transport.clear_router_cache()
    yield
    transport.clear_router_cache()


def write_routing(path: Path, scenario: str, models: list[str], *, providers: str = "") -> Path:
    """A minimal `routing.yaml` with one scenario and the given chain."""
    entries = "".join(f"    - model: {model}\n" for model in models)
    path.write_text(f"{providers}scenarios:\n  {scenario}:\n{entries}", encoding="utf-8")
    return path


def install_routing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, scenario: str, models: list[str]
) -> Any:
    """Make `scenario` resolvable, and hand back JC's own router for it."""
    from jc.llm.router import LLMRouter

    monkeypatch.setenv("JC_LLM_API_KEY", "test-key")
    monkeypatch.setenv("JC_LLM_API_BASE", "https://gateway.invalid/v1")
    jc_router = LLMRouter(write_routing(tmp_path / "routing.yaml", scenario, models))
    monkeypatch.setattr("jc.llm.router.get_llm_router", lambda: jc_router)
    return jc_router


@contextmanager
def fake_gateway(answers: dict[str, Any], default: Any = "default answer") -> Iterator[list[str]]:
    """Answer each model from `answers`, through litellm's own call path.

    A value may be a string (the assistant text) or an exception instance (the
    gateway failing). Keys are matched as suffixes so callers can write
    ``"first"`` for ``openai/first``.
    """
    import litellm

    called: list[str] = []
    real_acompletion = litellm.acompletion
    real_completion = litellm.completion

    def answer_for(model: str) -> Any:
        called.append(model)
        for key, value in answers.items():
            if model.endswith(key):
                return value
        return default

    async def acompletion(**kwargs: Any) -> Any:
        kwargs["mock_response"] = answer_for(str(kwargs.get("model", "")))
        return await real_acompletion(**kwargs)

    def completion(**kwargs: Any) -> Any:
        kwargs["mock_response"] = answer_for(str(kwargs.get("model", "")))
        return real_completion(**kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(litellm, "acompletion", acompletion)
        patch.setattr(litellm, "completion", completion)
        yield called


@contextmanager
def capture_audit_rows() -> Iterator[list[Any]]:
    """Collect audit rows instead of writing them, for both scope flavours.

    The async scope awaits `record_call`; the sync scope (the harness path) hands
    its row to the ambient sink. Both are redirected here so a test does not
    have to know which one the code under test used.
    """
    import litellm

    from jc.llm import audit_hook

    rows: list[Any] = []

    async def record(record_obj: Any) -> str:
        rows.append(record_obj)
        return "llmc_test"

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(audit_hook, "record_call", record)
        patch.setattr(audit_hook, "_registered", False)
        patch.setattr(litellm, "callbacks", [])
        # Forced on: `register_audit_callback` is a no-op when logging is
        # disabled, so without this a deployment setting in the ambient
        # environment would silently turn these assertions into no-ops.
        patch.setattr(audit_hook_settings(), "jc_llm_log_enabled", True)
        assert audit_hook.register_audit_callback() is True
        try:
            with audit_hook.audit_sink(rows.append):
                yield rows
        finally:
            audit_hook._registered = False


async def settle_callbacks(seconds: float = 1.0) -> None:
    """Wait for litellm's background logging worker to drain.

    litellm enqueues its success events onto a worker thread, so a row that is
    only complete once a callback has run is not readable the instant the call
    returns. JC does not depend on those events for success - the caller reports
    it - but a test asserting on failure attempts of a *recovered* chain can
    still race the last enqueued event.
    """
    import asyncio

    await asyncio.sleep(seconds)


def audit_hook_settings() -> Any:
    """The settings object `register_audit_callback` reads."""
    from jc.config import settings

    return settings


def gateway_error(kind: str, model: str = "openai/first") -> Exception:
    """A gateway failure of the given kind, as litellm would raise it."""
    import litellm

    if kind == "timeout":
        return litellm.exceptions.Timeout("timed out", model, "openai")
    if kind == "rate_limited":
        return litellm.exceptions.RateLimitError("429 Too Many Requests", "openai", model)
    if kind == "auth":
        return litellm.exceptions.AuthenticationError("401 unauthorized", "openai", model)
    return litellm.exceptions.InternalServerError("upstream exploded", model, "openai")


__all__ = [
    "audit_hook_settings",
    "capture_audit_rows",
    "fake_gateway",
    "gateway_error",
    "install_routing",
    "settle_callbacks",
    "write_routing",
]
