"""一个进程、一个端口：BFF + 控制桥 + worker。

原设计把它们拆成三个进程、发六把令牌，为的是隔离「AI 不能自批自落」。
2026-11-28 用户定案：**合并成一个进程，内部令牌共用一把**。人工审稿这道闸没有动——
批准仍然只有登录进来的审阅人按得动；去掉的是「三个服务互不信任」这一层假设。

本模块没有业务代码：把 worker 与控制桥挂进 BFF 现有的 app，同一个端口。

    /                    BFF 原有全部路由（对 Studio）
    /_bridge/*           poetry-domain-mcp（原独立 :8101）
    /_worker/*           agent-worker（原独立 :8102）

`/_*` 从公网打不到：nginx 的 studio vhost 只把 `/api/poetry/v1/agent/**` 转进来。
BFF 的 POETRY_DOMAIN_CONTROL_URL / POETRY_WORKER_URL 因此指回自己
（http://127.0.0.1:8100/_bridge、…/_worker）——走回环一圈，省掉两个进程。

`Mount` 不向被挂载的应用转发 lifespan（poetry_domain_mcp.server 里有过同款事故注释），
所以 worker 的线程池关闭与 MCP 会话管理器的 task group 都要在这里显式进出。
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from agent_worker.app import create_app as create_worker_app
from poetry_domain_mcp.server import build_app as build_bridge_app

from agent_bff import main as bff_main                # import 副作用：建好 app 与全部路由


def wire() -> None:
    """把 worker 与桥挂进 BFF 的 app，并接管它的 lifespan。"""
    worker_app = create_worker_app()
    bridge = build_bridge_app()                       # InternalMcpAuth(Starlette)
    bridge_inner = bridge.app                         # 带 lifespan 的那层

    bff_main.app.mount("/_worker", worker_app)
    bff_main.app.mount("/_bridge", bridge)

    @asynccontextmanager
    async def lifespan(_app) -> object:
        async with worker_app.router.lifespan_context(worker_app):
            async with bridge_inner.router.lifespan_context(bridge_inner):
                yield

    bff_main.app.router.lifespan_context = lifespan


wire()
app = bff_main.app


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    import uvicorn

    port = int(os.getenv("PORT", "8100"))
    logging.getLogger("allinone").info("单进程 agent 栈 :%s（bff / _bridge / _worker）", port)
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=port, log_level="info")


if __name__ == "__main__":
    run()
