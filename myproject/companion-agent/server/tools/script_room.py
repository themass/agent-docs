"""剧本房 CLI：lease.attach → agent JWT → LiveKitRtcAdapter → run_script_room。

用法（在 server/ 目录）::

    uv run python -m tools.script_room run --case barge_mid_sentence
    uv run python -m tools.script_room run --case multi_seg --tts volcengine
    uv run python -m tools.script_room run --case barge_mid_sentence --url wss://...

默认 TTS 为 fake（本地无网络）；``--tts volcengine`` 才走真实合成。
不 import 生产 agent 入口（companion.worker / companion.agent.entry）。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from companion.paths import SERVER_ROOT
from companion.worker import load_env

CASES_DIR = SERVER_ROOT / "cases" / "voice"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tools.script_room", description="剧本房 CLI runner")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="跑一个 YAML case 推到 LiveKit 剧本房")
    run.add_argument("--case", required=True, help="cases/voice/{id}.yaml 的 id，如 barge_mid_sentence")
    run.add_argument(
        "--url",
        default=None,
        help="LiveKit ws URL；默认读 Settings.livekit_url / LIVEKIT_URL",
    )
    run.add_argument(
        "--tts",
        choices=("fake", "volcengine"),
        default="fake",
        help="TTS 供应商（默认 fake）",
    )
    run.add_argument(
        "--wait",
        type=float,
        default=120.0,
        help="等手机入房超时秒数（默认 120）",
    )
    return parser


def _case_path(case_id: str) -> Path:
    path = CASES_DIR / f"{case_id}.yaml"
    if not path.is_file():
        raise SystemExit(f"case 不存在: {path}")
    return path


def _make_lease(settings):
    """与 API bootstrap 同策略：有 Redis 就共享；否则进程内内存（仅本 CLI 可见）。"""
    from companion.devtools.script_room.lease import InMemoryScriptRoomLease, RedisScriptRoomLease

    url = (getattr(settings, "companion_redis_url", "") or "").strip()
    if url:
        from redis import asyncio as redis_async

        return RedisScriptRoomLease(redis_async.from_url(url, decode_responses=True))
    print(
        "warn: 无 companion_redis_url，使用进程内 lease；"
        "手机 createScriptSession 若走另一进程的 Redis/内存，可能进不到同一房间",
        file=sys.stderr,
    )
    return InMemoryScriptRoomLease()


def _make_tts(kind: str):
    if kind == "fake":
        from companion.service.voice.fake import FakeVoiceProvider

        return FakeVoiceProvider(), "fake"
    from companion.service.voice.volcengine import VolcengineConfig, VolcengineProvider

    return VolcengineProvider(config=VolcengineConfig.from_env()), "volcengine"


async def _run(args: argparse.Namespace) -> int:
    # Settings / 适配器读 os.environ；先 load_env 再 import 依赖配置的模块
    load_env()

    from companion.config import settings
    from companion.devtools.script_room.case_schema import load_case
    from companion.devtools.script_room.runner import run_script_room
    from companion.devtools.script_room.rtc import LiveKitRtcAdapter
    from companion.service.room.livekit_tokens import TokenMinter
    from companion.service.voice.port import VoiceRef

    case = load_case(_case_path(args.case))
    url = (args.url or settings.livekit_url or "").strip()
    if not url:
        raise SystemExit("LIVEKIT_URL / --url 未配置")

    lease = _make_lease(settings)
    room = await lease.attach(case.id)
    if not room.startswith("script-"):
        raise SystemExit(f"lease 返回非法房间名: {room}")

    minter = TokenMinter.from_settings(settings)
    agent_id = f"script-{case.id}"
    minted = minter.agent_token(agent_id, room)

    tts, tts_name = _make_tts(args.tts)
    voice_ref = VoiceRef(provider=tts_name, voice_id="script")

    print(f"room: {room}")
    print(f"phone: createScriptSession(case={case.id!r})  # 同 case 会师此房间")
    print(f"tts: {tts_name}  agent={minted.identity}  url={url}")
    print("waiting for phone hello…", flush=True)

    rtc = LiveKitRtcAdapter()
    try:
        timeline = await run_script_room(
            case=case,
            url=url,
            token=minted.token,
            tts=tts,
            wait_timeout_sec=args.wait,
            rtc=rtc,
            voice_ref=voice_ref,
        )
    finally:
        await rtc.close()

    print("timeline:")
    for i, name in enumerate(timeline):
        print(f"  {i:02d}  {name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return asyncio.run(_run(args))
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
