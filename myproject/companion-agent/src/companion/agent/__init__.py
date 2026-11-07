"""LiveKit agent 包。

``CompanionAgent`` 通过 [build_agent_class] 构造：它的父类来自 livekit-agents，
包缺失时不能在这里就报错，否则 HTTP 接口和测试都会被连带拖垮。
"""

from companion.agent.companion_agent import build_agent_class

__all__ = ["build_agent_class"]
