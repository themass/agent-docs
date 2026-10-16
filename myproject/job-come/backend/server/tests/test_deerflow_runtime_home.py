"""JC must isolate DeerFlow generated state from legacy project-root caches."""

from __future__ import annotations

import os
from pathlib import Path

from agentkit.adapters.deerflow.client import DeerFlowClientConfig

from jc.adapters.deerflow_harness_client import _configure_deerflow_paths
from jc.config import settings


def test_deerflow_runtime_home_is_jc_data_directory(monkeypatch) -> None:
    monkeypatch.setenv("DEER_FLOW_HOME", "/tmp/untrusted-deerflow-home")
    monkeypatch.setenv("DEER_FLOW_PROJECT_ROOT", "/tmp/untrusted-project-root")

    _configure_deerflow_paths(
        DeerFlowClientConfig(
            extensions_config_path=settings.jc_deerflow_extensions_config,
            checkpoint_backend=settings.jc_deerflow_checkpoint_backend,
            checkpoint_sqlite_path=settings.jc_deerflow_checkpoint_sqlite_path,
            checkpoint_postgres_url=settings.jc_deerflow_checkpoint_postgres_url,
        )
    )

    root = Path(__file__).resolve().parents[1]
    assert Path(os.environ["DEER_FLOW_PROJECT_ROOT"]) == root
    assert Path(os.environ["DEER_FLOW_HOME"]) == (
        root / ".data" / "deerflow" / "runtime"
    )
