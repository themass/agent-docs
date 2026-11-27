"""出站到 Redis / TOS 的客户端必须带超时。

2026-11-28 生产挂死排查：回合之所以能**永不**终结，是因为链路上每一段 await 都没有
时间闸——其中最容易修、也最难在日志里看出来的两处是：

- ``redis_async.from_url(...)`` 不带 ``socket_timeout`` / ``socket_connect_timeout``
  （redis-py 默认 ``None`` = 永久等待）。任何一个 Redis await（``publish_and_append``、
  ``read_ctl_after``、``_watch_ctl`` 的 ``xread``）都能永久阻塞，而阻塞发生在持锁的
  回合任务里：锁靠续租活着，终止事件永远发不出去，SSE 那头只能等自己的超时。
- ``boto3`` 的 ``Config`` 只有 ``addressing_style``，连接/读取超时同样是默认值
  （connect 60s、read 60s，重试再乘一遍）。附件读字节挂在 ``asyncio.to_thread`` 里，
  回合跟着一起挂。

这里钉住「构造出来的客户端带超时」，并且钉住超时和读侧 BLOCK 常量的关系
（socket_timeout 必须大于最长阻塞读，否则正常等待会被自己的超时掐断）。
"""

from __future__ import annotations

import boto3
import pytest

# ---------------------------------------------------------------- Redis ----


def test_redis_client_carries_socket_and_connect_timeouts():
    from companion.bootstrap.redis_client import (
        REDIS_CONNECT_TIMEOUT_SEC,
        REDIS_SOCKET_TIMEOUT_SEC,
        redis_client_from_url,
    )

    client = redis_client_from_url("redis://localhost:6379/0")
    kwargs = client.get_connection_kwargs()
    assert kwargs["socket_timeout"] == REDIS_SOCKET_TIMEOUT_SEC
    assert kwargs["socket_connect_timeout"] == REDIS_CONNECT_TIMEOUT_SEC
    # 默认值（None / 没设）就是「永久阻塞」，这条断言是这个测试存在的理由本身。
    assert kwargs["socket_timeout"] is not None
    assert kwargs["socket_connect_timeout"] is not None


def test_socket_timeout_exceeds_the_longest_blocking_read():
    """socket_timeout 必须严格大于最长的阻塞 XREAD，否则一次正常的空等就报 TimeoutError。

    读侧的两个 BLOCK 常量：SSE 的 ``BLOCK_MS``（4000 ms）与 ``_watch_ctl`` 的 500 ms。
    4000 这个值本身有来历（托管 Redis ~5 s 掐断空闲连接），所以不能反过来调小读侧迁就
    客户端——只能保证命令级超时留出余量。
    """
    from companion.api.sse.stream import BLOCK_MS
    from companion.bootstrap.redis_client import REDIS_SOCKET_TIMEOUT_SEC

    assert REDIS_SOCKET_TIMEOUT_SEC * 1000 > BLOCK_MS


def test_timeouts_are_bounded_constants_not_zero_or_huge():
    from companion.bootstrap.redis_client import (
        REDIS_CONNECT_TIMEOUT_SEC,
        REDIS_SOCKET_TIMEOUT_SEC,
    )

    assert 0 < REDIS_CONNECT_TIMEOUT_SEC <= 10
    assert 0 < REDIS_SOCKET_TIMEOUT_SEC <= 30


def test_decode_responses_is_passed_through():
    """回合控制面要 bytes（decode_responses=False），登录态/房间要 str：帮助函数不能吃掉这个开关。"""
    from companion.bootstrap.redis_client import redis_client_from_url

    raw = redis_client_from_url("redis://localhost:6379/0")
    text = redis_client_from_url("redis://localhost:6379/0", decode_responses=True)
    assert raw.get_connection_kwargs()["decode_responses"] is False
    assert text.get_connection_kwargs()["decode_responses"] is True


def test_no_bare_from_url_left_in_src():
    """组装点的 Redis 客户端一律经 ``redis_client_from_url``，不许再直接 ``from_url``。

    超时写在帮助函数里只有一半价值：``bootstrap`` 里还有三处直接 ``from_url``（房间存储、
    剧本房 lease、登录态验签），漏一处就等于那条链路仍然可以永久阻塞。用源码扫描把这个
    约定变成闸——新增组装点时必须显式经过帮助函数（或显式改这条测试并说明理由）。
    """
    import re
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src"
    offenders: list[str] = []
    pattern = re.compile(r"\bfrom_url\s*\(")
    for path in sorted(src.rglob("*.py")):
        if path.name == "redis_client.py":
            continue
        if pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(src)))
    assert offenders == [], f"直接 from_url 的组装点（无超时）: {offenders}"


# ----------------------------------------------------------------- TOS ----


def test_tos_client_config_carries_connect_and_read_timeouts():
    """TOS（S3 兼容）客户端必须有连接与读取超时。

    read 不能太小：``get`` 读的是模型要看的图片对象（可达几 MiB），公网几 MiB 的下载
    在慢链路上就要几十秒；太小会把正常附件读成失败。connect 要小：TCP 连不上要快速失败。
    """
    from companion.service.uploads.tos import (
        TOS_CONNECT_TIMEOUT_SEC,
        TOS_READ_TIMEOUT_SEC,
        TosObjectStore,
    )

    store = TosObjectStore(endpoint="https://tos-s3-cn-beijing.volces.com", bucket="b",
                           access_key="AK", secret_key="SK")
    cfg = store._client.meta.config
    assert cfg.connect_timeout == TOS_CONNECT_TIMEOUT_SEC
    assert cfg.read_timeout == TOS_READ_TIMEOUT_SEC
    assert 0 < TOS_CONNECT_TIMEOUT_SEC <= 10
    assert TOS_READ_TIMEOUT_SEC >= 10  # 读对象是整张图片，不是单条命令


def test_tos_virtual_addressing_style_survives_the_timeout_change():
    """加超时不能改掉寻址风格——TOS 的 S3 接口只认虚拟主机风格。"""
    from companion.service.uploads.tos import TosObjectStore

    store = TosObjectStore(endpoint="https://tos-s3-cn-beijing.volces.com", bucket="b",
                           access_key="AK", secret_key="SK")
    assert store._client.meta.config.s3["addressing_style"] == "virtual"
