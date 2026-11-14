"""Shared entry point for every standalone `scripts/*.py` tool.

Why this exists
----------------
Fifteen scripts each recomputed `PROJECT_ROOT` as `Path(__file__).resolve().parents[N]`
and hand-rolled a `sys.path.insert`. Two of them (`verify_exports.py` and `seed_demo.py`, both since removed)
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

1. Finds the repository root by walking up from this file looking for
   `libs/agentkit/{pyproject.toml,src/agentkit}` — the same identity check
   `scripts/lib/project_paths.sh:jc_repo_root` uses on the shell side, so the two
   layers of tooling agree by construction rather than by two people remembering the
   same magic number. The interpreter is chosen separately (see `_target_python`):
   a virtualenv is never committed, so requiring one beside the source would make a
   fresh clone look like a missing repository.
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
    """Raised when the repository root or interpreter cannot be identified."""


def _find_repo_root(start: Path) -> Path:
    """Walk up from `start` to the directory owning the agentkit source tree.

    Identity check, not index arithmetic — see module docstring. A script moved to a
    new subdirectory still resolves correctly; a `parents[N]` constant would not.

    The marker is `libs/agentkit/{pyproject.toml,src/agentkit}`, i.e. the *source*.
    It used to also require `venv/bin/python` next to it, which conflated two
    unrelated questions: where the repository is, and which interpreter to run. A
    virtualenv is never committed, so a fresh clone has the source but no venv —
    that check would have declared the repository missing on exactly the machine
    that had just cloned it. Interpreter discovery is `_target_python`'s job.
    """
    probe = start
    while True:
        agentkit = probe / "libs" / "agentkit"
        if (agentkit / "pyproject.toml").exists() and (agentkit / "src" / "agentkit").is_dir():
            return probe
        if probe.parent == probe:
            raise ProjectEnvError(
                f"Could not find the repository root (libs/agentkit) above {start}. "
                "Set JC_PYTHON explicitly if this is a partial checkout."
            )
        probe = probe.parent


#: Kept as an alias: callers and docs already use "monorepo root" for this.
_find_monorepo_root = _find_repo_root


def _target_python(project_root: Path) -> Path:
    """The interpreter the scripts should run under. Same order as `jc_python` in
    `scripts/lib/project_paths.sh`, so shell and Python callers agree:

    1. ``$JC_PYTHON``.
    2. The monorepo's ``venv`` when this checkout sits inside the monorepo (development).
    3. ``backend/server/.venv``, the venv ``deploy.sh`` builds. On a server job-come is
       deployed on its own, there is no monorepo above it, and a script that insisted on
       finding one would fail before doing anything -- including the cron job that prunes
       the LLM audit log.

    The monorepo comes before the project venv because a leftover ``backend/server/.venv``
    on a dev machine lacks the dev dependencies.
    """
    configured = os.environ.get("JC_PYTHON")
    if configured:
        return Path(configured)
    try:
        repo_python = _find_repo_root(project_root) / "venv" / "bin" / "python"
        if repo_python.exists():
            return repo_python
    except ProjectEnvError:
        pass
    # A venv beside any ancestor of the project, which is where a sibling-checkout
    # layout keeps it (the venv and the repository need not be the same directory).
    for parent in project_root.parents:
        candidate = parent / "venv" / "bin" / "python"
        if candidate.exists():
            return candidate
    project_python = project_root / "backend" / "server" / ".venv" / "bin" / "python"
    if project_python.exists():
        return project_python
    raise ProjectEnvError(
        f"No interpreter found for {project_root}. "
        "Run ./scripts/setup-venv.sh, or set JC_PYTHON explicitly."
    )


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

    target_python = _target_python(project_root)

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
