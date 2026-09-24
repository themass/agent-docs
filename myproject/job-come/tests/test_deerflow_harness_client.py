"""DeerFlow harness adapter — JobCome non-interactive defaults."""

from __future__ import annotations

from unittest.mock import patch

from langchain_core.runnables import RunnableConfig

from jobcome.adapters.deerflow_harness_client import _jobcome_deerflow_client_class


def test_jobcome_client_sets_non_interactive() -> None:
    class FakeDeerFlowClient:
        def _get_runnable_config(self, thread_id: str, **overrides):  # noqa: ANN001
            return RunnableConfig(configurable={"thread_id": thread_id})

    with patch("deerflow.client.DeerFlowClient", FakeDeerFlowClient):
        client_cls = _jobcome_deerflow_client_class()
        client = client_cls.__new__(client_cls)
        runnable = client._get_runnable_config("thr_test")
        assert runnable["configurable"]["non_interactive"] is True
