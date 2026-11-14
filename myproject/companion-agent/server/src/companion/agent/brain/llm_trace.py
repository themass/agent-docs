"""采集每一次模型调用：输入、输出、思考、token、耗时、结束原因。

做成 LangChain 的回调处理器，而不是去解析 DeerFlow 的流：回调在模型层触发，一个回合里
工具往返、摘要等每一次模型调用都会各来一次，流里看不到这些。

采集器只在内存里攒记录；写库、同意判断由回合结束后的调用方负责（见 platform.py），
这样采集本身不会因为数据库慢或出错而拖住回答。
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from companion import metrics
from companion.agent.brain.trace_model import LlmCall

def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content or "")


def _input_item(m: Any) -> dict[str, Any]:
    """送进模型的一条消息。工具结果要带上是哪次调用的（tool_call_id）和哪个工具，否则回看时对不上号。"""
    item: dict[str, Any] = {"role": getattr(m, "type", "?"), "content": _text(getattr(m, "content", ""))}
    if getattr(m, "tool_call_id", None):
        item["tool_call_id"] = m.tool_call_id
    if getattr(m, "name", None):
        item["name"] = m.name
    if getattr(m, "tool_calls", None):
        item["tool_calls"] = [{"id": c.get("id"), "name": c.get("name")} for c in m.tool_calls]
    return item


def _tool_calls(message: Any) -> list[dict[str, Any]]:
    return [{"id": c.get("id"), "name": c.get("name"), "args": c.get("args")}
            for c in (getattr(message, "tool_calls", None) or [])]


def _reasoning(message: Any) -> str:
    """不同供应商把思考放在不同位置：additional_kwargs，或内容块里 type 为 reasoning / thinking。"""
    extra = getattr(message, "additional_kwargs", None) or {}
    for key in ("reasoning_content", "reasoning"):
        if extra.get(key):
            return str(extra[key])
    content = getattr(message, "content", None)
    if isinstance(content, list):
        parts = [p.get("reasoning") or p.get("thinking") or p.get("text", "")
                 for p in content if isinstance(p, dict) and p.get("type") in ("reasoning", "thinking")]
        return "".join(str(p) for p in parts if p)
    return ""


class LlmCallCollector(BaseCallbackHandler):
    """一个回合一个实例。``drain`` 取走已完成的调用记录。"""

    def __init__(self) -> None:
        self._open: dict[UUID, dict[str, Any]] = {}
        self._done: list[LlmCall] = []
        self._seq = 0

    # ---- LangChain 回调 ----

    def on_chat_model_start(self, serialized: dict[str, Any], messages: list[list[Any]], *, run_id: UUID,
                            metadata: dict[str, Any] | None = None, **kwargs: Any) -> None:
        meta = metadata or {}
        self._open[run_id] = {
            "t0": time.monotonic(), "first": None, "seq": self._seq,
            "provider": str(meta.get("ls_provider") or ""), "model": str(meta.get("ls_model_name") or ""),
            "input": [_input_item(m) for m in (messages[0] if messages else [])],
        }
        self._seq += 1

    def on_llm_new_token(self, token: str, *, run_id: UUID, **kwargs: Any) -> None:
        call = self._open.get(run_id)
        if call is not None and call["first"] is None and token:
            call["first"] = time.monotonic()

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        call = self._open.pop(run_id, None)
        if call is None:
            return
        message = None
        for generations in getattr(response, "generations", None) or []:
            if generations:
                message = getattr(generations[0], "message", None)
                break
        usage = (getattr(message, "usage_metadata", None) or {}) if message is not None else {}
        details = usage.get("input_token_details") or {}
        meta = (getattr(message, "response_metadata", None) or {}) if message is not None else {}
        now = time.monotonic()
        record = LlmCall(
            seq=call["seq"], provider=call["provider"], model=str(meta.get("model_name") or call["model"]),
            input_messages=call["input"], output_text=_text(getattr(message, "content", "")) if message else "",
            reasoning_text=_reasoning(message) if message is not None else "",
            tool_calls=_tool_calls(message) if message is not None else [],
            input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
            cached_tokens=details.get("cache_read"),
            first_token_ms=int((call["first"] - call["t0"]) * 1000) if call["first"] else None,
            total_ms=int((now - call["t0"]) * 1000),
            finish_reason=str(meta.get("finish_reason") or ""))
        self._done.append(record)
        # 指标在这里就写掉，不等 drain：drain 的调用方只在 QA 打开时才存在，
        # 而延迟和用量是线上随时要看的，不能跟着 QA 开关一起消失。
        metrics.observe_llm_call(
            model=record.model, ttft_ms=record.first_token_ms, total_ms=record.total_ms,
            input_tokens=record.input_tokens, output_tokens=record.output_tokens,
            cached_tokens=record.cached_tokens)

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        call = self._open.pop(run_id, None)
        if call is None:
            return
        total_ms = int((time.monotonic() - call["t0"]) * 1000)
        error_code = type(error).__name__[:64]
        self._done.append(LlmCall(
            seq=call["seq"], provider=call["provider"], model=call["model"],
            input_messages=call["input"], total_ms=total_ms, error_code=error_code))
        metrics.observe_llm_call(model=call["model"], ttft_ms=None, total_ms=total_ms,
                                 input_tokens=None, output_tokens=None, cached_tokens=None,
                                 error=error_code)

    # ---- 取用 ----

    def drain(self) -> list[LlmCall]:
        done, self._done = sorted(self._done, key=lambda r: r.seq), []
        return done
