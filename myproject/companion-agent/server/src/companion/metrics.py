"""指标登记簿——**委托给 agentkit**，与 job-come 共用同一套指标词汇。

为什么不再自己定义一套：两边的监控面板读的是同一份约定（``llm_*`` / ``agent_*`` /
``method_*``，见 ``agentkit.observability.OWNED_PREFIXES``）。我们原来那套 ``companion_*``
别人读不到——面板按前缀过滤，名字对不上就是空图。指标的价值在"同一个词在两层指的是同一件事"，
自己另起一套等于放弃这个价值。

本模块保留自己的函数名（``observe_llm_call`` / ``observe_turn``），但**内部只做映射**：
把 companion 的概念翻译成 agentkit 的词汇，调用方不用改。

映射：

| companion 概念 | agentkit 指标 | 说明 |
|---|---|---|
| 模型调用 | ``llm_calls_total`` / ``llm_call_duration_seconds`` | 带 scenario + model + status |
| 模型首 token | ``agent_phase_duration_seconds{phase="llm_ttft"}`` | 直连网关 0.7–1 秒 |
| 回合首字 | ``agent_phase_duration_seconds{phase="ttft"}`` | 与 job-come 同名同义：回合开始→第一个字 |
| 造提示词 | ``agent_phase_duration_seconds{phase="prepare"}`` | 召回、世界书、角色卡 |
| 回合总时长 | ``agent_phase_duration_seconds{phase="turn"}`` | |
| 回合结局 | ``agent_turns_total{role,status}`` | |
| 在跑的回合 | ``agent_turns_in_flight`` | |
| 重跑次数 | ``agent_turn_restarts_total`` | 我们自己加的，前缀合规所以面板也收 |

**指标不能跟着 QA 开关走**：``COMPANION_QA_ENABLED=false`` 时追踪不落库（省空间、省同意判断），
但线上照样需要看延迟和用量。所以采集器永远挂着，写指标在采集器内部完成，落库才看开关。
"""

from __future__ import annotations

import os
from typing import Any

from agentkit.observability import (
    CONTENT_TYPE,
    collect_peer_snapshots,
    configure,
    counter,
    inflight_turn,
    metrics_enabled,
    parse_peers,
    record_agent_phase,
    record_agent_turn,
    record_llm_metrics,
    render_metrics,
    snapshot,
)

#: 服务名与环境的标签。一次配置，之后所有指标都带这两个标签——
#: 一个 Prometheus 抓多套部署时，靠它们区分。
configure(
    application=os.environ.get("COMPANION_METRICS_SERVICE_NAME", "companion-agent"),
    environment=os.environ.get("COMPANION_ENV", "dev"),
    enabled=os.environ.get("COMPANION_METRICS_ENABLED", "true").lower() in {"1", "true", "yes"},
)

__all__ = [
    "CONTENT_TYPE",
    "collect_peer_snapshots",
    "parse_peers",
    "render",
    "observe_llm_call",
    "observe_turn",
    "observe_phase",
    "turn_in_flight",
    "count_restart",
    "snapshot",
    "metrics_enabled",
]

#: 合并/插话导致的重跑。agentkit 没有对应项，用它的 ``counter`` 造一个——
#: 前缀是 ``agent_``，所以面板的过滤器会带上它，不需要改前端。
_RESTARTS = counter("agent_turn_restarts_total", "回合因合并/插话重跑的次数", ())


def observe_llm_call(*, scenario: str = "companion_chat", model: str, ttft_ms: int | None,
                     total_ms: int | None, input_tokens: int | None,
                     output_tokens: int | None, cached_tokens: int | None,
                     error: str = "") -> None:
    """一次模型调用的结果。失败时只有总耗时和错误类名。"""
    if not metrics_enabled():
        return
    record_llm_metrics(
        scenario=scenario,
        model=model,
        duration=(total_ms / 1000) if total_ms is not None else None,
        status="error" if error else "success",
        error_type=error or None,
        prompt_tokens=input_tokens,
        completion_tokens=output_tokens,
    )
    # 首 token 单独记一条 phase：它和总耗时回答的不是同一个问题。
    # "模型慢" 经常被当成一个数，其实首字慢和出字慢是两回事。
    if ttft_ms is not None:
        record_agent_phase(phase="llm_ttft", duration=ttft_ms / 1000)


def observe_turn(*, state: str, duration_sec: float, ttft_sec: float | None,
                 role: str = "chat") -> None:
    """一个回合的结局。``state`` 是 done / failed / cancelled / interrupted / lost。"""
    if not metrics_enabled():
        return
    record_agent_turn(role=role, status=state)
    record_agent_phase(phase="turn", duration=duration_sec,
                       outcome="ok" if state == "done" else "error")
    if ttft_sec is not None:
        record_agent_phase(phase="ttft", duration=ttft_sec)


def observe_phase(*, phase: str, duration_sec: float, outcome: str = "ok") -> None:
    """回合内的一个命名阶段：prepare（造提示词）、build（建图）、tool（工具）等。"""
    if not metrics_enabled():
        return
    record_agent_phase(phase=phase, duration=duration_sec, outcome=outcome)


def turn_in_flight():
    """``with turn_in_flight():`` —— 在跑的回合数。只涨不跌说明有回合卡住了。"""
    return inflight_turn()


def count_restart() -> None:
    if not metrics_enabled():
        return
    try:
        _RESTARTS.inc()
    except Exception:  # noqa: BLE001 —— 指标失败绝不能影响回合
        pass


def render() -> bytes:
    """Prometheus 文本格式。"""
    return render_metrics()
