"""The DeerFlow adapter must receive a *resolved* checkpointer DSN.

The bug this pins: `DeerFlowClientConfig.checkpoint_dsn` (agentkit) treats an
empty `checkpoint_postgres_url` as "not configured" and raises. JC resolves the
DSN itself — falling back to `JC_DATABASE_URL` — so passing the raw, empty
`JC_DEERFLOW_CHECKPOINT_POSTGRES_URL` through made every agent turn fail with
`checkpoint_postgres_url is required`, while the deterministic services (which
call the router directly) kept working. That asymmetry is why the failure was
easy to miss: the API was up and most endpoints answered.
"""

from __future__ import annotations

from jc.adapters.deerflow_client import _client_config


def test_the_adapter_gets_the_resolved_dsn_not_the_raw_env(monkeypatch):
    """With only JC_DATABASE_URL set, the adapter must still get a usable DSN."""
    monkeypatch.setattr("jc.config.settings.jc_database_url", "", raising=False)
    monkeypatch.setenv("JC_DATABASE_URL", "postgresql+psycopg://u:p@h:5432/db")
    monkeypatch.delenv("JC_DEERFLOW_CHECKPOINT_POSTGRES_URL", raising=False)
    monkeypatch.setenv("JC_DEERFLOW_CHECKPOINT_BACKEND", "postgres")

    from jc.config import Settings

    resolved = Settings().deerflow_checkpoint_dsn
    assert resolved.startswith("postgresql+psycopg://")


def test_the_client_config_carries_a_non_empty_url_for_postgres(monkeypatch):
    """The exact regression: an empty URL here raised inside every agent turn."""
    monkeypatch.setenv("JC_DATABASE_URL", "postgresql+psycopg://u:p@h:5432/db")
    monkeypatch.delenv("JC_DEERFLOW_CHECKPOINT_POSTGRES_URL", raising=False)
    monkeypatch.setenv("JC_DEERFLOW_CHECKPOINT_BACKEND", "postgres")

    from jc.config import Settings

    monkeypatch.setattr("jc.adapters.deerflow_client.settings", Settings())
    config = _client_config()
    assert config.checkpoint_postgres_url, "adapter got an empty DSN; every turn would fail"
    # And the property agentkit reads returns it rather than raising.
    assert config.checkpoint_dsn == config.checkpoint_postgres_url


def test_a_dedicated_checkpoint_url_still_wins(monkeypatch):
    monkeypatch.setenv("JC_DATABASE_URL", "postgresql+psycopg://u:p@business:5432/db")
    monkeypatch.setenv(
        "JC_DEERFLOW_CHECKPOINT_POSTGRES_URL", "postgresql+psycopg://u:p@ckpt:5432/db"
    )
    monkeypatch.setenv("JC_DEERFLOW_CHECKPOINT_BACKEND", "postgres")

    from jc.config import Settings

    monkeypatch.setattr("jc.adapters.deerflow_client.settings", Settings())
    assert _client_config().checkpoint_postgres_url.endswith("@ckpt:5432/db")


def test_sqlite_backend_needs_no_postgres_url(monkeypatch, tmp_path):
    """The dev default must keep working with no Postgres at all."""
    monkeypatch.setenv("JC_DEERFLOW_CHECKPOINT_BACKEND", "sqlite")
    monkeypatch.setenv(
        "JC_DEERFLOW_CHECKPOINT_SQLITE_PATH", str(tmp_path / "ckpt.sqlite3")
    )
    monkeypatch.delenv("JC_DATABASE_URL", raising=False)

    from jc.config import Settings

    resolved = Settings()
    monkeypatch.setattr("jc.adapters.deerflow_client.settings", resolved)
    config = _client_config()
    # JC's own resolver returns a plain path (DeerFlow's sqlite resolver rejects
    # `file:` URIs); agentkit's property wraps the same path for its cache key.
    assert resolved.deerflow_checkpoint_dsn == str(tmp_path / "ckpt.sqlite3")
    assert config.checkpoint_dsn.endswith("ckpt.sqlite3")
