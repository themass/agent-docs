"""Local log capture must preserve output without changing service exit status/PIDs."""
from __future__ import annotations

import importlib.util
import io
import re
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
HELPER = PROJECT / "scripts/lib/log_output.py"


def load():
    spec = importlib.util.spec_from_file_location("dev_log_output", HELPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_log_captures_unicode_traceback_and_terminal_output(tmp_path):
    text = "\x1b[31mERROR\x1b[0m 预览失败\nTraceback:\n  frame\nlast line"
    output = io.StringIO()
    path = tmp_path / "logs/api.log"
    load().capture(path, io.StringIO(text), output)
    assert output.getvalue() == text
    saved = path.read_text()
    assert "\x1b" not in saved
    assert "预览失败" in saved and "Traceback:" in saved and "last line" in saved
    assert re.match(r"\[\d{4}-\d\d-\d\dT.*[+-]\d\d:\d\d\]", saved)
    assert path.stat().st_mode & 0o077 == 0


def test_log_rotates_and_stays_bounded(tmp_path):
    path = tmp_path / "api.log"
    load().capture(path, io.StringIO("line\n" * 100), io.StringIO(), max_bytes=160, backups=2)
    assert {p.name for p in tmp_path.iterdir()} == {"api.log", "api.log.1", "api.log.2"}
    assert all(p.stat().st_size <= 160 for p in tmp_path.iterdir())


def test_capture_is_append_only_between_restarts(tmp_path):
    path = tmp_path / "api.log"
    for line in ("first\n", "second\n"):
        load().capture(path, io.StringIO(line), io.StringIO())
    assert "first" in path.read_text() and "second" in path.read_text()


def test_bash_redirection_preserves_service_pid_and_failure_status(tmp_path):
    result = subprocess.run([
        "bash", "-c",
        '"$1" -c "import sys; print(12345); sys.exit(7)" '
        '> >("$1" "$2" "$3") 2>&1 & pid=$!; wait "$pid"; result=$?; '
        'echo "service_status=$result"; exit "$result"',
        "fixture", sys.executable, str(HELPER), str(tmp_path / "api.log"),
    ], capture_output=True, text=True)
    assert result.returncode == 7
    assert "12345" in result.stdout and "service_status=7" in result.stdout
    assert "12345" in (tmp_path / "api.log").read_text()
