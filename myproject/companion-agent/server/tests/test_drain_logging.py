"""停机过程必须留下可判定的证据（service/chat/lifecycle.py）。

2026-11-28 线上重启打断了一个刚起步的回合，而 journal 里没有任何一行能证明 drain 跑过、
当时有几个回合在飞——事后只能靠时间戳相邻去猜。这些用例钉的是**日志存在与否**，
因为不可判定的停机等于没有优雅停机。
"""

import logging

from companion.service.chat.lifecycle import DrainState


async def test_begin_logs_how_many_turns_are_in_flight(caplog):
    """active=0 也要打：它是「停机时没有回合在飞」的正面证据。"""
    drain = DrainState()
    with caplog.at_level(logging.INFO, logger="companion.drain"):
        drain.begin()
    assert "drain begin active_turns=0" in caplog.text


async def test_begin_reports_the_turns_it_is_waiting_for(caplog):
    drain = DrainState()
    drain.turn_started()
    drain.turn_started()
    with caplog.at_level(logging.INFO, logger="companion.drain"):
        drain.begin()
    assert "active_turns=2" in caplog.text


async def test_timeout_is_a_warning_naming_the_dropped_turns(caplog):
    """等满超时 = 这些回合会被后面的 SIGKILL 打断。这一行把那件事从推测变成记录。"""
    drain = DrainState()
    drain.turn_started()
    with caplog.at_level(logging.INFO, logger="companion.drain"):
        ok = await drain.wait_idle(timeout=0.05)
    assert ok is False
    assert "timed out" in caplog.text and "active_turns=1" in caplog.text


async def test_clean_drain_logs_the_wait(caplog):
    drain = DrainState()
    drain.turn_started()
    with caplog.at_level(logging.INFO, logger="companion.drain"):
        drain.begin()
        drain.turn_finished()
        ok = await drain.wait_idle(timeout=1.0)
    assert ok is True
    assert "drain idle after" in caplog.text


async def test_second_signal_does_not_relog_begin(caplog):
    """第二次信号走 uvicorn 原路；begin 的日志只该有一条。"""
    drain = DrainState()
    with caplog.at_level(logging.INFO, logger="companion.drain"):
        drain.begin()
        drain.begin()
    assert caplog.text.count("drain begin") == 1
