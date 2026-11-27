"""组装点共用的 Redis 客户端工厂：带超时的 ``from_url``。

为什么要有这个文件：redis-py 的 ``from_url`` 默认 ``socket_timeout`` /
``socket_connect_timeout`` 全是 ``None``——**任何一次 await 都可以永久阻塞**。
2026-11-28 生产挂死里，回合之所以能「永不终结」，链路每一段都没有时间闸，
其中 Redis 这一段最隐蔽：持锁的回合任务卡在 ``publish_and_append`` /
``read_ctl_after`` / ``_watch_ctl`` 的 ``xread`` 上，锁靠续租一直"活着"，
终止事件永远发不出去，客户端只能等自己的超时。

超时怎么取值（读侧已有自己的 BLOCK 常量，别和命令级超时打架）：

- ``REDIS_CONNECT_TIMEOUT_SEC = 5``：建连失败要快速失败（DNS/TCP 不通没有等的价值）。
- ``REDIS_SOCKET_TIMEOUT_SEC = 8``：单条命令的 socket 读超时。托管 Redis 单命令实测
  百毫秒量级（尖峰 ~200 ms），8 秒已经留出 40 倍余量；同时必须严格大于读侧最长的
  阻塞读 ``BLOCK_MS = 4000``（SSE 的 ``wait_events``，见 api/sse/stream.py 的来历注释：
  托管 Redis 约 5 秒掐断空闲连接，读侧刻意只阻塞 4 秒），否则一次正常的空等会被
  自己的超时掐断。``_watch_ctl`` 的 500 ms 更远在其下。

注意 ``xread(block=4000)`` 这类阻塞命令走的是同一个 socket_timeout：4000 < 8000，
阻塞等待正常返回，不会抛 TimeoutError。真正的 Redis 挂死则在 8 秒处断开，
由调用方（回合的异常路径 / SSE 的重连循环）接手。
"""

from __future__ import annotations

from typing import Any

REDIS_CONNECT_TIMEOUT_SEC = 5.0
REDIS_SOCKET_TIMEOUT_SEC = 8.0


def redis_client_from_url(url: str, *, decode_responses: bool = False, **kwargs: Any) -> Any:
    """带连接/命令超时的 ``redis.asyncio.from_url``。

    所有组装点都要经这里建 Redis 客户端（源码扫描测试守着这条约定）。
    ``decode_responses`` 必须显式传：回合控制面要 bytes（Lua/APPEND 语义），
    登录态与房间存储要 str——工厂不替调用方决定。
    """
    from redis import asyncio as redis_async

    kwargs.setdefault("socket_connect_timeout", REDIS_CONNECT_TIMEOUT_SEC)
    kwargs.setdefault("socket_timeout", REDIS_SOCKET_TIMEOUT_SEC)
    return redis_async.from_url(url, decode_responses=decode_responses, **kwargs)
