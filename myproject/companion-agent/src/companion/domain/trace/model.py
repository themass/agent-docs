"""回合追踪：一个回合一条，存完整的执行链路，并且能还原出模型每一次实际看到的输入。

要解决的问题是体量。一个回合里模型可能被调用几次（工具往返、摘要），每次的输入都包含同一段历史；
跨回合，系统提示词里的角色卡、技能也基本不变。如果每次调用都存一份完整输入，同样的文字会被重复存很多遍。
做法是两层：

1. **内容寻址去重**：消息正文按段落切开，每段按内容哈希存一份（``blobs``），追踪里只存哈希。
   稳定的段落（角色卡、技能、已经说过的历史）因此只存一份，变化的段落（本轮召回的记忆）才新增。
2. **回合内增量**：同一回合里第 k+1 次调用的输入，就是第 k 次的输入加上“模型回复 + 工具结果”。
   所以每个回合只存第一次的完整输入（``base``），之后只存追加的部分（``append``）。
   接不上时（中间件改写了历史）退回存一份新的 ``base``，不会错位。

单条消息超过 ``MAX_MESSAGE_CHARS`` 时保留头尾、中间用标记替代，并记录原长——这只是兜底，防极端情况，
不是主要手段。没有同意留存内容时，只保留指标和工具名，不产生任何 blob。

本模块是纯逻辑，不碰数据库；存取由 ``adapters/store/sql/qa.py`` 负责。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

MAX_MESSAGE_CHARS = 20_000
HEAD_CHARS = 14_000
TAIL_CHARS = 6_000
CUT_MARK = "\n…[中间省略 {n} 字]…\n"
HASH_LEN = 32                     # 128 位，足够避免碰撞，又比完整 sha256 省一半空间
TRACE_VERSION = 1


@dataclass
class LlmCall:
    """采集器看到的一次模型调用。``input_messages`` 是送进模型的完整消息列表。"""

    seq: int = 0
    provider: str = ""
    model: str = ""
    input_messages: list[dict[str, Any]] | None = None
    output_text: str = ""
    reasoning_text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    first_token_ms: int | None = None
    total_ms: int | None = None
    finish_reason: str = ""
    error_code: str = ""


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:HASH_LEN]


def clip(text: str) -> tuple[str, int | None]:
    """超长就保留头尾。返回 (文本, 原长)；没超长时原长为 None。"""
    if len(text) <= MAX_MESSAGE_CHARS:
        return text, None
    cut = len(text) - HEAD_CHARS - TAIL_CHARS
    return text[:HEAD_CHARS] + CUT_MARK.format(n=cut) + text[-TAIL_CHARS:], len(text)


def chunks(text: str) -> list[str]:
    """按空行切段。每段单独去重，所以切法必须是确定的：同样的文字永远切出同样的段，
    前面某段变了不会让后面的段哈希跟着变。段与段之间的空行在还原时补回。"""
    return text.split("\n\n")


def _ref(item: dict[str, Any], blobs: dict[str, str]) -> dict[str, Any]:
    """一条消息 → 紧凑引用：角色、各段哈希、（超长时）原长，以及工具相关的 id。"""
    text, original = clip(str(item.get("content") or ""))
    hashes = []
    for part in chunks(text):
        h = digest(part)
        blobs[h] = part
        hashes.append(h)
    ref: dict[str, Any] = {"r": item.get("role") or "?", "c": hashes}
    if original is not None:
        ref["x"] = original
    for src, dst in (("tool_call_id", "i"), ("name", "n"), ("tool_calls", "t")):
        if item.get(src):
            ref[dst] = item[src]
    return ref


def _key(ref: dict[str, Any]) -> str:
    """两条消息是不是同一条：角色 + 内容哈希 + 工具 id。用于判断下一次调用的输入是否接在上一次后面。"""
    return f"{ref['r']}|{','.join(ref['c'])}|{ref.get('i', '')}"


def _metrics(call: LlmCall) -> dict[str, Any]:
    out: dict[str, Any] = {"seq": call.seq}
    for key, value in (("p", call.provider), ("m", call.model), ("fr", call.finish_reason), ("err", call.error_code),
                       ("in", call.input_tokens), ("out", call.output_tokens), ("cache", call.cached_tokens),
                       ("ttft", call.first_token_ms), ("ms", call.total_ms)):
        if value not in (None, ""):
            out[key] = value
    return out


def build_trace(calls: list[LlmCall], *, keep_content: bool, attempt: int = 0) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """把一个回合的几次模型调用变成 (步骤列表, 需要入库的新文本块)。

    不同意留存内容时：只有指标和工具名，``blobs`` 为空。
    """
    steps: list[dict[str, Any]] = []
    blobs: dict[str, str] = {}
    previous: list[dict[str, Any]] | None = None
    for call in sorted(calls, key=lambda c: c.seq):
        step = _metrics(call)
        step["a"] = attempt
        tools = call.tool_calls or []
        if tools:
            step["tools"] = [{"id": t.get("id"), "name": t.get("name"),
                              **({"args": t.get("args")} if keep_content else {})} for t in tools]
        if keep_content:
            refs = [_ref(m, blobs) for m in (call.input_messages or [])]
            if previous is not None and len(refs) >= len(previous) and \
                    [_key(r) for r in refs[:len(previous)]] == [_key(r) for r in previous]:
                step["append"] = refs[len(previous):]
            else:
                step["base"] = refs
            previous = refs
            if call.output_text:
                parts = []
                text, original = clip(call.output_text)
                for part in chunks(text):
                    h = digest(part)
                    blobs[h] = part
                    parts.append(h)
                step["o"] = parts
                if original is not None:
                    step["ox"] = original
            if call.reasoning_text:
                text, _ = clip(call.reasoning_text)
                parts = []
                for part in chunks(text):
                    h = digest(part)
                    blobs[h] = part
                    parts.append(h)
                step["th"] = parts
        steps.append(step)
    return steps, blobs


def usage_of(steps: list[dict[str, Any]]) -> dict[str, int]:
    """回合级用量合计，从步骤算出来（跨重试累计）。"""
    return {
        "calls": len(steps),
        "input_tokens": sum(s.get("in") or 0 for s in steps),
        "output_tokens": sum(s.get("out") or 0 for s in steps),
        "cached_tokens": sum(s.get("cache") or 0 for s in steps),
        "llm_ms": sum(s.get("ms") or 0 for s in steps),
        "tool_calls": sum(len(s.get("tools") or []) for s in steps),
    }


def _join(hashes: list[str], blobs: dict[str, str]) -> str:
    return "\n\n".join(blobs.get(h, f"[缺失文本块 {h}]") for h in hashes)


def _expand(ref: dict[str, Any], blobs: dict[str, str]) -> dict[str, Any]:
    msg: dict[str, Any] = {"role": ref["r"], "content": _join(ref["c"], blobs)}
    if "x" in ref:
        msg["truncated_from"] = ref["x"]
    for src, dst in (("i", "tool_call_id"), ("n", "name"), ("t", "tool_calls")):
        if src in ref:
            msg[dst] = ref[src]
    return msg


def referenced_hashes(steps: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for s in steps:
        for ref in (s.get("base") or []) + (s.get("append") or []):
            out.update(ref["c"])
        out.update(s.get("o") or [])
        out.update(s.get("th") or [])
    return out


def read_trace(steps: list[dict[str, Any]], blobs: dict[str, str]) -> list[dict[str, Any]]:
    """还原每一步：模型实际看到的输入（逐条）、输出、思考、工具请求和指标。

    ``blobs`` 缺失的块会在正文里标成“缺失文本块”，而不是静默当成空串——
    被清理掉的内容应该看得出来是被清理了。
    """
    out: list[dict[str, Any]] = []
    running: list[dict[str, Any]] = []
    for s in steps:
        if "base" in s:
            running = list(s["base"])
        else:
            running = running + list(s.get("append") or [])
        step = {k: v for k, v in s.items() if k not in ("base", "append", "o", "ox", "th")}
        step["input"] = [_expand(r, blobs) for r in running]
        if "o" in s:
            step["output"] = _join(s["o"], blobs)
            if "ox" in s:
                step["output_truncated_from"] = s["ox"]
        if "th" in s:
            step["reasoning"] = _join(s["th"], blobs)
        out.append(step)
    return out
