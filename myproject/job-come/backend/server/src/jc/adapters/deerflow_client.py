"""DeerFlow harness client factory — single runtime, no fallback."""

from __future__ import annotations

from agentkit.adapters.deerflow.client import DeerFlowClientConfig, DeerFlowSessionClient
from sqlalchemy.ext.asyncio import AsyncSession

from jc.adapters.deerflow_harness_client import DeerFlowHarnessSessionClient
from jc.config import settings


def _client_config() -> DeerFlowClientConfig:
    # `settings.deerflow_checkpoint_dsn` is already resolved: it falls back to
    # `JC_DATABASE_URL` when no dedicated checkpointer URL is set, and raises if
    # the backend is postgres with nothing usable. Passing the raw
    # `jc_deerflow_checkpoint_postgres_url` instead would hand agentkit an empty
    # string, and its own `checkpoint_dsn` property treats empty as "not
    # configured" and raises — which is exactly how the whole agent path broke
    # once production moved to Postgres without a dedicated checkpoint URL.
    return DeerFlowClientConfig(
        extensions_config_path=settings.jc_deerflow_extensions_config,
        checkpoint_backend=settings.jc_deerflow_checkpoint_backend,
        checkpoint_sqlite_path=settings.jc_deerflow_checkpoint_sqlite_path,
        checkpoint_postgres_url=settings.deerflow_checkpoint_dsn,
    )


def get_deerflow_client(db: AsyncSession | None = None) -> DeerFlowSessionClient:
    client = DeerFlowHarnessSessionClient(_client_config())
    if db is not None:
        client.bind_db(db)
    return client
