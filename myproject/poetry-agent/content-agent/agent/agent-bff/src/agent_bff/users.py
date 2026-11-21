"""Manage Studio accounts from a terminal. Passwords are read with getpass, never from arguments.

    python -m agent_bff.users add --file /path/outside/repo/studio-users.json --id wang-reviewer \\
        --role HISTORICAL_REVIEWER --name 王审核
    python -m agent_bff.users list --file ...
    python -m agent_bff.users remove --file ... --id wang-reviewer
    python -m agent_bff.users gen-secret

Keep the file outside the repository (it holds password hashes) and ``chmod 600`` it; this tool does.
Account changes take effect on the running BFF immediately (no restart).
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import secrets
import sys
from pathlib import Path

from agent_bff.auth import USER_ID, hash_password
from agent_bff.models import ROLES


def _read(path: Path) -> dict:
    if not path.exists():
        return {"users": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent_bff.users", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("add", "list", "remove"):
        command = sub.add_parser(name)
        command.add_argument("--file", required=True, type=Path)
        if name != "list":
            command.add_argument("--id", required=True)
        if name == "add":
            command.add_argument("--role", required=True, choices=ROLES)
            command.add_argument("--name", default="")
    sub.add_parser("gen-secret")
    args = parser.parse_args(argv)

    if args.command == "gen-secret":
        print(secrets.token_urlsafe(48))
        return 0
    document = _read(args.file)
    entries = [e for e in document.get("users", []) if isinstance(e, dict)]
    if args.command == "list":
        for entry in entries:
            print(f"{entry.get('id')}\t{entry.get('role')}\t{entry.get('name', '')}")
        return 0
    if args.command == "remove":
        kept = [e for e in entries if e.get("id") != args.id]
        if len(kept) == len(entries):
            print(f"no such user: {args.id}", file=sys.stderr)
            return 1
        _write(args.file, {"users": kept})
        print(f"removed {args.id}")
        return 0
    if not USER_ID.fullmatch(args.id):
        print("id must be 2-64 characters of letters, digits, '_', '.', '-'", file=sys.stderr)
        return 2
    password = getpass.getpass("密码(至少 10 位): ")
    if len(password) < 10 or password != getpass.getpass("再输入一次: "):
        print("密码太短或两次不一致", file=sys.stderr)
        return 2
    entries = [e for e in entries if e.get("id") != args.id]
    entries.append({"id": args.id, "name": args.name or args.id, "role": args.role, "password_hash": hash_password(password)})
    _write(args.file, {"users": entries})
    print(f"saved {args.id} ({args.role}) to {args.file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
