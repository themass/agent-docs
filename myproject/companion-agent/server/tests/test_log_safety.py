"""第三方库日志不能把凭据带进 journald（2026-11-28 线上实测过的泄露）。

journal 里真实出现过这一行：

    INFO httpx HTTP Request: GET https://restapi.amap.com/v3/place/around?key=…&location=…

判断标准是这条实样，不是「日志里最好别有密钥」的泛泛要求：同一条记录必须被压掉，
而 httpx 真正的故障信号（WARNING）必须留下。
"""

import logging

from companion.observability.log_safety import pin_third_party_log_levels

_REQUEST_LINE = ('HTTP Request: GET https://restapi.amap.com/v3/place/around'
                 '?key=secret-amap-key&location=121.47,31.23 "HTTP/1.1 200 OK"')


def test_pinned_third_party_info_line_does_not_reach_handler(caplog):
    caplog.set_level(logging.INFO)
    pin_third_party_log_levels()
    logging.getLogger("httpx").info(_REQUEST_LINE)
    assert "secret-amap-key" not in caplog.text
    assert "place/around" not in caplog.text


def test_pinning_keeps_httpx_warnings(caplog):
    caplog.set_level(logging.INFO)
    pin_third_party_log_levels()
    logging.getLogger("httpx").warning("connect timeout to restapi.amap.com")
    assert "connect timeout" in caplog.text


def test_pinning_does_not_quiet_application_logs(caplog):
    """压的是第三方 logger，不是整个进程——业务 INFO 还得能用来排查。"""
    caplog.set_level(logging.INFO)
    pin_third_party_log_levels()
    logging.getLogger("companion.chat_api").info("send_message timing session=39 disposition=started")
    assert "send_message timing" in caplog.text


def test_pinning_covers_httpcore_and_is_idempotent():
    pin_third_party_log_levels()
    pin_third_party_log_levels()
    for name in ("httpx", "httpcore"):
        assert logging.getLogger(name).level == logging.WARNING
