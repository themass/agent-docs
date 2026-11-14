"""进程内的指标登记簿。``/metrics`` 端点（Prometheus 文本格式）读的就是这里。

为什么单独一层：指标要同时被三处写——模型回调（``agent/brain/llm_trace.py``）、回合执行
（``service/chat/turn_runner.py``）、健康探针（``api``）。放进 ``agent`` 会让 service 依赖一个
被 agent 拥有的模块；放进 ``service`` 则 agent 的回调要反向依赖。它既不是能力也不是业务，
所以和 ``config.py`` / ``paths.py`` 一样放在顶层。

**指标不能跟着 QA 开关走**：``COMPANION_QA_ENABLED=false`` 时追踪不落库（省空间、省同意判断），
但线上照样需要看延迟和用量。所以采集器永远挂着，写指标在采集器内部完成，落库才看开关。

只用一个进程（``serve.py`` 的 uvicorn 单进程），所以不需要 prometheus_client 的多进程模式。
如果哪天上了多 worker，要换成 ``PROMETHEUS_MULTIPROC_DIR``，否则每个 worker 各报一份、
计数器会互相覆盖。
"""

from __future__ import annotations

from typing import Any

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

# 独立注册表，不往 prometheus_client 的默认注册表里塞：默认注册表还会收进程自身的
# python_gc_*、process_* 指标，混在一起不好按前缀筛。
REGISTRY = CollectorRegistry(auto_describe=True)

# 用户等待的第一个字。直连网关实测 0.7–1s，经图另加自己的开销，所以桶从 0.25 到 60 秒铺开。
_TTFT_BUCKETS = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0, 30.0, 60.0)
# 一次模型调用的总耗时。
_LLM_BUCKETS = (0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0)
# 一个回合从开始到收尾。语音里超过 5 秒就觉得卡，文字里 30 秒仍可接受。
_TURN_BUCKETS = (1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0, 30.0, 60.0, 120.0, 300.0)

LLM_CALLS = Counter(
    "companion_llm_calls", "模型调用次数", ("model", "outcome"), registry=REGISTRY)
LLM_TTFT = Histogram(
    "companion_llm_ttft_seconds", "模型首 token 耗时", ("model",),
    buckets=_TTFT_BUCKETS, registry=REGISTRY)
LLM_DURATION = Histogram(
    "companion_llm_duration_seconds", "模型调用总耗时", ("model",),
    buckets=_LLM_BUCKETS, registry=REGISTRY)
LLM_TOKENS = Counter(
    "companion_llm_tokens", "token 用量", ("model", "kind"), registry=REGISTRY)
LLM_ERRORS = Counter(
    "companion_llm_errors", "模型调用失败", ("model", "error"), registry=REGISTRY)

TURNS = Counter(
    "companion_turns", "回合结束次数", ("state",), registry=REGISTRY)
TURN_TTFT = Histogram(
    "companion_turn_ttft_seconds", "回合开始到第一个可见 token（用户的真实等待）", (),
    buckets=_TTFT_BUCKETS, registry=REGISTRY)
TURN_DURATION = Histogram(
    "companion_turn_duration_seconds", "回合总时长", ("state",),
    buckets=_TURN_BUCKETS, registry=REGISTRY)
TURN_RESTARTS = Counter(
    "companion_turn_restarts", "回合因合并/插话重跑的次数", (), registry=REGISTRY)
ACTIVE_TURNS = Gauge(
    "companion_active_turns", "本进程正在跑的回合数", (), registry=REGISTRY)

# 造提示词（召回、世界书、角色卡）与等待 checkpointer 的耗时。用户的等待里有很大一块在这里，
# 和模型本身无关，所以单独量一次，别都算到"模型慢"头上。
PREPARE_DURATION = Histogram(
    "companion_turn_prepare_seconds", "造提示词（含召回）耗时", (),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0), registry=REGISTRY)


