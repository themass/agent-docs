#!/usr/bin/env python3
"""Dispatch Content Studio reports to local index and optional webhooks."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path


def post_json(url: str, payload: dict[str, object]) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        resp.read()


def read_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.name


def update_index(report_dir: Path, script_dir: Path) -> None:
    script = script_dir / "report_index.py"
    if script.exists():
        subprocess.run(
            [sys.executable, str(script), "--report-dir", str(report_dir)],
            check=False,
        )


def dispatch_webhook(report: Path, *, channel: str, url: str) -> None:
    title = read_title(report)
    text = report.read_text(encoding="utf-8", errors="replace")
    excerpt = "\n".join(text.splitlines()[:40])

    if channel == "discord":
        payload: dict[str, object] = {
            "content": f"**{title}**\n`{report}`\n\n{excerpt[:1800]}",
        }
    else:
        payload = {
            "msg_type": "text",
            "content": {
                "text": f"{title}\n{report}\n\n{excerpt[:3000]}",
            },
        }
    post_json(url, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", help="Report file to dispatch.")
    parser.add_argument(
        "--report-dir",
        default="~/.hermes/profiles/content-studio/reports",
        help="Report root directory.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print report path and a short preview.",
    )
    args = parser.parse_args()

    report = Path(args.report).expanduser()
    report_dir = Path(args.report_dir).expanduser()
    script_dir = Path(__file__).resolve().parent

    if not report.exists():
        print(f"report not found: {report}", file=sys.stderr)
        return 1

    update_index(report_dir, script_dir)

    if args.stdout:
        print(f"Report: {report}")
        print(f"Index: {report_dir / 'index.md'}")

    webhook_channels = {
        "feishu": os.getenv("CONTENT_STUDIO_FEISHU_WEBHOOK"),
        "wecom": os.getenv("CONTENT_STUDIO_WECOM_WEBHOOK"),
        "dingtalk": os.getenv("CONTENT_STUDIO_DINGTALK_WEBHOOK"),
        "discord": os.getenv("CONTENT_STUDIO_DISCORD_WEBHOOK"),
    }
    for channel, url in webhook_channels.items():
        if not url:
            continue
        try:
            dispatch_webhook(report, channel=channel, url=url)
            print(f"dispatched to {channel}")
        except OSError as exc:
            print(f"failed to dispatch to {channel}: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
