"""Kept for compatibility: ``python -m agent_worker.health`` now starts the real worker."""
from __future__ import annotations


def main() -> None:
    from agent_worker.app import run

    run()


if __name__ == "__main__":
    main()
