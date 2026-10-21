"""Where things live on disk — the single owner of repository layout.

This exists because the same layout knowledge was spelled out eleven times in four
different ways (`parents[2]`, `parents[3]`, `parents[2].parent`, `parents[3].parent`),
and one of them was off by a level: `llm/router.py` resolved the server root to
`src/` instead of `backend/server/`, so `.env` loading silently did nothing and the
routing file was only ever found because the process happened to be started from
`backend/server`. Starting the server from anywhere else raised FileNotFoundError.

An off-by-one in a `parents[]` index cannot be caught by reading the line; it can only
be caught by asking "which directory is this, by name". That is what the asserts at
import time below do, and what `tests/test_paths.py` keeps honest.

Everything here is a pure path computation. No layer restrictions apply: this module
imports nothing from `jc`, so any layer may use it.
"""

from __future__ import annotations

from pathlib import Path

#: `backend/server` — the Python project root (holds `.env`, `pyproject.toml`, `alembic/`).
SERVER_ROOT = Path(__file__).resolve().parents[2]

#: `backend` — the parent of both the Python server and the agent asset tree.
BACKEND_ROOT = SERVER_ROOT.parent

#: `backend/agent` — prompts, skills and harness config. Not Python; shipped as data.
AGENT_ROOT = BACKEND_ROOT / "agent"

#: `backend/agent/prompts` — Jinja prompt templates, addressed by relative path.
PROMPTS_ROOT = AGENT_ROOT / "prompts"

#: `<repo>/myproject/job-come` — holds `docs/`, `scripts/`, `frontend/`.
PROJECT_ROOT = BACKEND_ROOT.parent

# Fail at import rather than at the first missing file. A wrong index here makes every
# prompt load and every skill lookup degrade quietly, which is how the original defect
# survived: the fallback paths were all misses, so nothing ever raised.
assert SERVER_ROOT.name == "server", f"SERVER_ROOT resolved to {SERVER_ROOT}"
assert BACKEND_ROOT.name == "backend", f"BACKEND_ROOT resolved to {BACKEND_ROOT}"


def prompt_file(*parts: str) -> Path:
    """A prompt under `backend/agent/prompts`, e.g. `prompt_file("ingest", "jd_parser.md")`."""
    return PROMPTS_ROOT.joinpath(*parts)


def agent_file(*parts: str) -> Path:
    """A non-prompt agent asset, e.g. `agent_file("llm", "routing.yaml")`."""
    return AGENT_ROOT.joinpath(*parts)


def resolve_under_server(raw: str | Path) -> Path:
    """Resolve a configured path that may be absolute or relative to `backend/server`.

    Settings such as `JC_SKILLS_ROOT` and `JC_LLM_ROUTING_PATH` default to values like
    `../agent/llm/routing.yaml`, which are written relative to the server root. Passing
    them to `Path()` alone makes them relative to the *current working directory*, so
    the process worked from one directory and failed from every other one.
    """
    path = Path(raw)
    if path.is_absolute():
        return path
    return (SERVER_ROOT / path).resolve()
