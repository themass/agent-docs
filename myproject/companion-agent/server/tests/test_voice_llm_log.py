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
