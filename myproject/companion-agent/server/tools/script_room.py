"""剧本房 CLI：lease.attach → agent JWT → LiveKitRtcAdapter → run_script_room。

用法（在 server/ 目录）::

    uv run python -m tools.script_room run --case barge_mid_sentence
    uv run python -m tools.script_room run --case multi_seg --tts volcengine
    uv run python -m tools.script_room run --case barge_mid_sentence --url wss://...
    uv run --extra dev --extra livekit python -m tools.script_room run --case image_reply --tts fake --wait 180

默认 TTS 为 fake（本地无网络）；``--tts volcengine`` 才走真实合成。
case YAML 的 ``mode`` 决定跑法：``push``（默认）等手机入房、把台词推给它；
``real_turn`` 由 CLI 自己在房里同时扮演 agent 与用户，走生产装配 + 真模型（见
``companion.devtools.script_room.real_turn``）。``--tts`` 只作用于 push 模式。
不 import 生产 agent 入口（companion.worker / companion.agent.entry）——
real_turn 用的是 ``bootstrap.platform``（组合根本身），不是 worker 的语音入口。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
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
        help="等手机入房 + control.hello 的超时秒数（默认 120；两段共用）",
    )
    run.add_argument(
        "--no-image",
        action="store_true",
        help="real_turn 负对照：装配、文字、模型、门禁全不变，只不发 control.input"
             "(kind=attachments)。断言反转成「关键词族零命中 + submit 没收到附件」，"
             "用来证明正向那条的命中不是模型的条件反射。",
    )
    return parser


def _case_path(case_id: str) -> Path:
    path = CASES_DIR / f"{case_id}.yaml"
    if not path.is_file():
        raise SystemExit(f"case 不存在: {path}")
    return path


async def cleanup_fixture_object(platform, key: str) -> str:
    """跑完删掉本次的 fixture 对象，返回一句给控制台的话。

    桶卫生：fixture 是可再生的测试产物，跑完就删；只删本次运行的那一个 key，
    会话与消息留在库里当运行证据（``ca_chat_*`` 本来就是测试/开发共用的库）。
    负对照不上传图，``key`` 是空串——没东西要删，也别拿空 key 去删。

    守卫查的必须是**真正调用的那个对象**（``objects``）而不是 ``uploads``：原来查
    ``uploads`` 却调 ``objects.delete``，两者在对象存储降级时一起变 None
    （见 ``build_platform``），所以那时侥幸没事；但 ``uploads`` 存在而 ``objects``
    缺的组合会拿到 ``AttributeError: 'NoneType' object has no attribute 'delete'``。
    清理失败也不能盖住跑测结果，所以异常只警告。
    """
    if not key:
        return "cleanup: 本次没有上传对象（负对照），无需删除"
    if platform.objects is None:
        return f"warn: 对象存储不可用（objects=None），fixture 对象 {key} 留在桶里"
    try:
        await platform.objects.delete(key=key)
        return f"cleanup: deleted object {key}"
    except Exception as exc:  # noqa: BLE001 — 清理失败只警告，不能盖住跑测结果
        return f"warn: cleanup 失败（key={key}）: {exc}"


def ensure_no_image_matches_mode(mode: str, no_image: bool) -> None:
    """``--no-image`` 只对 ``mode: real_turn`` 的 case 有意义，别的模式当场报错。

    这个开关注册在共享的 ``run`` 子命令上，但只有 ``_run_real_turn`` 读它。push 模式压根
    没有附件路径（台词是 CLI 自己推的），带上 ``--no-image`` 跑过去就是**静默无效**：
    跑的人以为自己做了一次负对照，实际只跑了一遍正向。与仓库里「无意义绿灯」同一个形状，
    所以宁可当场红一次。
    """
    if no_image and mode != "real_turn":
        raise SystemExit(f"--no-image 对 mode: {mode} 的 case 无效"
                         "（push 模式没有附件路径，这条开关会被静默忽略）")


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


async def _run_push(args, case, settings, lease, minter) -> int:
    """push 模式：CLI 当推流 agent，等**手机**入房发 hello。原有行为，原样搬进来。"""
    room = await lease.attach(case.id)
    if not room.startswith("script-"):
        raise SystemExit(f"lease 返回非法房间名: {room}")

    agent_id = f"script-{case.id}"
    minted = minter.agent_token(agent_id, room)

    from companion.devtools.script_room.runner import run_script_room
    from companion.devtools.script_room.rtc import LiveKitRtcAdapter
    from companion.service.voice.port import VoiceRef

    tts, tts_name = _make_tts(args.tts)
    voice_ref = VoiceRef(provider=tts_name, voice_id="script")

    url = args.url_or_settings
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
            # 真机 Intent 冷启动：入房后还要走 createScriptSession→connect→hello，
            # 不能卡在 LEGACY_WAIT_SECONDS(3s)；与 --wait 共用预算。
            hello_timeout_sec=args.wait,
            rtc=rtc,
            voice_ref=voice_ref,
        )
    finally:
        await rtc.close()

    print("timeline:")
    for i, name in enumerate(timeline):
        print(f"  {i:02d}  {name}")
    return 0


async def _run_real_turn(args, case, settings, lease, minter) -> int:
    """real_turn 模式：CLI 同时在房里扮演 agent 与用户两个 participant，中间是真装配真模型。

    需要 ``.env`` 里的全套真环境（DB/Redis/LLM 网关/TOS/LiveKit）——这条 case 的意义
    就在于它走的是生产的那条装配，缺任何一环都该红，不该假绿。

    ``--no-image`` 走**同一条装配**但不发 ``control.input(kind=attachments)``，
    断言反转：关键词族必须**零**命中，且 ``submit`` 必须**没有**收到附件。
    这两条合起来才是「关键词命中 ⇔ 图真的进了模型」的可复现证伪——
    只有正向的绿灯说明不了命中不是模型对「照片里有什么？」这句话的条件反射。
    """
    from companion.bootstrap.platform import build_platform, default_prompts
    from companion.agent.memory.fake import InMemoryMemoryPort
    from companion.devtools.script_room.real_turn import (
        keyword_hits,
        negative_control_problems,
        run_real_turn,
    )
    from companion.devtools.script_room.rtc import LiveKitRtcAdapter

    room = await lease.attach(case.id)
    if not room.startswith("script-"):
        raise SystemExit(f"lease 返回非法房间名: {room}")

    # 回合主人用一个跑得动的数字 id：ca_chat_message.owner_id 是 BIGINT，
    # AuthVerifier 在生产里保证登录态是正整数。剧本房没有登录态，就自己造一个
    # 每次运行都新鲜的（同一进程/同一天的重复跑不会撞别人的会话历史）。
    owner_id = int(time.time()) % 10**11

    url = args.url_or_settings
    user_token = minter.user_token(str(owner_id), room)
    agent_token = minter.agent_token(f"script-{case.id}", room)

    print(f"room: {room}")
    print(f"real_turn: owner={owner_id} agent={agent_token.identity} user={user_token.identity}")
    print(f"fixture: {case.real_turn.fixture}  text: {case.real_turn.text!r}")
    if args.no_image:
        print("mode: NEGATIVE CONTROL (--no-image) — 不发 attachments 事件，断言取反")
    print("building platform (real brain, real turn stack)…", flush=True)

    platform = build_platform(settings, prompts=default_prompts(), memory_port=InMemoryMemoryPort())
    await platform.astart()

    agent_rtc = LiveKitRtcAdapter()
    user_rtc = LiveKitRtcAdapter()
    key = None
    try:
        result = await run_real_turn(
            case=case,
            url=url,
            agent_token=agent_token.token,
            user_token=user_token.token,
            owner_id=owner_id,
            platform=platform,
            agent_rtc=agent_rtc,
            user_rtc=user_rtc,
            room=room,
            wait_timeout_sec=args.wait,
            with_image=not args.no_image,
        )
        key = result.object_key
    finally:
        await agent_rtc.close()
        await user_rtc.close()
        # 桶卫生与「查哪个对象」见 ``cleanup_fixture_object``。清理的话走 stderr，
        # 不能盖住跑测结果。
        print(await cleanup_fixture_object(platform, key))
        await platform.aclose()

    print("timeline:")
    for i, name in enumerate(result.timeline):
        print(f"  {i:02d}  {name}")
    print(f"session: {result.session_id}  turn: {result.turn_id}  upload: {result.upload_id or '-'}")
    print("speech.seg texts:")
    for text in result.seg_texts:
        print(f"  - {text}")
    if result.stored_reply:
        print(f"stored assistant reply: {result.stored_reply!r}")
    print(f"submit attachments: {result.submit_attachments!r}")

    family = case.real_turn.keyword_family
    hits = keyword_hits(family, result.seg_texts)
    if args.no_image:
        # 断言取反。三条都要成立（见 ``negative_control_problems``）：零命中、**submit
        # 真的被调用过**、且它没收到附件。只验「零命中」的话，一条没走到 submit 的空回合
        # 也能骗绿——那种绿灯证明的是「什么都没发生」。
        problems = negative_control_problems(hits=hits, submit_attachments=result.submit_attachments,
                                             seg_texts=result.seg_texts)
        if problems:
            for problem in problems:
                print(f"FAIL(负对照): {problem}", file=sys.stderr)
            return 1
        print(f"\nPASS(负对照): 不带图时关键词族 {list(family)} 零命中，"
              "且 submit 被调用但没收到任何附件 → 正向那条的命中确实来自图")
        return 0

    if not hits:
        print(f"\nFAIL: 回复没有命中图内要素关键词族 {list(family)} 中任何一个", file=sys.stderr)
        return 1
    if not any(result.submit_attachments):
        print("\nFAIL: 关键词命中了，但 submit 没收到附件——图根本没进模型，"
              "命中是泛词或条件反射", file=sys.stderr)
        return 1
    print(f"\nPASS: 关键词族命中 {hits}（族={list(family)}），且 submit 收到了附件")
    return 0


async def _run(args: argparse.Namespace) -> int:
    """按 case 的 ``mode`` 分派：push（等手机、推台词）或 real_turn（真装配真模型）。"""
    # Settings / 适配器读 os.environ；先 load_env 再 import 依赖配置的模块
    load_env()

    from companion.config import settings
    from companion.devtools.script_room.case_schema import MODE_REAL_TURN, load_case
    from companion.service.room.livekit_tokens import TokenMinter

    case = load_case(_case_path(args.case))
    ensure_no_image_matches_mode(case.mode, args.no_image)
    url = (args.url or settings.livekit_url or "").strip()
    if not url:
        raise SystemExit("LIVEKIT_URL / --url 未配置")
    args.url_or_settings = url

    lease = _make_lease(settings)
    minter = TokenMinter.from_settings(settings)

    if case.mode == MODE_REAL_TURN:
        return await _run_real_turn(args, case, settings, lease, minter)
    return await _run_push(args, case, settings, lease, minter)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return asyncio.run(_run(args))
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
