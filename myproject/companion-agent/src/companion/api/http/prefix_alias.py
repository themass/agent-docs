"""对外 URL 前缀别名：``/v1/...`` 是正式路径，``/api/agent/v1/...`` 保留兼容。

为什么要在 ASGI 层做，而不是把每个 router 的 ``prefix`` 改掉：

- 九个 router 各自写死了 ``PREFIX = "/api/agent/v1"``，逐个改成参数会让
  「同一个路径有多长」散播到九个文件、所有构造函数和所有测试里；
- 而且改名期间必须让已安装的客户端继续可用——它们在公网上跑着旧版本，
  一改前缀就是全量客户端同时 404。

所以这里只做一次**路径重写**：进来是 ``/v1/x``，就当 ``/api/agent/v1/x`` 处理。
同一份路由、同一套处理器，没有第二份实现，也就不存在「两套互相影响」。

将来的收敛方向：内部前缀改为 ``/v1``，这里只保留反向别名
（``/api/agent/v1`` → ``/v1``），再观察一个版本后删除。
"""

from __future__ import annotations

CANONICAL = "/v1"
LEGACY = "/api/agent/v1"


class PrefixAliasMiddleware:
    """把 ``/v1/*`` 改写成 ``/api/agent/v1/*``。只改 path 与 raw_path，不动 query。"""

    def __init__(self, app, *, canonical: str = CANONICAL, target: str = LEGACY) -> None:
        self.app = app
        self._canonical = canonical.rstrip("/")
        self._target = target.rstrip("/")

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            path = scope.get("path", "")
            if path == self._canonical or path.startswith(self._canonical + "/"):
                rest = path[len(self._canonical):]
                scope = dict(scope)
                scope["path"] = self._target + rest
                raw = scope.get("raw_path")
                if raw:
                    scope["raw_path"] = self._target.encode() + raw[len(self._canonical):]
                # 让下游日志/审计看到的是客户端真实请求的路径
                headers = list(scope.get("headers") or [])
                headers.append((b"x-forwarded-path", path.encode()))
                scope["headers"] = headers
        await self.app(scope, receive, send)
