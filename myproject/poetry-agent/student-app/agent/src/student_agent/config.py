"""Settings. Reads only the variables this service needs, from the process environment first and then
from the git-ignored ``student-app/agent/.env``. Secrets never appear in ``repr`` or in ``health()``.

A missing or partial LLM configuration is not an error: the service starts in ``script`` mode.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[2]  # student-app/agent
APP_ROOT = AGENT_ROOT.parent  # student-app

# Only these keys are ever read from the .env file; everything else in it is ignored on purpose.
_ENV_KEYS = frozenset({
    "POETRY_LLM_API_BASE", "POETRY_LLM_API_KEY", "POETRY_LLM_MODEL_PRIMARY", "POETRY_LLM_MODEL_FALLBACK",
    "STUDENT_AGENT_MODE", "STUDENT_AGENT_SOURCE", "STUDENT_AGENT_AUTH", "STUDENT_JAVA_BASE",
    "STUDENT_LLM_ACTIONS", "STUDENT_LLM_POET", "STUDENT_AGENT_PORT", "STUDENT_AGENT_HOST", "STUDENT_AGENT_CORS",
    "STUDENT_LESSONS_DIR", "STUDENT_FIXTURES_DIR", "STUDENT_BUNDLES_DIR",
})

DEFAULT_LLM_ACTIONS = frozenset({"rephrase", "hint"})  # B1: the only actions allowed to reach a model
DEFAULT_CORS = (
    "http://localhost:5180,http://127.0.0.1:5180,capacitor://localhost,http://localhost,ionic://localhost"
)


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return values
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key not in _ENV_KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


@dataclass(frozen=True)
class Settings:
    llm_base: str = field(default="", repr=False)
    llm_key: str = field(default="", repr=False)
    model_primary: str = field(default="", repr=False)
    model_fallback: str = field(default="", repr=False)
    mode_override: str = ""  # "script" forces scripted answers
    source: str = "fixture"  # "java" | "fixture"
    java_base: str = field(default="", repr=False)
    auth: str = "none"  # "java" | "none". "none" is only valid when bound to loopback (see check_binding).
    llm_actions: frozenset[str] = DEFAULT_LLM_ACTIONS
    llm_poet: bool = False  # the poet's wording stays scripted until the eval set passes
    host: str = "127.0.0.1"  # loopback by default; anything else requires auth="java"
    port: int = 8765
    cors: tuple[str, ...] = tuple(DEFAULT_CORS.split(","))
    lessons_dir: Path = AGENT_ROOT / "data" / "lessons"
    fixtures_dir: Path = APP_ROOT / "runtime" / "contracts"
    bundles_dir: Path | None = None  # dev only: compiled bundles (content-agent/pipeline/dist/bundles); None = sample only
    timeout_primary: float = 6.0
    timeout_fallback: float = 4.0
    calls_per_lesson: int = 12
    tokens_per_lesson: int = 4000
    turns_per_minute: int = 20

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base and self.llm_key and self.model_primary)

    @property
    def mode(self) -> str:
        if self.mode_override.lower() == "script":
            return "script"
        return "llm" if self.llm_configured else "script"

    def binding_error(self) -> str | None:
        """Why this bind address + auth combination is refused, or ``None`` if it is safe.

        ``auth="none"`` only checks that an Authorization header *exists* — any string passes. That is
        acceptable on loopback (reachable only from this machine) and unacceptable anywhere else, where it
        would hand every caller an authenticated bucket. Refusing to start beats a deployment checklist line
        nobody remembers to copy to the next machine.
        """
        if self.auth == "java":
            return None
        if self.host in ("127.0.0.1", "::1", "localhost"):
            return None
        return (f"refusing to start: STUDENT_AGENT_HOST={self.host} is not loopback but "
                f"STUDENT_AGENT_AUTH={self.auth!r} does not verify credentials. "
                "Set STUDENT_AGENT_AUTH=java (with STUDENT_JAVA_BASE) or bind 127.0.0.1.")

    def health(self) -> dict[str, object]:
        """Safe to return to any caller: no address, no key, no model name."""
        return {"status": "ok", "mode": self.mode, "primary_configured": self.llm_configured, "source": self.source}

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, env_file: Path | None = None) -> Settings:
        process = dict(os.environ if env is None else env)
        file_values = read_env_file(env_file if env_file is not None else AGENT_ROOT / ".env")
        merged = {**file_values, **{k: v for k, v in process.items() if k in _ENV_KEYS}}

        def get(name: str, default: str = "") -> str:
            return merged.get(name, default).strip()

        java_base = get("STUDENT_JAVA_BASE").rstrip("/")
        source = get("STUDENT_AGENT_SOURCE") or ("java" if java_base else "fixture")
        auth = get("STUDENT_AGENT_AUTH") or ("java" if source == "java" else "none")
        actions = get("STUDENT_LLM_ACTIONS")
        llm_actions = frozenset(a.strip() for a in actions.split(",") if a.strip()) if actions else DEFAULT_LLM_ACTIONS
        port_text = get("STUDENT_AGENT_PORT", "8765")
        return cls(
            llm_base=get("POETRY_LLM_API_BASE").rstrip("/"),
            llm_key=get("POETRY_LLM_API_KEY"),
            model_primary=get("POETRY_LLM_MODEL_PRIMARY"),
            model_fallback=get("POETRY_LLM_MODEL_FALLBACK") or get("POETRY_LLM_MODEL_PRIMARY"),
            mode_override=get("STUDENT_AGENT_MODE"),
            source=source,
            java_base=java_base,
            auth=auth,
            llm_actions=llm_actions,
            llm_poet=get("STUDENT_LLM_POET") in {"1", "true", "yes"},
            host=get("STUDENT_AGENT_HOST") or "127.0.0.1",
            port=int(port_text) if port_text.isdigit() else 8765,
            cors=tuple(c.strip() for c in get("STUDENT_AGENT_CORS", DEFAULT_CORS).split(",") if c.strip()),
            lessons_dir=Path(get("STUDENT_LESSONS_DIR")) if get("STUDENT_LESSONS_DIR") else AGENT_ROOT / "data" / "lessons",
            fixtures_dir=Path(get("STUDENT_FIXTURES_DIR")) if get("STUDENT_FIXTURES_DIR") else APP_ROOT / "runtime" / "contracts",
            bundles_dir=Path(get("STUDENT_BUNDLES_DIR")) if get("STUDENT_BUNDLES_DIR") else None,
        )
