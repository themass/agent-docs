"""按路由表构造模型（O §8.4）。只在组合根里用：其它层只认 LangChain 的聊天模型或 ``async (prompt) -> str``。

网关是 OpenAI 兼容的 LiteLLM。路由表里的模型名沿用 LiteLLM SDK 的写法（``openai/<名字>``），
直连网关时去掉 ``openai/`` 前缀。密钥与地址从路由表声明的环境变量读取。
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from typing import Any

from companion.agent.llm.router import LLMRouter, ModelEndpoint

LLMCall = Callable[[str], Awaitable[str]]


def _gateway_model_name(name: str) -> str:
    return name.split("/", 1)[1] if name.startswith("openai/") else name


def chat_model(endpoint: ModelEndpoint, *, streaming: bool = True) -> Any:
    from langchain_openai import ChatOpenAI

    base = os.environ.get(endpoint.api_base_env, "")
    key = os.environ.get(endpoint.api_key_env, "")
    if not base or not key:
        raise RuntimeError(f"{endpoint.api_base_env} / {endpoint.api_key_env} are required for {endpoint.model}")
    kwargs: dict[str, Any] = {
        "model": _gateway_model_name(endpoint.model),
        "base_url": base,
        "api_key": key,
        "timeout": endpoint.timeout_sec,
        "temperature": endpoint.temperature,
        "max_tokens": endpoint.max_tokens,
        "streaming": streaming,
    }
    if endpoint.extra_body:
        kwargs["extra_body"] = dict(endpoint.extra_body)
    if endpoint.reasoning_effort:
        kwargs["reasoning_effort"] = endpoint.reasoning_effort
    return ChatOpenAI(**kwargs)


def brain_models(router: LLMRouter, scenario: str = "companion_chat") -> tuple[Any, list[Any]]:
    """大脑用的 (主模型, 备用模型列表)。图要对模型调用 ``bind_tools``，带 fallbacks 的包装对象没有这个方法，
    所以主模型单独给；备用模型交给模型降级中间件（chain 的其余条目，按顺序）。"""
    chain = router.chain(scenario)
    return chat_model(chain[0], streaming=True), [chat_model(e, streaming=True) for e in chain[1:]]


def scenario_model(router: LLMRouter, scenario: str, *, streaming: bool = True) -> Any:
    """场景链的第一个模型；其余作为 LangChain 的 fallbacks（主模型报错时依次尝试）。不能交给大脑的图。"""
    chain = router.chain(scenario)
    primary = chat_model(chain[0], streaming=streaming)
    rest = [chat_model(e, streaming=streaming) for e in chain[1:]]
    return primary.with_fallbacks(rest) if rest else primary


def scenario_call(router: LLMRouter, scenario: str) -> LLMCall:
    """非流式的 ``async (prompt) -> str``，给记忆提取、摘要重建等后台任务用。"""
    model = scenario_model(router, scenario, streaming=False)

    async def call(prompt: str) -> str:
        result = await model.ainvoke(prompt)
        content = getattr(result, "content", result)
        if isinstance(content, list):
            return "".join(p.get("text", "") for p in content if isinstance(p, dict))
        return str(content)

    return call
