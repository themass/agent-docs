"""DeerFlow harness client factory — single runtime, no fallback."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from agentkit.adapters.deerflow.client import DeerFlowClientConfig, DeerFlowSessionClient

from jobcome.adapters.deerflow_harness_client import DeerFlowHarnessSessionClient
from jobcome.config import settings


def _client_config() -> DeerFlowClientConfig:
    return DeerFlowClientConfig(
        extensions_config_path=settings.job_come_deerflow_extensions_config,
        checkpoint_backend=settings.job_come_deerflow_checkpoint_backend,
        checkpoint_sqlite_path=settings.job_come_deerflow_checkpoint_sqlite_path,
        checkpoint_postgres_url=settings.job_come_deerflow_checkpoint_postgres_url,
    )


def get_deerflow_client(db: AsyncSession | None = None) -> DeerFlowSessionClient:
    client = DeerFlowHarnessSessionClient(_client_config())
    if db is not None:
        client.bind_db(db)
    return client
