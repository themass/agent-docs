"""语音 worker 用的 DeerFlow 大脑：和文字对话同一套图与提示词能力。

为什么不复用 ``build_platform``：那个函数装配的是完整的聊天栈（消息表、Redis 事件流、
提醒调度），语音 worker 只需要一个 ``BrainPort``。这里只构造它用到的那部分——
模型、工具运行时、checkpoint——不打开任何 FastAPI 相关的东西。

没有模型配置或没有 DeerFlow 依赖时抛错，由调用方决定是否降级到假大脑（并在日志里叫出来）。
"""

from __future__ import annotations

from typing import Any

from companion.config import settings


def build_voice_brain() -> Any:
    if not (settings.companion_llm_api_base and settings.companion_llm_api_key):
        raise RuntimeError("缺少 COMPANION_LLM_API_BASE / COMPANION_LLM_API_KEY")

    from companion.bootstrap.platform import _build_brain
    from companion.bootstrap.platform import default_prompts  # noqa: F401 —— 保持与文字栈同源
    from companion.domain.tools.registry import ToolRegistry

    registry = ToolRegistry()
    # 语音第一版不挂工具：提醒、记忆写入等都在文字链路上，等共用会话接通后再打开。
    # 工具运行时在 _build_brain 里是可选的。
    brain, _graph, _llm = _build_brain(settings, registry=registry, runtime=None, checkpointer=None,
                                       product="roleplay")
    return brain
