"""剧本 case 的 capture / freeze：真脑（或 FakeBrain）跑一轮 → JSON → 写回 YAML。

用法（在 server/ 目录）::

    uv run python -m tools.script_cases capture --case greet_emotion
    uv run python -m tools.script_cases capture --case greet_emotion --out /tmp/capture.json
    uv run python -m tools.script_cases freeze --case greet_emotion --from /tmp/capture.json

默认脑：无凭据时 FakeBrain（读 case 里已有 expect_reply，否则占位句）；
环境变量 ``COMPANION_LLM_API_KEY``（或 Settings 里等价项）存在时才尝试 DeerFlow。
不 import 生产 agent 入口（``companion.worker`` / ``companion.agent.entry``）。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

from companion.paths import SERVER_ROOT

CASES_DIR = SERVER_ROOT / "cases" / "voice"


def _case_path(case_id: str) -> Path:
    path = CASES_DIR / f"{case_id}.yaml"
    if not path.is_file():
        raise SystemExit(f"case 不存在: {path}")
    return path


def _first_user(case) -> str:
    for step in case.steps:
        if step.user is not None:
            return step.user
    return case.id


def _existing_reply_lines(case) -> list[str]:
    return [
        line
        for step in case.steps
        if step.expect_reply is not None
        for line in step.expect_reply
    ]


def _intended_protocol(case) -> list[str]:
    """拼出 YAML 里声明的 protocol 序列（供人对照，不是再跑一遍 publisher）。"""
    out: list[str] = []
    for step in case.steps:
        if step.protocol is not None:
            out.extend(step.protocol)
    return out


async def _collect_reply_lines(brain: Any, *, user_text: str, case_id: str) -> list[str]:
    from companion.agent.brain.port import TurnRequest
    from companion.agent.text.splitter import SentenceSplitter

    turn = await brain.start_turn(
        TurnRequest(user_id="script", character_id="script", message=user_text, thread_id=f"capture-{case_id}")
    )
    chunks: list[str] = []
    async for chunk in turn.tokens:
        if chunk:
            chunks.append(chunk)
    await brain.aclose()

    # FakeBrain 的 script 项本身就是「句」；真脑可能吐任意切分的 token。
    # 统一走 SentenceSplitter，保证 freeze 写入的是可朗读的整句。
    splitter = SentenceSplitter()
    lines: list[str] = []
    for chunk in chunks:
        lines.extend(splitter.feed(chunk))
    lines.extend(splitter.flush())
    # 若 splitter 因无终止符吐空、但脑确实吐了文本，退回整段
    if not lines and chunks:
        joined = "".join(chunks).strip()
        if joined:
            lines = [joined]
    return [ln for ln in lines if ln.strip()]


async def _protocol_from_lines(lines: list[str]) -> list[str]:
    """用离线 publisher 路径推一遍，得到实际协议时间线（含 emotion）。"""
    from companion.api.livekit.speech_publisher import SpeechPublisher
    from companion.devtools.script_room.offline_runner import RecordingBridge, drive_reply_line
    from companion.agent.protocol.cue_compiler import CueBudget

    bridge = RecordingBridge()
    publisher = SpeechPublisher(bridge)  # type: ignore[arg-type]
    budget = CueBudget()
    await publisher.start_reply()
    for i, line in enumerate(lines):
        await drive_reply_line(
            line,
            publisher=publisher,
            bridge=bridge,
            turn_id=f"capture-{i}",
            budget=budget,
        )
    await publisher.finish()
    return list(bridge.types)


async def capture_case(
    *,
    case_path: Path,
    brain: Any | None = None,
    out_path: Path | None = None,
) -> dict[str, Any]:
    """跑一轮脑，返回并可选写入 capture.json。

    ``brain`` 缺省时由 ``_default_brain`` 决定（测试应显式传入 FakeBrain）。
    """
    from companion.devtools.script_room.case_schema import load_case

    case = load_case(case_path)
    user_text = _first_user(case)
    if brain is None:
        brain = _default_brain(case)

    reply_lines = await _collect_reply_lines(brain, user_text=user_text, case_id=case.id)
    # 优先录实际协议；若无回复则退回 YAML 声明的 intended protocol
    protocol = await _protocol_from_lines(reply_lines) if reply_lines else _intended_protocol(case)
    if not protocol:
        protocol = _intended_protocol(case)

    payload: dict[str, Any] = {
        "case_id": case.id,
        "user": user_text,
        "reply_lines": reply_lines,
        "protocol": protocol,
    }
    if out_path is not None:
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def freeze_case(*, case_path: Path, capture_path: Path) -> None:
    """把 capture.json 的 reply_lines 写入 YAML 的 expect_reply 步。"""
    raw_capture = json.loads(capture_path.read_text(encoding="utf-8"))
    reply_lines = raw_capture.get("reply_lines")
    if not isinstance(reply_lines, list) or not reply_lines or not all(isinstance(x, str) for x in reply_lines):
        raise ValueError(f"capture.reply_lines must be non-empty list[str]: {capture_path}")

    doc = yaml.safe_load(case_path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("steps"), list):
        raise ValueError(f"case YAML must have steps list: {case_path}")

    steps: list[Any] = doc["steps"]
    expect_step = {"expect_reply": list(reply_lines)}

    # 已有 expect_reply → 替换；否则插在第一个 user 之后（没有 user 就插到最前）
    replaced = False
    for i, step in enumerate(steps):
        if isinstance(step, dict) and "expect_reply" in step:
            steps[i] = expect_step
            replaced = True
            break
    if not replaced:
        insert_at = 0
        for i, step in enumerate(steps):
            if isinstance(step, dict) and "user" in step:
                insert_at = i + 1
                break
        steps.insert(insert_at, expect_step)

    case_path.write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def _llm_credentials_present() -> bool:
    if (os.environ.get("COMPANION_LLM_API_KEY") or "").strip():
        return True
    try:
        from companion.config import settings

        return bool((getattr(settings, "companion_llm_api_key", "") or "").strip())
    except Exception:
        return False


def _default_brain(case) -> Any:
    """无凭据 → FakeBrain；有凭据时尝试 DeerFlow，失败再退 FakeBrain。"""
    from companion.agent.brain.fake import FakeBrain

    existing = _existing_reply_lines(case)
    fake = FakeBrain(script=existing or ["（capture 占位回复。）"])
    if not _llm_credentials_present():
        return fake
    try:
        return _try_deerflow_brain()
    except Exception as exc:  # noqa: BLE001 — capture CLI 要可降级
        print(f"warn: DeerFlow 不可用（{exc!r}），改用 FakeBrain", file=sys.stderr)
        return fake


def _try_deerflow_brain() -> Any:
    """最小 DeerFlow 装配；失败由调用方捕获。不走生产 entry/bootstrap。"""
    from companion.agent.brain.deerflow import DeerFlowBrain, build_turn_graph

    # 延迟 import：无凭据/无 litellm 时 capture 仍可用 FakeBrain
    from langchain_openai import ChatOpenAI

    from companion.config import settings

    api_key = (os.environ.get("COMPANION_LLM_API_KEY") or getattr(settings, "companion_llm_api_key", "") or "").strip()
    api_base = (os.environ.get("COMPANION_LLM_API_BASE") or getattr(settings, "companion_llm_api_base", "") or "").strip() or None
    model_name = (
        os.environ.get("COMPANION_LLM_MODEL_COMPANION_CHAT")
        or getattr(settings, "companion_llm_model_companion_chat", "")
        or "gpt-4o-mini"
    ).strip()
    model = ChatOpenAI(model=model_name, api_key=api_key, base_url=api_base, temperature=0.7)
    graph = build_turn_graph(model, tools=(), checkpointer=None)
    return DeerFlowBrain(graph, stateful=False)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tools.script_cases", description="capture / freeze 剧本 case 回复")
    sub = parser.add_subparsers(dest="command", required=True)

    cap = sub.add_parser("capture", help="跑一轮脑，打印 reply + protocol，并写 capture.json")
    cap.add_argument("--case", required=True, help="cases/voice/{id}.yaml 的 id")
    cap.add_argument(
        "--out",
        default=None,
        help="capture.json 路径（默认 ./capture-{case}.json）",
    )
    cap.add_argument(
        "--fake",
        action="store_true",
        help="强制 FakeBrain（忽略 LLM 凭据）",
    )

    frz = sub.add_parser("freeze", help="把 capture.json 的 reply_lines 写入 YAML expect_reply")
    frz.add_argument("--case", required=True, help="cases/voice/{id}.yaml 的 id")
    frz.add_argument("--from", dest="capture_from", required=True, help="capture.json 路径")
    return parser


async def _cmd_capture(args: argparse.Namespace) -> int:
    from companion.worker import load_env

    load_env()
    case_path = _case_path(args.case)
    out_path = Path(args.out) if args.out else Path(f"capture-{args.case}.json")
    brain = None
    if args.fake:
        from companion.agent.brain.fake import FakeBrain
        from companion.devtools.script_room.case_schema import load_case

        case = load_case(case_path)
        brain = FakeBrain(script=_existing_reply_lines(case) or ["（capture 占位回复。）"])

    payload = await capture_case(case_path=case_path, brain=brain, out_path=out_path)
    print(f"case: {payload['case_id']}")
    print(f"user: {payload['user']}")
    print("reply_lines:")
    for line in payload["reply_lines"]:
        print(f"  - {line}")
    print("protocol:")
    for ev in payload["protocol"]:
        print(f"  - {ev}")
    print(f"wrote: {out_path}")
    return 0


def _cmd_freeze(args: argparse.Namespace) -> int:
    case_path = _case_path(args.case)
    capture_path = Path(args.capture_from)
    if not capture_path.is_file():
        raise SystemExit(f"capture 不存在: {capture_path}")
    freeze_case(case_path=case_path, capture_path=capture_path)
    print(f"froze expect_reply → {case_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "capture":
        return asyncio.run(_cmd_capture(args))
    if args.command == "freeze":
        return _cmd_freeze(args)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
