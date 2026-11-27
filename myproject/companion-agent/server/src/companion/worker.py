"""worker 进程：把 entrypoint 交给 LiveKit 的 CLI 跑。

`WorkerOptions` 与 `cli.run_app` 是 LiveKit Agents 的标准启动方式；我们只提供装配，
不自己写调度——重连、并发、优雅退出都由框架负责，自己实现只会在边界情况下出错。
"""

from __future__ import annotations

import logging
import os
import sys

from companion.config import settings
from companion.paths import ENV_FILE


def load_env(path=None) -> int:
    """把 ``.env`` 里的变量载入进程环境，已存在的环境变量优先（部署时由平台注入的值不能被文件盖掉）。

    为什么需要：``Settings``（pydantic）会读 ``.env``，但语音适配器、LiveKit 的 CLI 直接读 ``os.environ``。
    不加载的话，配置在文件里写着、进程里却读不到，表现是音色和供应商悄悄退回默认值，很难查。
    返回新载入的变量个数。
    """
    from dotenv import dotenv_values

    values = dotenv_values(path or ENV_FILE)
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

    stage-6：``build_platform`` 仍是同步的重装配（含大脑图），但角色目录在 prewarm 里
    已进程级缓存；装配本身 ``asyncio.to_thread``，避免在接房关键路径上冻事件循环 10s+。

    ``AsyncPostgresSaver`` 构造时要 ``asyncio.get_running_loop()``——必须在事件循环里建，
    不能跟着 ``build_platform`` 进线程池（stage-6 回归）。
    """
    import asyncio

    from companion.bootstrap.catalog_cache import get_system_catalog, warm_system_catalog
    from companion.bootstrap.database import profile_for
    from companion.bootstrap.platform import _checkpointer, build_platform, default_prompts
    from companion.config import settings

    if not (settings.database_url and settings.companion_redis_url):
        raise RuntimeError("语音 worker 需要 COMPANION_DATABASE_URL 与 COMPANION_REDIS_URL（与 HTTP 服务相同）")
    catalog = get_system_catalog() or warm_system_catalog()

    checkpoint_bundle = None
    if settings.checkpoint_url:
        checkpoint_bundle = _checkpointer(settings.checkpoint_url, profile_for("voice"))

    def _build() -> object:
        return build_platform(
            settings,
            prompts=default_prompts(),
            catalog=catalog,
            profile="voice",
            checkpoint_bundle=checkpoint_bundle,
        )

    # 每个房间一个任务进程，各自一份连接池：用最小的档，同时在线的房间多了也不会占满数据库
    return await asyncio.to_thread(_build)


def main() -> None:
    load_env()      # 要在读任何语音配置之前
    logging.basicConfig(level=settings.companion_log_level)
    # 8082 也直接对公网：aiohttp 健康检查端口每天被 PRI/垃圾字节打，整段堆栈刷 voice.log
    from companion.observability.noise import attach_noise_filter

    attach_noise_filter()
    # 语音链路也会出站调第三方（高德、TTS）：httpx 的 INFO 带整条 URL，key 在 query 里
    from companion.observability.log_safety import pin_third_party_log_levels

    pin_third_party_log_levels()
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
    # 质检记录里的供应商与音色：**这里只是兜底**。真正记的那一份由入口按房间说话人改写
    # （``VoiceWiring.info_for``）——音色跟着角色走，不是进程级配置。
    voice_info = {"stt_provider": cfg.provider, "tts_provider": cfg.provider,
                  "tts_voice": cfg.voice_id or os.environ.get("VOLC_TTS_VOICE", "saturn_zh_female_keainvsheng_tob")}
    from companion.bootstrap.voice_wiring import voice_wiring

    # 角色来源：入口把房间的 character_id 解析成 voice_ref。挂上平台后它用平台的读取链
    # （库里的系统包优先、随包文件兜底）——与 HTTP 目录同一份封装，
    # 「页面上显示的这个角色」和「语音里说话的这个声音」因此不会分家。
    entry = make_entrypoint(_platform, voice_factory=build_voice_stack,
                            wire_voice=voice_wiring(voice_info))
    from companion.api.livekit.capacity import worker_options_kwargs
    from companion.api.livekit.prewarm import prewarm

    # LiveKit 的 CLI 是子命令式的（start / dev / console / download-files），
    # 不带子命令时它只打印帮助然后退出——进程"启动成功"却什么都没做，日志里只有一段 usage。
    # 部署脚本和 `./run.sh voice` 都是不带参数的，所以这里补上 start；本地调试仍可显式传 dev。
    if len(sys.argv) == 1:
        sys.argv.append("start")

    # 按房间数限流：默认按 CPU 判断的话语音 agent 永远“不满”，房间会把数据库连接占满。
    # port 是 worker 自己的健康检查端口：SDK 生产模式默认 8081，和 api 撞车（两个进程都在本机时
    # 后起的那个绑不上就退出），所以由配置单独给一个。
    # 预热：job 进程一启动就把首帧必经的重 import（botocore 那条 11.8s 的链）做完，
    # 而不是等第一个房间的第一次调用在事件循环里干——那时用户已经在等首帧了。
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entry,
        prewarm_fnc=prewarm,
        **worker_options_kwargs(settings.companion_voice_max_rooms, port=settings.companion_voice_worker_port)))


if __name__ == "__main__":
    main()
