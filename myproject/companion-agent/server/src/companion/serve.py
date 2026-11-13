"""进程入口：带优雅停机的 uvicorn（P §3.5）。

收到第一次退出信号：置 draining（新发送 503，SSE 发 reconnect），等回合收尾至多 45 秒，
再交给 uvicorn 原本的 handle_exit。第二次信号立即退出。
"""

from __future__ import annotations

import asyncio
import os
import signal

import uvicorn

from companion.chat.lifecycle import DrainState

GRACE_SECONDS = 45.0


class DrainingServer(uvicorn.Server):
    def __init__(self, config: uvicorn.Config, drain: DrainState, grace: float = GRACE_SECONDS) -> None:
        super().__init__(config)
        self._drain = drain
        self._grace = grace

    def handle_exit(self, sig: int, frame) -> None:  # noqa: ANN001 — uvicorn 签名
        if self._drain.draining:
            return super().handle_exit(sig, frame)
        self._drain.begin()
        asyncio.get_event_loop().create_task(self._graceful_exit(sig, frame))

    async def _graceful_exit(self, sig: int, frame) -> None:  # noqa: ANN001
        await self._drain.wait_idle(self._grace)
        super().handle_exit(sig, frame)


def build_app():
    """配置了数据库与 Redis 时用新聊天栈（/api/agent/v1，Postgres checkpoint + DeerFlow 大脑）；
    否则退回旧的进程内链路（只用于本地开发）。"""
    from companion.bootstrap.app import create_app
    from companion.config import settings

    if settings.database_url and settings.companion_redis_url:
        from companion.bootstrap.platform import build_platform, default_prompts

        platform = build_platform(settings, prompts=default_prompts())
        return create_app(platform=platform)
    return create_app()


class LoopBuiltServer(DrainingServer):
    """在事件循环里构建 app 的 server。

    为什么要这样：``build_platform()`` 会构造 ``AsyncPostgresSaver``，它的
    ``__init__`` 调用 ``asyncio.get_running_loop()``。而 ``build_app()`` 是同步函数，
    以前在 ``main()`` 里先构建、再把 app 交给 ``server.run()``——那时还没有事件循环，
    进程直接抛 ``RuntimeError: no running event loop``。

    只有配置了 Postgres checkpoint（即生产配置）才会触发，所以本地不配库跑测试时发现不了。
    uvicorn 的 ``_serve`` 本身就是协程，在它开头构建 app 即可，不用改 uvicorn 的加载方式。
    """

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        # 先给父类一个占位 config；真正的 app 在 _serve 里构建后替换
        super().__init__(uvicorn.Config(_placeholder_app(), host=host, port=port, log_config=None), None)  # type: ignore[arg-type]

    async def _serve(self, sockets: list | None = None) -> None:
        app = build_app()
        self.config = uvicorn.Config(app, host=self._host, port=self._port, log_config=None)
        self._drain = app.state.companion.drain  # type: ignore[attr-defined]
        await super()._serve(sockets=sockets)

    def handle_exit(self, sig: int, frame) -> None:  # noqa: ANN001
        drain = getattr(self, "_drain", None)
        if drain is None or drain.draining:
            return super().handle_exit(sig, frame)
        drain.begin()
        asyncio.get_event_loop().create_task(self._graceful_exit(sig, frame))


def _placeholder_app():
    """父类构造时要求一个 app；它永远不会被真正服务（_serve 会替换 config）。"""
    from fastapi import FastAPI

    return FastAPI()


def main() -> None:
    host = os.environ.get("COMPANION_HOST", "127.0.0.1")
    port = int(os.environ.get("COMPANION_PORT", "8081"))
    LoopBuiltServer(host, port).run()


if __name__ == "__main__":
    main()
