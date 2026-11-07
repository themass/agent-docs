"""中间件链。

顺序是设计的一部分，不是实现细节：安全 → 记忆召回 → 事件抽取 → 人设一致性
→ 工具授权 → 成本 → 观测。见设计文档第 8 节。
"""

from companion.middleware.chain import Middleware, MiddlewareChain, MiddlewareContext
from companion.middleware.cost import CostMiddleware
from companion.middleware.extraction import EventExtractionMiddleware, drives_proactive
from companion.middleware.memory_recall import MemoryRecallMiddleware
from companion.middleware.observability import ObservabilityMiddleware
from companion.middleware.persona_guard import PersonaGuardMiddleware
from companion.middleware.render import render_events
from companion.middleware.safety import SafetyMiddleware

__all__ = [
    "CostMiddleware",
    "EventExtractionMiddleware",
    "MemoryRecallMiddleware",
    "Middleware",
    "MiddlewareChain",
    "MiddlewareContext",
    "ObservabilityMiddleware",
    "PersonaGuardMiddleware",
    "SafetyMiddleware",
    "drives_proactive",
    "render_events",
]
