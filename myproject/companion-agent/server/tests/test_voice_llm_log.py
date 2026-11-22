"""回合收尾的模型调用日志：语音 worker（8082）没有 /metrics，行内日志是它唯一的模型段现场。

RCA 的 ② 段（context 完成→流末）此前只能靠两条日志的时间差推断；
这一行把每次调用的 ttft / total / reasoning 直接落在 voice.log 里。字段来自
LlmCallCollector（agent/brain/llm_trace.py），不新造一套采集。
"""

from __future__ import annotations

import logging

from companion.agent.brain.trace_model import LlmCall


def _calls() -> list[LlmCall]:
    return [
        LlmCall(seq=0, model="doubao-seed", first_token_ms=1200, total_ms=9000, reasoning_text="想" * 300),
        LlmCall(seq=1, model="doubao-seed", first_token_ms=None, total_ms=500, reasoning_text=""),
    ]


def test_voice_channel_logs_one_line_per_llm_call(caplog):
    from companion.bootstrap.platform import log_turn_llm_calls

    with caplog.at_level(logging.INFO, logger="companion.platform"):
        log_turn_llm_calls(_calls(), channel="voice")

    lines = [r.message for r in caplog.records if "voice llm" in r.message]
    assert len(lines) == 2, lines
    assert "seq=0" in lines[0] and "model=doubao-seed" in lines[0]
    assert "ttft_ms=1200" in lines[0] and "total_ms=9000" in lines[0]
    assert "reasoning_chars=300" in lines[0]
    # 没有首 token 的调用（出错/空响应）不能打塌日志格式
    assert "seq=1" in lines[1] and "ttft_ms=-" in lines[1]


def test_text_channel_stays_quiet(caplog):
    """文字通道的模型指标走 api 进程的 /metrics，这里不重复刷屏。"""
    from companion.bootstrap.platform import log_turn_llm_calls

    with caplog.at_level(logging.INFO, logger="companion.platform"):
        log_turn_llm_calls(_calls(), channel="text")

    assert not [r for r in caplog.records if "voice llm" in r.message]


# ---- 模型开流的墙钟时刻（② 段拆分的钥匙）----
#
# 原来 `voice llm seq=0` 这行在回合收尾时才落日志，时间戳是流末。RCA 想把 ② 段
# （recall 完成→模型开流）单独量出来，只能拿流末时刻减 total_ms 反推 t0，
# 而被打断的回合里 on_llm_end 本身可能晚触发，反推就整体错位（2026-11-21 实测：
# R4/R5 反推出的 t0 落在 tts start 之后，自相矛盾）。开流时刻必须在开流那一刻记。


def _start_collector():
    """一个真实的最小 chat-model 启动，不猜回调形状。"""
    from uuid import uuid4

    from langchain_core.messages import HumanMessage

    from companion.agent.brain.llm_trace import LlmCallCollector

    seen: list[dict] = []
    collector = LlmCallCollector(on_start=lambda **kw: seen.append(kw))
    collector.on_chat_model_start({"name": "ChatDoubao"}, [[HumanMessage(content="讲个故事")]],
                                  run_id=uuid4(),
                                  metadata={"ls_model_type": "chat", "ls_provider": "volc",
                                            "ls_model_name": "doubao-seed-2-1-lite"})
    return seen


def test_collector_reports_model_stream_open_as_it_happens():
    """开流回调在 on_chat_model_start 当场触发，带得上 seq 与模型名。"""
    seen = _start_collector()

    assert len(seen) == 1, seen
    assert seen[0]["seq"] == 0
    assert seen[0]["model"] == "doubao-seed-2-1-lite"


def test_a_broken_logging_callback_never_breaks_the_model_call():
    """采集是旁路：日志口炸了不能让回合失败。"""
    from companion.agent.brain.llm_trace import LlmCallCollector

    def boom(**_kw):
        raise RuntimeError("sink down")

    collector = LlmCallCollector(on_start=boom)
    _start_collector_with(collector)   # 不该抛


def _start_collector_with(collector):
    from uuid import uuid4

    from langchain_core.messages import HumanMessage

    collector.on_chat_model_start({"name": "ChatDoubao"}, [[HumanMessage(content="hi")]], run_id=uuid4(),
                                  metadata={"ls_model_name": "m"})
    return collector


def test_voice_turn_logs_the_open_time(caplog):
    """语音回合：开流当场落一行；文字通道保持安静（数字由 /metrics 提供）。"""
    import logging

    from companion.bootstrap.platform import voice_llm_start_logger

    log = voice_llm_start_logger(channel="voice")
    assert log is not None
    with caplog.at_level(logging.INFO, logger="companion.platform"):
        log(seq=0, model="doubao-seed-2-1-lite")
    lines = [r.message for r in caplog.records if "voice llm start" in r.message]
    assert len(lines) == 1, lines
    assert "seq=0" in lines[0] and "model=doubao-seed-2-1-lite" in lines[0]

    assert voice_llm_start_logger(channel="text") is None
