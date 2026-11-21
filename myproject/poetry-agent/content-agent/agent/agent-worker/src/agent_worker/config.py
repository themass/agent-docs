"""Environment-driven settings. Defaults are conservative; the worker holds no model credential."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.getenv(name, "") or default)
    except ValueError:
        return default
    return max(low, min(high, value))


def _float(name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(os.getenv(name, "") or default)
    except ValueError:
        return default
    return max(low, min(high, value))


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    port: int
    profile_root: Path | None
    control_url: str
    control_token: str
    worker_token: str
    deerflow_enabled: bool
    deerflow_url: str
    deerflow_token: str
    deerflow_assistant_id: str
    deerflow_auth_mode: str  # auto | bearer | internal | none
    deerflow_owner_user_id: str
    deerflow_fallback_model: str
    max_concurrent_runs: int
    queue_limit: int
    control_timeout: float
    deerflow_timeout: float
    poll_interval: float

    @property
    def budgets_path(self) -> Path | None:
        return self.profile_root / "config" / "budgets.yaml" if self.profile_root else None

    def public(self) -> dict[str, object]:
        """Safe to log: no tokens."""
        return {
            "port": self.port, "profile_root": str(self.profile_root or ""),
            "control_configured": bool(self.control_url and self.control_token),
            "worker_token_configured": bool(self.worker_token),
            "deerflow_enabled": self.deerflow_enabled, "max_concurrent_runs": self.max_concurrent_runs,
        }


def load_settings() -> Settings:
    root = os.getenv("POETRY_AGENT_PROFILE_ROOT", "").strip()
    if not root and Path("/app/deerflow-profile").is_dir():  # the copy baked into the image
        root = "/app/deerflow-profile"
    return Settings(
        port=_int("PORT", 8102, 1, 65535),
        profile_root=Path(root) if root else None,
        control_url=os.getenv("POETRY_DOMAIN_CONTROL_URL", "").strip().rstrip("/"),
        control_token=os.getenv("POETRY_DOMAIN_CONTROL_TOKEN", ""),
        worker_token=os.getenv("POETRY_WORKER_TOKEN", ""),
        deerflow_enabled=_flag("DEERFLOW_ENABLED"),
        deerflow_url=os.getenv("DEERFLOW_GATEWAY_URL", "").strip().rstrip("/"),
        deerflow_token=os.getenv("DEERFLOW_GATEWAY_TOKEN", ""),
        deerflow_assistant_id=os.getenv("DEERFLOW_ASSISTANT_ID", "").strip() or "poetry-editor-lead",
        deerflow_auth_mode=(os.getenv("DEERFLOW_AUTH_MODE", "auto").strip().lower() or "auto"),
        deerflow_owner_user_id=os.getenv("DEERFLOW_OWNER_USER_ID", "").strip() or "poetry-authoring",
        deerflow_fallback_model=os.getenv("DEERFLOW_FALLBACK_MODEL", "").strip(),
        max_concurrent_runs=_int("WORKER_MAX_CONCURRENT_RUNS", 2, 1, 16),
        queue_limit=_int("WORKER_QUEUE_LIMIT", 8, 0, 64),
        control_timeout=_float("WORKER_CONTROL_TIMEOUT_SECONDS", 15, 1, 120),
        deerflow_timeout=_float("WORKER_DEERFLOW_TIMEOUT_SECONDS", 30, 1, 300),
        poll_interval=_float("WORKER_POLL_INTERVAL_SECONDS", 2, 0.05, 30),
    )
