"""Local dev stdout/stderr mirror. Stdlib only; never imports JC or its settings."""
from __future__ import annotations

import logging
import os
import re
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TextIO

ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class LocalTimeFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return datetime.fromtimestamp(record.created).astimezone().isoformat(timespec="seconds")


def capture(path: Path, source: TextIO, console: TextIO, *,
            max_bytes: int = 10 * 1024 * 1024, backups: int = 3) -> None:
    # Restrict new files and rotated copies to this user. Logs can include third-party
    # exception text; they are diagnostic artifacts, not public application data.
    previous_umask = os.umask(0o077)
    handler = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        handler = RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backups,
                                      encoding="utf-8")
        os.chmod(path, 0o600)
        handler.setFormatter(LocalTimeFormatter("[%(asctime)s] %(message)s"))
        for line in source:
            clean = ANSI.sub("", line).rstrip("\r\n")
            handler.emit(logging.LogRecord("dev", logging.INFO, "", 0, clean, (), None))
            if console is not None:
                try:
                    console.write(line)
                    console.flush()
                except (BrokenPipeError, OSError):
                    # Closing the terminal must not prevent writing the diagnostic file.
                    console = None
    finally:
        if handler is not None:
            handler.close()
        os.umask(previous_umask)


if __name__ == "__main__":
    capture(Path(sys.argv[1]), sys.stdin, sys.stdout)
