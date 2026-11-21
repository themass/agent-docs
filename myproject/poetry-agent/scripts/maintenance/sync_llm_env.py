#!/usr/bin/env python3
"""Copy the LLM gateway settings from another project's .env into this platform's gitignored env files.

    python3 scripts/maintenance/sync_llm_env.py            # write both targets
    python3 scripts/maintenance/sync_llm_env.py --check    # report only; change nothing

Rules this script enforces so a secret cannot end up in the repository:
  * a target is written only if `git check-ignore` says git ignores it;
  * values are never printed - only key names, lengths and the gateway host;
  * only the base URL and key are taken from the source (not logging or vision settings);
  * the file is written atomically with mode 600, and only the managed block is replaced.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path

PLATFORM = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = Path("/Users/gqli/work/deepagents/docs/myproject/job-come/backend/server/.env")
TARGETS = [PLATFORM / "content-agent/deploy/.env", PLATFORM / "student-app/agent/.env"]

# project-neutral names every agent in this platform reads
PRIMARY_MODEL = "deepseek-v4-pro"
FALLBACK_MODEL = "deepseek-v4-flash"
BEGIN = "# >>> poetry-llm (managed by scripts/maintenance/sync_llm_env.py) >>>"
END = "# <<< poetry-llm <<<"


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def git_ignores(path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(PLATFORM), "check-ignore", "-q", str(path)], capture_output=True, check=False
    )
    return result.returncode == 0


def managed_block(base: str, key: str) -> str:
    return "\n".join([
        BEGIN,
        f"POETRY_LLM_API_BASE={base}",
        f"POETRY_LLM_API_KEY={key}",
        f"POETRY_LLM_MODEL_PRIMARY={PRIMARY_MODEL}",
        f"POETRY_LLM_MODEL_FALLBACK={FALLBACK_MODEL}",
        END,
    ]) + "\n"


def with_block(existing: str, block: str) -> str:
    if BEGIN in existing and END in existing:
        head, rest = existing.split(BEGIN, 1)
        tail = rest.split(END, 1)[1].lstrip("\n")
        return head.rstrip("\n") + ("\n\n" if head.strip() else "") + block + ("\n" + tail if tail else "")
    sep = "" if not existing or existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    return existing + sep + block


def write_private(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".env.tmp.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--check", action="store_true", help="report only")
    args = parser.parse_args()

    if not args.source.is_file():
        print(f"source env not found: {args.source}", file=sys.stderr)
        return 2
    env = parse_env(args.source)
    base, key = env.get("JC_LLM_API_BASE", ""), env.get("JC_LLM_API_KEY", "")
    if not base or not key:
        print("source has no JC_LLM_API_BASE / JC_LLM_API_KEY", file=sys.stderr)
        return 2
    host = urllib.parse.urlparse(base).netloc or "?"
    print(f"source : {args.source}")
    print(f"gateway: {host}   key: <{len(key)} chars>   models: {PRIMARY_MODEL} / {FALLBACK_MODEL}")
    if base.startswith("http://"):
        print("note   : the gateway URL is plain http (as configured in the source project)")

    status = 0
    for target in TARGETS:
        rel = target.relative_to(PLATFORM)
        if not target.parent.is_dir():
            print(f"SKIP  {rel}: directory does not exist")
            status = 1
            continue
        if not git_ignores(target):
            print(f"REFUSE {rel}: git does not ignore this path - not writing a secret there")
            status = 1
            continue
        if args.check:
            have = target.is_file() and BEGIN in target.read_text(encoding="utf-8")
            print(f"{'present' if have else 'absent '} {rel} (git-ignored)")
            continue
        example = target.parent / ".env.example"
        if target.is_file():
            existing = target.read_text(encoding="utf-8")
        elif example.is_file():
            existing = example.read_text(encoding="utf-8")  # a new .env starts from the project's example
        else:
            existing = ""
        # An .env written earlier by this script contains only the managed block; give it the
        # project's other settings too, without overwriting anything already present.
        if example.is_file() and target.is_file():
            have = {line.split("=", 1)[0] for line in existing.splitlines() if "=" in line and not line.startswith("#")}
            missing = [line for line in example.read_text(encoding="utf-8").splitlines()
                       if "=" in line and not line.startswith("#") and line.split("=", 1)[0] not in have]
            if missing:
                existing = existing.rstrip("\n") + "\n\n# defaults added from .env.example\n" + "\n".join(missing) + "\n"
        write_private(target, with_block(existing, managed_block(base, key)))
        print(f"wrote  {rel}  (mode 600, git-ignored; managed block only)")
    return status


if __name__ == "__main__":
    sys.exit(main())
