"""Run the real-model checklist on one interview.

    python -m jc.coach.acceptance_run --session <mock_session_id>
    python -m jc.coach.acceptance_run --session <id> --save recording.json
    python -m jc.coach.acceptance_run --file recording.json

`--session` reads the interview from the database the server is configured for (`.env`), so run it
where the interview was held. `--save` keeps the recording so it can be checked later or sent to
someone else; the recording holds the interview's text, so treat the file as you would the
interview.

Exit status: 0 when no rule failed, 1 when one did, 2 when the input could not be read. Rules that
need a person to read the interview are listed but never fail the run: code cannot decide them.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from jc.coach.acceptance import check_interviewer, check_reviewer, failures
from jc.coach.recording import render_findings

_REQUIRED = ("events", "role_family", "answers", "skipped", "control_messages")


def run_on_recording(recording: dict[str, Any]) -> tuple[bool, str]:
    """Check one recording. Returns (no rule failed, the text to show)."""
    lines: list[str] = []
    if recording.get("warnings"):
        lines.append("读取记录时的提醒（先看这里）")
        lines += [f"  ! {w}" for w in recording["warnings"]]
        lines.append("")

    events = recording.get("events") or []
    if not events:
        lines.append("没有可检查的对话：这份记录里没有消息。")
        return False, "\n".join(lines)

    interviewer = check_interviewer(events, role_family=recording.get("role_family"))
    reviewer = []
    report = recording.get("report")
    if report:
        reviewer = check_reviewer(
            report,
            answers=recording.get("answers") or {},
            skipped=set(recording.get("skipped") or []),
            control_messages=recording.get("control_messages") or [],
        )
    else:
        lines.append("还没有报告：评审那部分没有检查。报告生成后再跑一次。")
        lines.append("")

    session = recording.get("session") or {}
    lines.append(
        "面试：{id}  岗位：{job}  岗位族：{family}  级别：{level}  风格：{style}".format(
            id=session.get("id", "?"), job=session.get("job") or "无",
            family=recording.get("role_family") or "未知", level=session.get("level") or "无",
            style=session.get("style") or "无")
    )
    lines.append(render_findings(interviewer, reviewer))
    ok = not failures(interviewer) and not failures(reviewer)
    return ok, "\n".join(lines)


async def _record(session_id: str) -> dict[str, Any]:
    from jc.coach.recording import record_interview
    from jc.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        return await record_interview(db, session_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="jc.coach.acceptance_run", description=__doc__.split("\n")[0]
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--session", help="从数据库读取这场面试")
    source.add_argument("--file", help="检查一份保存好的记录")
    parser.add_argument("--save", help="把读到的记录存到这个文件（只配合 --session）")
    args = parser.parse_args(argv)

    if args.file:
        try:
            recording = json.loads(Path(args.file).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            print(f"读不到文件 {args.file}：{error}", file=sys.stderr)
            return 2
        if not isinstance(recording, dict) or not all(k in recording for k in _REQUIRED):
            print(f"{args.file} 不是一份面试记录（缺少 {', '.join(_REQUIRED)} 中的字段）。",
                  file=sys.stderr)
            return 2
    else:
        try:
            recording = asyncio.run(_record(args.session))
        except LookupError as error:
            print(str(error), file=sys.stderr)
            return 2
        if args.save:
            Path(args.save).write_text(
                json.dumps(recording, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"已保存到 {args.save}\n")

    ok, text = run_on_recording(recording)
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