def observe_llm_call(*, model: str, ttft_ms: int | None, total_ms: int | None,
                     input_tokens: int | None, output_tokens: int | None,
                     cached_tokens: int | None, error: str = "") -> None:
    """一次模型调用的结果。失败时只有总耗时和错误名。"""
    name = model or "unknown"
    if error:
        LLM_CALLS.labels(model=name, outcome="error").inc()
        LLM_ERRORS.labels(model=name, error=error).inc()
    else:
        LLM_CALLS.labels(model=name, outcome="ok").inc()
    if ttft_ms is not None:
        LLM_TTFT.labels(model=name).observe(ttft_ms / 1000)
    if total_ms is not None:
        LLM_DURATION.labels(model=name).observe(total_ms / 1000)
    for kind, value in (("input", input_tokens), ("output", output_tokens), ("cached", cached_tokens)):
        if value:
            LLM_TOKENS.labels(model=name, kind=kind).inc(value)


def observe_turn(*, state: str, duration_sec: float, ttft_sec: float | None) -> None:
    """一个回合的结局。``state`` 是 done / failed / cancelled / interrupted / lost 之一。"""
    TURNS.labels(state=state).inc()
    TURN_DURATION.labels(state=state).observe(duration_sec)
    if ttft_sec is not None:
        TURN_TTFT.observe(ttft_sec)


def render() -> bytes:
    """Prometheus 文本格式。调用方直接用这个字节串做响应体。"""
    return generate_latest(REGISTRY)


def reset_for_tests() -> None:
    """测试之间清零。**只在测试里用**：线上没有"重开一个注册表"这回事。"""
    for collector in list(REGISTRY._collector_to_names):   # noqa: SLF001 — 官方没有公开的遍历接口
        REGISTRY.unregister(collector)
    _recreate()


def _recreate() -> None:  # pragma: no cover — 只在 reset_for_tests 之后调用
    global LLM_CALLS, LLM_TTFT, LLM_DURATION, LLM_TOKENS, LLM_ERRORS
    global TURNS, TURN_TTFT, TURN_DURATION, TURN_RESTARTS, ACTIVE_TURNS, PREPARE_DURATION
    LLM_CALLS = Counter("companion_llm_calls", "模型调用次数", ("model", "outcome"), registry=REGISTRY)
    LLM_TTFT = Histogram("companion_llm_ttft_seconds", "模型首 token 耗时", ("model",),
                         buckets=_TTFT_BUCKETS, registry=REGISTRY)
    LLM_DURATION = Histogram("companion_llm_duration_seconds", "模型调用总耗时", ("model",),
                             buckets=_LLM_BUCKETS, registry=REGISTRY)
    LLM_TOKENS = Counter("companion_llm_tokens", "token 用量", ("model", "kind"), registry=REGISTRY)
    LLM_ERRORS = Counter("companion_llm_errors", "模型调用失败", ("model", "error"), registry=REGISTRY)
    TURNS = Counter("companion_turns", "回合结束次数", ("state",), registry=REGISTRY)
    TURN_TTFT = Histogram("companion_turn_ttft_seconds", "回合开始到第一个可见 token（用户的真实等待）", (),
                          buckets=_TTFT_BUCKETS, registry=REGISTRY)
    TURN_DURATION = Histogram("companion_turn_duration_seconds", "回合总时长", ("state",),
                              buckets=_TURN_BUCKETS, registry=REGISTRY)
    TURN_RESTARTS = Counter("companion_turn_restarts", "回合因合并/插话重跑的次数", (), registry=REGISTRY)
    ACTIVE_TURNS = Gauge("companion_active_turns", "本进程正在跑的回合数", (), registry=REGISTRY)
    PREPARE_DURATION = Histogram("companion_turn_prepare_seconds", "造提示词（含召回）耗时", (),
                                 buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
                                 registry=REGISTRY)


def _unused(_: Any) -> None:  # pragma: no cover — 让类型检查器知道 Any 有用
    return None
