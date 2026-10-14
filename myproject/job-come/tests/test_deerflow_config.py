"""DeerFlow harness config smoke tests."""

import os
from pathlib import Path


def test_deerflow_config_loads(monkeypatch) -> None:
    monkeypatch.setenv("YUAI_API_BASE", "https://example.invalid/v1")
    monkeypatch.setenv("YUAI_API_KEY", "test-key")
    monkeypatch.setenv("JOB_COME_SUMMARIZATION_TRIGGER_TOKENS", "32000")
    monkeypatch.setenv("JOB_COME_SUMMARIZATION_KEEP_MESSAGES", "6")
    root = Path(__file__).resolve().parents[1]
    config_path = root / "deploy" / "deerflow" / "config.yaml"
    from deerflow.config.app_config import AppConfig

    cfg = AppConfig.from_file(str(config_path))
    assert cfg.sandbox is not None
    assert cfg.subagents.max_total_per_run >= 1
