"""Launch-script contracts must match the monorepo layout documented for JC."""

from __future__ import annotations

import subprocess
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SERVER_ROOT.parents[1]
MONOREPO_ROOT = PROJECT_ROOT.parents[2]


def test_launch_scripts_are_valid_bash() -> None:
    result = subprocess.run(
        [
            "bash",
            "-n",
            "scripts/dev.sh",
            "scripts/db_upgrade.sh",
            "scripts/setup-venv.sh",
            "scripts/lib/project_paths.sh",
            "scripts/lib/ensure_python_env.sh",
            "scripts/test-local.sh",
            "scripts/test-live.sh",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_alembic_ini_lives_with_server_migrations() -> None:
    ini = SERVER_ROOT / "alembic.ini"
    assert ini.is_file(), f"missing {ini} (Alembic cwd is backend/server)"
    assert (SERVER_ROOT / "alembic" / "env.py").is_file()
    assert "script_location" in ini.read_text(encoding="utf-8")


def test_db_upgrade_uses_venv_alembic_cli() -> None:
    text = (PROJECT_ROOT / "scripts" / "db_upgrade.sh").read_text(encoding="utf-8")
    assert 'exec "$ALEMBIC_BIN"' in text
    assert 'exec "$PYTHON" -m alembic' not in text
    assert "jc_ensure_python_env" in text


def test_dev_bootstraps_python_env_before_logs() -> None:
    text = (PROJECT_ROOT / "scripts" / "dev.sh").read_text(encoding="utf-8")
    ensure_pos = text.index("jc_ensure_python_env")
    log_redirect_pos = text.index('exec > >("$PYTHON"')
    assert ensure_pos < log_redirect_pos


def test_monorepo_discovery_finds_deepagents_venv() -> None:
    command = (
        'source scripts/lib/project_paths.sh; '
        'root="$(jc_monorepo_root \"$PWD\")"; '
        'python="$(jc_python \"$PWD\")"; '
        'printf "%s\\n%s\\n" "$root" "$python"'
    )
    result = subprocess.run(
        ["bash", "-c", command],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    monorepo_root, python = result.stdout.splitlines()
    assert monorepo_root == str(MONOREPO_ROOT)
    assert python == str(MONOREPO_ROOT / "venv" / "bin" / "python")
