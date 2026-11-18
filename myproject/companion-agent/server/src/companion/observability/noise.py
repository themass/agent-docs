"""公网扫描器噪音的日志过滤。

8081/8082 直接监听公网（反代在另一台机器上），所以每天有成千上万条畸形请求：
uvicorn 的 ``Invalid HTTP request received``（HTTP/2 preface、垃圾字节打到 HTTP 端口），
aiohttp 的 ``Error handling request ... BadHttpMessage: Pause on PRI/Upgrade`` 带整段
堆栈。这些请求**根本没进应用层**（传输层直接回 400 / 断连），日志里除了淹掉真实信号
没有任何用处——生产 api.log 里这一类曾经占 WARNING 的大头。

做法：挂在 ``uvicorn.error`` 与 ``aiohttp.server`` 两个 logger 上的 Filter，
只丢上面这两类；每小时补一条计数行，保住「外面确实在敲我们」这个信号。
其余记录（业务 WARNING/ERROR、ASGI 异常、访问日志）一律原样通过。

注意：这是降噪，不是防护。防护是把 8081 的防火墙收口到反代来源（待做），
收口之后这个 filter 自然无事可做，但留着无害。
"""

from __future__ import annotations

import logging
import re
import time

# uvicorn(h11) 对垃圾请求的全部输出就这一句；aiohttp 的行首是 "Error handling request"，
# 具体是不是扫描噪音再看异常类型（下面 _is_noise），不靠文案。
_UVICORN_INVALID_HTTP = re.compile(r"^Invalid HTTP request received\.?$", re.IGNORECASE)


def _aiohttp_parser_errors() -> tuple[type[BaseException], ...]:
    """aiohttp 解析层异常族（类名随版本变，逐个 getattr 容错）。惰性导入：
    过滤逻辑不该把 aiohttp 变成硬依赖。"""
    try:
        from aiohttp import http_parser  # type: ignore
    except ImportError:  # pragma: no cover — venv 里必然有，缺了就只过滤 uvicorn 一类
        return ()
    names = ("BadHttpMessage", "BadHttpMethod", "BadStatusLine", "InvalidHeader",
             "InvalidURLError", "LineTooLong")
    return tuple(t for t in (getattr(http_parser, n, None) for n in names)
                 if isinstance(t, type) and issubclass(t, Exception))


class ScannerNoiseFilter(logging.Filter):
    """丢掉传输层畸形请求的日志，每小时用一条 INFO 计数行替代。

    可带 ``[from ip]`` 之类的尾巴：aiohttp 的消息是 "Error handling request from 1.2.3.4"，
    所以 uvicorn 那条按前缀匹配，aiohttp 那条按异常类型判定。
    """

    def __init__(self, summary_every_sec: float = 3600.0) -> None:
        super().__init__()
        self._summary_every = summary_every_sec
        self._dropped = 0
        self._window_open = time.monotonic()

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._is_noise(record):
            return True
        self._dropped += 1
        now = time.monotonic()
        if now - self._window_open >= self._summary_every and self._dropped:
            # 计数行不匹配噪音判定（level 是 INFO、文案不同），不会再被自己吃掉。
            logging.getLogger(record.name).info(
                "已丢弃 %d 条扫描器畸形请求日志（最近 %.1f 分钟）",
                self._dropped, (now - self._window_open) / 60,
            )
            self._dropped = 0
            self._window_open = now
        return False

    def _is_noise(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if _UVICORN_INVALID_HTTP.match(msg):
            return True
        if not msg.startswith("Error handling request"):
            return False
        # aiohttp 的这条一定带 exc_info（web_protocol.log_exception 传入）；
        # 判定只看异常类型，不看文案。没带 exc_info 的同名日志宁可放过不误删。
        exc = record.exc_info[1] if record.exc_info and len(record.exc_info) > 1 else None
        return exc is not None and isinstance(exc, _aiohttp_parser_errors())


_FILTER = ScannerNoiseFilter()
_TARGET_LOGGERS = ("uvicorn.error", "aiohttp.server")


def attach_noise_filter() -> None:
    """把过滤挂到传输层 logger 上。幂等：重复调用不会叠加。"""
    for name in _TARGET_LOGGERS:
        logger = logging.getLogger(name)
        if not any(isinstance(f, ScannerNoiseFilter) for f in logger.filters):
            logger.addFilter(_FILTER)
