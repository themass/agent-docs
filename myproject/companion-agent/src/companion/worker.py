"""worker 进程：把 entrypoint 交给 LiveKit 的 CLI 跑。

`WorkerOptions` 与 `cli.run_app` 是 LiveKit Agents 的标准启动方式；我们只提供装配，
不自己写调度——重连、并发、优雅退出都由框架负责，自己实现只会在边界情况下出错。
"""

from __future__ import annotations

import logging
import os

from companion.config import PROJECT_ROOT, settings


def load_env(path=None) -> int:
    """把 ``.env`` 里的变量载入进程环境，已存在的环境变量优先（部署时由平台注入的值不能被文件盖掉）。

    为什么需要：``Settings``（pydantic）会读 ``.env``，但语音适配器、LiveKit 的 CLI 直接读 ``os.environ``。
    不加载的话，配置在文件里写着、进程里却读不到，表现是音色和供应商悄悄退回默认值，很难查。
    返回新载入的变量个数。
    """
    from dotenv import dotenv_values

    values = dotenv_values(path or (PROJECT_ROOT / ".env"))
    loaded = 0
    for name, value in values.items():
        if value is not None and name not in os.environ:
            os.environ[name] = value
            loaded += 1
    return loaded


def _export_livekit_env() -> None:
    """把配置写回进程环境变量。

    LiveKit 的 CLI 自己读 ``os.environ["LIVEKIT_URL"]`` 等变量，不认我们的
    ``.env``（那是 pydantic 读的）。不导出的话，worker 会在启动时报
    ``ws_url is required``——配置明明有值却起不来，很难查。
    已存在的环境变量优先，不覆盖。
    """
    import os

    for name, value in (
        ("LIVEKIT_URL", settings.livekit_url),
        ("LIVEKIT_API_KEY", settings.livekit_api_key),
        ("LIVEKIT_API_SECRET", settings.livekit_api_secret),
    ):
        if value and not os.environ.get(name):
            os.environ[name] = value


async def _platform():
    """语音 worker 用的 platform：与 HTTP 服务同一套（同库、同 Redis、同回合引擎）。

    以前这里单独造一个大脑并在配置不全时退回 FakeBrain：房间能进、能听能说，回答却是
    写死的假话，而且说过的话不落库。现在没有数据库 / Redis 就直接拒绝启动，不降级。
    """
    from companion.bootstrap.platform import build_platform, default_prompts
    from companion.config import settings

    if not (settings.database_url and settings.companion_redis_url):
        raise RuntimeError("语音 worker 需要 COMPANION_DATABASE_URL 与 COMPANION_REDIS_URL（与 HTTP 服务相同）")
    # 每个房间一个任务进程，各自一份连接池：用最小的档，同时在线的房间多了也不会占满数据库
    return build_platform(settings, prompts=default_prompts(), profile="voice")


def main() -> None:
    load_env()      # 要在读任何语音配置之前
    logging.basicConfig(level=settings.companion_log_level)
    log = logging.getLogger("companion.worker")

    if not (settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret):
        log.error("缺少 LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET，无法启动 worker")
        raise SystemExit(2)
    _export_livekit_env()

    from companion.api.livekit.bridge import require

    require()

    from livekit.agents import WorkerOptions, cli

    from companion.api.livekit.entrypoint import make_entrypoint
    from companion.bootstrap.voice_stack import build_voice_stack

    from companion.bootstrap.voice_stack import config_from_env

    cfg = config_from_env()
    # 质检记录里的供应商与音色：取自实际装配的配置，不靠事后猜
    voice_info = {"stt_provider": cfg.provider, "tts_provider": cfg.provider,
                  "tts_voice": cfg.voice_id or os.environ.get("VOLC_TTS_VOICE", "saturn_zh_female_keainvsheng_tob")}
    from companion.bootstrap.voice_wiring import voice_wiring

    entry = make_entrypoint(_platform, voice_factory=build_voice_stack, wire_voice=voice_wiring(voice_info))
    from companion.api.livekit.capacity import worker_options_kwargs

    # 按房间数限流：默认按 CPU 判断的话语音 agent 永远“不满”，房间会把数据库连接占满
    cli.run_app(WorkerOptions(entrypoint_fnc=entry, **worker_options_kwargs(settings.companion_voice_max_rooms)))


if __name__ == "__main__":
    main()
