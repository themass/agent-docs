from __future__ import annotations

from pathlib import Path

import pytest
from agent_worker.config import load_settings

ENV = ("PORT", "POETRY_AGENT_PROFILE_ROOT", "POETRY_DOMAIN_CONTROL_URL", "POETRY_DOMAIN_CONTROL_TOKEN",
       "POETRY_WORKER_TOKEN", "DEERFLOW_ENABLED", "DEERFLOW_GATEWAY_URL", "DEERFLOW_GATEWAY_TOKEN",
       "DEERFLOW_ASSISTANT_ID", "DEERFLOW_AUTH_MODE", "DEERFLOW_OWNER_USER_ID", "DEERFLOW_FALLBACK_MODEL",
       "WORKER_MAX_CONCURRENT_RUNS", "WORKER_QUEUE_LIMIT")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV:
        monkeypatch.delenv(name, raising=False)


def test_defaults_are_conservative() -> None:
    s = load_settings()
    assert (s.port, s.max_concurrent_runs, s.deerflow_enabled) == (8102, 2, False)
    assert s.deerflow_assistant_id == "poetry-editor-lead" and s.deerflow_auth_mode == "auto"
    assert s.deerflow_owner_user_id == "poetry-authoring" and s.deerflow_fallback_model == ""
    assert s.control_url == "" and s.worker_token == "" and s.control_token == ""


def test_environment_is_read_and_clamped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("POETRY_AGENT_PROFILE_ROOT", str(tmp_path))
    monkeypatch.setenv("POETRY_DOMAIN_CONTROL_URL", "http://bridge:8101/")
    monkeypatch.setenv("DEERFLOW_ENABLED", "TRUE")
    monkeypatch.setenv("DEERFLOW_GATEWAY_URL", "http://gw:8001/")
    monkeypatch.setenv("WORKER_MAX_CONCURRENT_RUNS", "500")
    monkeypatch.setenv("DEERFLOW_FALLBACK_MODEL", " poetry-fallback ")
    s = load_settings()
    assert s.port == 9000 and s.control_url == "http://bridge:8101" and s.deerflow_url == "http://gw:8001"
    assert s.deerflow_enabled and s.max_concurrent_runs == 16 and s.deerflow_fallback_model == "poetry-fallback"
    assert s.budgets_path == tmp_path / "config" / "budgets.yaml"
    monkeypatch.setenv("WORKER_MAX_CONCURRENT_RUNS", "abc")
    monkeypatch.setenv("PORT", "-5")
    s = load_settings()
    assert s.max_concurrent_runs == 2 and s.port == 1


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off"])
def test_deerflow_is_only_enabled_explicitly(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("DEERFLOW_ENABLED", value)
    assert load_settings().deerflow_enabled is False


def test_public_view_never_contains_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POETRY_WORKER_TOKEN", "w-secret")
    monkeypatch.setenv("POETRY_DOMAIN_CONTROL_TOKEN", "c-secret")
    monkeypatch.setenv("DEERFLOW_GATEWAY_TOKEN", "g-secret")
    text = str(load_settings().public())
    assert "secret" not in text and "worker_token_configured" in text
