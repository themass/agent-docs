"""扫描器噪音过滤：丢该丢的，留必须留的。

判断标准来自生产日志实样（api.log 的 uvicorn.error、voice.log 的 aiohttp.server），
不是猜的文案。
"""

import logging

from aiohttp.http_parser import BadHttpMessage

from companion.observability.noise import ScannerNoiseFilter, attach_noise_filter


def _make(name: str, msg: str, exc=None, level=logging.WARNING) -> logging.LogRecord:
    exc_info = (type(exc), exc, None) if exc else None
    return logging.LogRecord(name, level, __file__, 1, msg, (), exc_info)


def test_drops_uvicorn_invalid_http():
    f = ScannerNoiseFilter()
    assert not f.filter(_make("uvicorn.error", "Invalid HTTP request received."))
    # 带尾巴的同款（不同 h11 版本措辞可能加句号/来源）
    assert not f.filter(_make("uvicorn.error", "Invalid HTTP request received"))


def test_keeps_other_uvicorn_error_records():
    f = ScannerNoiseFilter()
    assert f.filter(_make("uvicorn.error", "ASGI application startup failed."))
    assert f.filter(_make("uvicorn.error", 'WebSocket disconnection without close frame'))


def test_drops_aiohttp_parser_bombs_only_by_exception_type():
    f = ScannerNoiseFilter()
    bomb = _make("aiohttp.server", "Error handling request from 66.132.172.178",
                 exc=BadHttpMessage("400, message:\n  Pause on PRI/Upgrade"))
    assert not f.filter(bomb)
    # 同一条消息、异常不是解析层 → 必须留下（可能是真故障）
    real = _make("aiohttp.server", "Error handling request from 1.2.3.4", exc=RuntimeError("boom"))
    assert f.filter(real)


def test_a_real_handler_error_with_exc_info_still_passes():
    f = ScannerNoiseFilter()
    rec = _make("aiohttp.server", "Error handling request", exc=RuntimeError("handler crashed"))
    assert f.filter(rec)


def test_summary_row_survives_its_own_filter(caplog):
    """计数行不得被过滤器自己吃掉，否则「外面在敲」的信号彻底丢失。"""
    f = ScannerNoiseFilter(summary_every_sec=0)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        f.filter(_make("uvicorn.error", "Invalid HTTP request received."))
    assert "扫描器" in caplog.text


def test_attach_is_idempotent():
    before = len(logging.getLogger("uvicorn.error").filters)
    attach_noise_filter()
    attach_noise_filter()
    assert len(logging.getLogger("uvicorn.error").filters) - before <= 1
