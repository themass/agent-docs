"""Shared entry point for every standalone `scripts/*.py` tool.

Why this exists
----------------
Fifteen scripts each recomputed `PROJECT_ROOT` as `Path(__file__).resolve().parents[N]`
and hand-rolled a `sys.path.insert`. Two of them (`verify_exports.py`, `seed_demo.py`)
had the index wrong and pointed at `<repo>/src`, which does not exist — the kind of
defect `jc/paths.py` documents as "caught by nothing, because the fallback never
raises". A third, independent failure mode sits one level further out and `jc/paths.py`
cannot reach it: every script carries `#!/usr/bin/env python3` and is commonly invoked
as `python scripts/x.py`, which resolves through whatever `python` happens to be first
on `PATH` — a pyenv shim, a different venv, system Python — not the project's
`deepagents/venv`. That interpreter has none of `backend/server`'s dependencies
(`pymupdf`, `markitdown`, ...), so a script degrades with a *downstream* symptom (a
PDF decoder reports it cannot render pages) that looks like a parsing bug and is
actually a wrong-interpreter bug. That exact failure is what prompted this module.

What every script should do instead
------------------------------------
Put this as the first import, before any `jc.*` import and before argument parsing::

    from lib.bootstrap import ensure_project_env
    ensure_project_env()

`ensure_project_env()`:

1. Finds the monorepo root by walking up from this file looking for the directory that
   owns both `venv/bin/python` and `libs/agentkit` — the same identity check
   `scripts/lib/project_paths.sh:jc_monorepo_root` uses on the shell side, so the two
   layers of tooling agree by construction rather than by two people remembering the
   same magic number.
2. If the *running* interpreter is not that venv's `python` (and `JC_PYTHON` was not
   set to deliberately override it), re-execs the current script under the correct one
   via `os.execv`. The script's own `sys.argv` is preserved, so this is transparent to
   both `python scripts/x.py ...` and `./scripts/x.py ...` invocations and to anyone
   reading the traceback (it is the same process image, not a subprocess wrapper).
3. Inserts `backend/server/src` onto `sys.path` so `import jc...` resolves regardless
   of the caller's cwd.

A script that must skip the re-exec (for example because it is itself under test and
the test harness already controls the interpreter) can set
`JC_BOOTSTRAP_SKIP_REEXEC=1`; `ensure_project_env()` still fixes `sys.path`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


class ProjectEnvError(RuntimeError):
    """Raised when the monorepo root cannot be identified from this file's location."""


def _find_monorepo_root(start: Path) -> Path:
    """Walk up from `start` to the directory owning `venv/` and `libs/agentkit`.

    Identity check, not index arithmetic — see module docstring. A script moved to a
    new subdirectory still resolves correctly; a `parents[N]` constant would not.
    """
    probe = start
    while True:
        if (probe / "venv" / "bin" / "python").exists() and (probe / "libs" / "agentkit").is_dir():
            return probe
        if probe.parent == probe:
            raise ProjectEnvError(
                f"Could not find the monorepo root (venv/ + libs/agentkit) above {start}. "
                "Run ./scripts/setup-venv.sh first, or set JC_PYTHON explicitly."
            )
        probe = probe.parent


def _project_root(this_file: Path) -> Path:
    """`<repo>/myproject/job-come` — holds `docs/`, `scripts/`, `backend/`, `frontend/`."""
    # this_file is scripts/lib/bootstrap.py; job-come root is two levels up.
    candidate = this_file.resolve().parents[2]
    if not (candidate / "backend" / "server").is_dir():
        raise ProjectEnvError(
            f"scripts/lib/bootstrap.py moved? parents[2]={candidate} has no backend/server."
        )
    return candidate


def ensure_project_env() -> Path:
    """Guarantee the right interpreter and import path. Returns PROJECT_ROOT.

    Call this before any `jc.*` import. Safe to call more than once.
    """
    this_file = Path(__file__)
    project_root = _project_root(this_file)
    server_src = project_root / "backend" / "server" / "src"

    server_src_str = str(server_src)
    if server_src_str not in sys.path:
        sys.path.insert(0, server_src_str)

    configured = os.environ.get("JC_PYTHON")
    if configured:
        target_python = Path(configured)
    else:
        monorepo_root = _find_monorepo_root(project_root)
        target_python = monorepo_root / "venv" / "bin" / "python"

    if os.environ.get("JC_BOOTSTRAP_SKIP_REEXEC"):
        return project_root

    if not target_python.exists():
        # Nothing to re-exec into; let the caller's own import of `jc.*` fail with a
        # real traceback rather than hiding it behind a second, confusing error here.
        return project_root

    # Compared without resolving symlinks on purpose. A venv's `bin/python` is a
    # symlink to the base interpreter by design (see `pyvenv.cfg`), so resolving it
    # erases exactly the distinction this check needs: the pyenv shim and this venv
    # can resolve to the *same* real binary while still being different environments
    # (the venv's `site-packages` is reached through `sys.prefix`, derived from the
    # unresolved path next to `pyvenv.cfg`, not from the binary's final target).
    if str(target_python) == sys.executable:
        return project_root

    os.environ["JC_BOOTSTRAP_SKIP_REEXEC"] = "1"  # the re-exec'd process must not loop
    os.execv(str(target_python), [str(target_python), *sys.argv])
    raise AssertionError("os.execv returned, which it never does on success")  # pragma: no cover
