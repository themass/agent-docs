"""第三方库日志的凭据收口。

httpx 在 INFO 打整条请求 URL。高德的 Web Service 把凭据放在 query 里
（`?key=…`），于是 `poi_search` 每查一次，amap key 就明文进 journald 一次：

    INFO httpx HTTP Request: GET https://restapi.amap.com/v3/place/around?key=…&location=…

2026-11-28 线上 journal 实测，不是推测。我们自己的 log 调用一直不打参数，挡不住
这条——泄露路径是 HTTP 库自己的日志，而 journald 会把它持久保存、任何能
`journalctl` 的人都读得到。放 header 鉴权的服务（ark / volces）不受影响，
只有密钥放 query 的会漏。

httpx 0.28.1 的 `AsyncClient` 没有 `log_level` 参数（已核签名），所以只能在
logger 上压。`httpcore` 与 `httpx` 是兄弟 logger 不是父子，两个都要压。
"""

from __future__ import annotations

import logging

_THIRD_PARTY_LOGGERS = ("httpx", "httpcore")


def pin_third_party_log_levels() -> None:
    """第三方 HTTP 库最低只出 WARNING。幂等：重复调用没有副作用。"""
    for name in _THIRD_PARTY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
