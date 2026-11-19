"""cue JSON 守卫：把模型输出的一行 ``{"say":…,"cues":[…]}`` 整段交给下游。

**为什么需要它**（生产日志 ``said='{"say":"好，其他都能进…`` 的泄漏根因）：
prompt（``CUE_OUTPUT_SNIPPET``）要求模型优先输出一行 cue JSON，而
:class:`~companion.agent.text.splitter.SentenceSplitter` 只认标点：say 字段内部的
``。！？`` 与 200 字硬切会把 JSON 剁成碎片，每片都过不了
``fragment.try_parse_fragment`` 的整段对象判定，回落成原文——``{"say":"`` 就进了字幕、
``speech.seg`` 和 TTS。

守卫插在断句器**前面**，接口与 ``SentenceSplitter`` 对齐（feed/flush 都返回句子列表）：
看到 ``{`` 且前缀还可能是 cue 片段就停止向下游透传，缓存到花括号配平（跳过字符串
字面量与 ``\\`` 转义）后把整段一次性返回，调用方喂给 ``fragment.ingest`` 即走结构化路径。

不越权也不扣话：
- 它不解析内容——合不合法是 ``fragment`` 的事，形状不符的 ``{`` 原样放行给断句器；
- 缓存超过 ``max_pending_chars``（模型跑偏写长文）立刻回落断句器，宁可退回旧行为
  也不永久扣住用户该听到的话；
- ``flush()`` 时未闭合的残段照吐（流断了也要把话交付）。
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from companion.agent.text.splitter import SentenceSplitter

#: ``{`` + 可选空白 + 可选引号 + "say" 的前缀（s/sa/say）。前缀阶段还判不了就继续等。
_PARTIAL_SHAPE = re.compile(r'^\{\s*("?\s*(s(a(y)?)?)?)?$')


def looks_like_fragment_start(prefix: str) -> bool:
    """缓存中的前缀是否还可能长成 cue 片段？False 时原样放行，不再等。"""
    if not prefix.startswith("{"):
        return False
    if len(prefix) > 400:          # cue 片段是"一行 JSON"，远超就是跑偏
        return False
    if _PARTIAL_SHAPE.match(prefix):
        return True
    # 键名已开始：只认 "say" 的前缀；`{"speak"` / `{"foo"` 之类放行给断句器。
    m = re.match(r'^\{\s*"([a-z_]*)', prefix)
    return bool(m and "say".startswith(m.group(1)))


class CueJsonGuard:
    """断句器前的 JSON 缓存：组合而非子类——断句规则本身保持无关。"""

    def __init__(self, splitter: "SentenceSplitter", *, max_pending_chars: int = 4000) -> None:
        self._splitter = splitter
        self._max_pending = max_pending_chars
        self._pending: str | None = None   # None = 当前不在 JSON 缓存里

    def feed(self, chunk: str) -> list[str]:
        """吃一块模型文本，返回此刻能交付的"句"（cue 片段是完整一行 JSON）。"""
        out: list[str] = []
        buf = chunk
        while buf:
            if self._pending is None:
                brace = buf.find("{")
                if brace < 0:
                    out += self._splitter.feed(buf)
                    return out
                if brace > 0:
                    # JSON 前的正常文本先过断句器（含"没有终止符的尾巴"扣在断句器缓冲里，
                    # 下一段 JSON 到达时它还没吐——见 flush 与测试的顺序约定）。
                    out += self._splitter.feed(buf[:brace])
                rest = buf[brace:]
                if not looks_like_fragment_start(rest[:401]):
                    out += self._splitter.feed(rest)
                    return out
                # JSON 开头：断句器里没到终止符的尾巴（"好的，"）必须先出来，
                # 否则念出来的顺序是 JSON 在前、正文在后。
                out += self._splitter.flush()
                self._pending = ""
                buf = rest
                continue
            probe = self._pending + buf
            end = _scan_close(probe)
            if end is None:
                if not looks_like_fragment_start(probe[:401]):
                    # 进来后才露馅（如 `{"foo"`）：整段回落断句器。
                    dumped, self._pending = probe, None
                    out += self._splitter.feed(dumped)
                    return out
                self._pending = probe
                if len(self._pending) > self._max_pending:
                    dumped, self._pending = self._pending, None
                    out += self._splitter.feed(dumped)
                return out
            complete, self._pending = probe[:end], None
            out.append(complete)
            buf = probe[end:]         # 闭合后的尾巴（可能是正文或下一段 JSON）继续走循环
        return out

    def flush(self) -> list[str]:
        """收尾：未闭合的 JSON 残段与断句器缓冲一起吐出。"""
        out: list[str] = []
        if self._pending is not None:
            out.append(self._pending)
            self._pending = None
        out += self._splitter.flush()
        return out


def _scan_close(text: str) -> int | None:
    """返回最外层配平闭合的下标（含 ``}``），未闭合返回 None。跳过字符串与转义。"""
    depth = 0
    in_str = False
    escaped = False
    for i, ch in enumerate(text):
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                return i + 1
    return None
