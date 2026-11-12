"""worker 进程：把 entrypoint 交给 LiveKit 的 CLI 跑。

`WorkerOptions` 与 `cli.run_app` 是 LiveKit Agents 的标准启动方式；我们只提供装配，
不自己写调度——重连、并发、优雅退出都由框架负责，自己实现只会在边界情况下出错。
"""

from __future__ import annotations

import logging

from companion.config import settings


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


def _container():
    """语音 worker 用的容器：有模型网关配置就用 DeerFlow，否则退回 FakeBrain。

    以前这里固定 ``create_container()``，默认 ``FakeBrain``——worker 连上了、能听能说，
    但回答是写死的假话。这类「看起来能跑」的降级比直接失败更难查，所以这里显式选，
    并在用假大脑时打一条警告。
    """
    import logging

    from companion.bootstrap.container import create_container

    log = logging.getLogger("companion.worker")
    try:
        from companion.bootstrap.voice_brain import build_voice_brain

        brain = build_voice_brain()
        log.info("voice brain: DeerFlow")
        return create_container(brain=brain)
    except Exception as exc:  # noqa: BLE001 —— 配置不全时明确降级，并让人看得见
        log.warning("DeerFlow 不可用，语音回合使用 FakeBrain（回答是假的）：%s", exc)
        return create_container()


def main() -> None:
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
    from companion.bootstrap.container import create_container
    from companion.bootstrap.voice_stack import build_voice_stack

    entry = make_entrypoint(_container(), voice_factory=build_voice_stack)
    cli.run_app(WorkerOptions(entrypoint_fnc=entry))


if __name__ == "__main__":
    main()
