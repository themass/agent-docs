"""DeerFlow harness client factory — single runtime, no fallback."""

from __future__ import annotations

from agentkit.adapters.deerflow.client import DeerFlowClientConfig, DeerFlowSessionClient
from sqlalchemy.ext.asyncio import AsyncSession

from jc.adapters.deerflow_harness_client import DeerFlowHarnessSessionClient
from jc.config import settings


def _client_config() -> DeerFlowClientConfig:
    return DeerFlowClientConfig(
        extensions_config_path=settings.jc_deerflow_extensions_config,
        checkpoint_backend=settings.jc_deerflow_checkpoint_backend,
        checkpoint_sqlite_path=settings.jc_deerflow_checkpoint_sqlite_path,
        checkpoint_postgres_url=settings.jc_deerflow_checkpoint_postgres_url,
    )


def get_deerflow_client(db: AsyncSession | None = None) -> DeerFlowSessionClient:
    client = DeerFlowHarnessSessionClient(_client_config())
    if db is not None:
        client.bind_db(db)
    return client
