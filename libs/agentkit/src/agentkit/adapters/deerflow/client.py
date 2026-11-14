from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(slots=True)
class AgentRunMetadata:
    trace_id: str
    user_id: str | None
    profile_id: str | None
    session_id: str | None
    skill_hint: str | None
    extra: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "profile_id": self.profile_id,
            "session_id": self.session_id,
            "skill_hint": self.skill_hint,
        }
        data.update(self.extra)
        return {k: v for k, v in data.items() if v is not None}

@dataclass(frozen=True, slots=True)
class DeerFlowClientConfig:
    extensions_config_path: str
    checkpoint_backend: str = "sqlite"
    checkpoint_sqlite_path: str = ".data/deerflow/checkpoints.sqlite3"
    checkpoint_postgres_url: str = ""

    @property
    def checkpoint_dsn(self) -> str:
        backend = self.checkpoint_backend.lower()
        if backend == "postgres":
            if not self.checkpoint_postgres_url:
                raise ValueError("checkpoint_postgres_url is required")
            return self.checkpoint_postgres_url
        path = Path(self.checkpoint_sqlite_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path}"

class DeerFlowSessionClient:
    """Only module that may import deerflow (inside methods, optional extra)."""

    def __init__(self, config: DeerFlowClientConfig) -> None:
        self._config = config

    @property
    def checkpoint_dsn(self) -> str:
        return self._config.checkpoint_dsn

    async def run_once(self, *, skill: str, metadata: AgentRunMetadata, context: dict[str, Any]) -> Any:
        raise NotImplementedError("W0 DeerFlow spike")

    async def start_session(self, *, metadata: AgentRunMetadata) -> str:
        raise NotImplementedError("W0 DeerFlow spike")

    async def stream_events(self, session_id: str):
        raise NotImplementedError("W0 DeerFlow spike")
        yield
