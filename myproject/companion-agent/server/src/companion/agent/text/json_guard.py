"""cue JSON 守卫：把模型输出的一行 ``{"say":…,"cues":[…]}`` 整段交给下游。

**为什么需要它**（生产日志 ``said='{"say":"好，其他都能进…`` 的泄漏根因）：
prompt（``CUE_OUTPUT_SNIPPET``）要求模型优先输出一行 cue JSON，而
:class:`~companion.agent.text.splitter.SentenceSplitter` 只认标点：say 字段内部的
``。！？`` 与 200 字硬切会把 JSON 剁成碎片，每片都过不了
``fragment.try_parse_fragment`` 的整段对象判定，回落成原文——``{"say":"`` 就进了字幕、
``speech.seg`` 和 TTS。

守卫插在断句器**前面**，接口与 ``SentenceSplitter`` 对齐（feed/flush 都返回句子列表）：
看到 ``{`` 且前缀还可能是 cue 片段就缓存到花括号配平；**闭合前**把 ``"say"``
字符串字面量内的新增字节经断句器逐句放出（F16：避免整段 JSON 收齐才首句），
闭合后下发完整 JSON——若 say 已流式放过则只下发 ``{"say":"","cues":[…]}``
以免 TTS 复读。调用方 ``fragment.ingest`` 在闭合片段上仍走结构化路径拿 cues。

已识别的 cue JSON 必须可解析且含可朗读的 say 才能交付。畸形、未闭合或
超限片段丢弃，绝不回落到原文朗读。超限后丢弃本轮余下 token，flush 重置状态；
普通非协议花括号正文仍走断句器。
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from companion.agent.text.splitter import SentenceSplitter

#: cue 片段顶层可能出现的键。识别只认这两个键的前缀，`{"port"` 之类仍是正文。
#: `cues` 必须在列：模型把 cues 写在前面是合法 JSON，只认 say 就会把整段当正文
#: 放给断句器——`{"cues":[…` 原文进字幕与 TTS，say 也被句号切成半句。
_FRAGMENT_KEYS = ("say", "cues")

#: ``{`` + 可选空白 + 可选引号 + 键名的前缀。前缀阶段还判不了就继续等。
_PARTIAL_SHAPE = re.compile(r'^\{\s*("?\s*(s(a(y)?)?|c(u(e(s)?)?)?)?)?$')
_SAY_KEY = re.compile(r'"say"\s*:\s*"')
_CUES_AFTER_SAY = re.compile(r'^\s*,\s*"cues"\s*:\s*\[')


def looks_like_fragment_start(prefix: str) -> bool:
    """缓存中的前缀是否还可能长成 cue 片段？False 时原样放行，不再等。"""
    if not prefix.startswith("{"):
        return False
    if _PARTIAL_SHAPE.match(prefix):
        return True
    # 键名已开始：只认 say / cues 的前缀；`{"speak"` / `{"port"` 之类放行给断句器。
    m = re.match(r'^\{\s*"([a-z_]*)', prefix)
    return bool(m and any(k.startswith(m.group(1)) for k in _FRAGMENT_KEYS))


class CueJsonGuard:
    """断句器前的 JSON 缓存：组合而非子类——断句规则本身保持无关。"""

    def __init__(self, splitter: "SentenceSplitter", *, max_pending_chars: int = 4000) -> None:
        self._splitter = splitter
        self._max_pending = max_pending_chars
        self._pending: str | None = None   # None = 当前不在 JSON 缓存里
        self._discarding = False
        self._say_streamed_chars = 0     # say 闭合后已喂给断句器的解码长度
        self._say_field_closed = False   # 顶层 say 字符串是否已闭合

    def feed(self, chunk: str) -> list[str]:
        """吃一块模型文本，返回此刻能交付的"句"（cue 片段是完整一行 JSON）。"""
        if self._discarding:
            return []
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
                if not looks_like_fragment_start(rest):
                    out += self._splitter.feed(rest)
                    return out
                # JSON 开头：断句器里没到终止符的尾巴（"好的，"）必须先出来，
                # 否则念出来的顺序是 JSON 在前、正文在后。
                out += self._splitter.flush()
                self._pending = ""
                self._say_streamed_chars = 0
                self._say_field_closed = False
                buf = rest
                continue
            probe = self._pending + buf
            end = _scan_close(probe)
            if end is None:
                if not looks_like_fragment_start(probe):
                    # 进来后才露馅（如 `{"foo"`）：整段回落断句器。
                    dumped, self._pending = probe, None
                    self._say_streamed_chars = 0
                    self._say_field_closed = False
                    out += self._splitter.feed(dumped)
                    return out
                self._pending = probe
                out += self._emit_say_stream_delta(probe)
                if len(self._pending) > self._max_pending:
                    self._pending = None
                    self._discarding = True
                    self._say_streamed_chars = 0
                    self._say_field_closed = False
                return out
            complete, self._pending = probe[:end], None
            if len(complete) <= self._max_pending and _safe_fragment(complete):
                if self._say_streamed_chars > 0:
                    out += self._splitter.flush()
                out.append(self._finalize_fragment(complete))
            else:
                self._say_streamed_chars = 0
                self._say_field_closed = False
            buf = probe[end:]         # 闭合后的尾巴（可能是正文或下一段 JSON）继续走循环
        return out

    def _emit_say_stream_delta(self, probe: str) -> list[str]:
        """在整段 JSON 闭合前，把 ``say`` 正文经断句器逐句放出。"""
        decoded, closed, say_end = _say_value_decoded(probe)
        if not decoded or re.search(r'\{\s*"say"\s*:', decoded):
            return []
        if "{" in decoded and (not closed or not _safe_fragment(probe)):
            return []
        if closed:
            if not _say_suffix_allows_stream(probe, say_end) or not _safe_fragment(probe):
                return []
            self._say_field_closed = True
        elif self._say_field_closed:
            return []
        elif len(decoded) < 4:
            # 太短易把 `好。` + `,oops` 误放出去。
            return []
        delta = decoded[self._say_streamed_chars:]
        if not delta:
            return []
        emitted = self._splitter.feed(delta)
        self._say_streamed_chars = len(decoded)
        if not closed and not emitted:
            return []
        return emitted

    def _finalize_fragment(self, complete: str) -> str:
        """闭合后返回整段 JSON；say 若已流式放过则只留 cues 壳。"""
        if self._say_streamed_chars <= 0:
            self._say_streamed_chars = 0
            return complete
        try:
            data = json.loads(complete)
        except (ValueError, RecursionError):
            self._say_streamed_chars = 0
            return complete
        if not isinstance(data, dict):
            self._say_streamed_chars = 0
            return complete
        if self._say_streamed_chars > 0:
            cues = data.get("cues", [])
            self._say_streamed_chars = 0
            return json.dumps({"say": "", "cues": cues if isinstance(cues, list) else []}, ensure_ascii=False)
        self._say_streamed_chars = 0
        return complete

    def flush(self) -> list[str]:
        """收尾：丢弃不完整的协议片段，释放普通正文，重置下一轮状态。"""
        if self._pending is not None or self._discarding:
            self._pending = None
            self._discarding = False
            self._say_streamed_chars = 0
            self._say_field_closed = False
            self._splitter.flush()
            return []
        self._pending = None
        self._discarding = False
        self._say_streamed_chars = 0
        self._say_field_closed = False
        return self._splitter.flush()


def _safe_fragment(text: str) -> bool:
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):
        return False
    if not isinstance(data, dict):
        return False
    say = data.get("say")
    # A syntactically valid outer object can still contain leaked cue JSON in say.
    return isinstance(say, str) and re.search(r'\{\s*"say"\s*:', say) is None


def _say_suffix_allows_stream(probe: str, say_end: int) -> bool:
    """say 已闭合后：空白、单逗号待续、或合法 `,"cues":[` 才允许把余下正文放出。"""
    tail = probe[say_end:]
    stripped = tail.strip()
    if not stripped:
        return False
    if stripped == ",":
        return False
    if _CUES_AFTER_SAY.match(tail):
        return not re.search(r'\]\s*\]', tail)
    return bool(_safe_fragment(probe))


def _say_value_decoded(probe: str) -> tuple[str, bool, int]:
    """从可能未闭合的 JSON 片段里取出当前 ``say`` 字符串的解码正文与闭合后下标。"""
    match = _SAY_KEY.search(probe)
    if not match:
        return "", False, 0
    start = match.end()
    raw, closed = _json_string_body(probe, start)
    body_len = len(raw)
    say_end = start + body_len + (1 if closed else 0)
    if not raw:
        return "", closed, say_end
    if closed:
        try:
            return json.loads('"' + raw + '"'), closed, say_end
        except (ValueError, TypeError):
            return _unescape_json_string_partial(raw), closed, say_end
    # 未闭合：不喂尾部反斜杠，避免半个转义序列。
    trim = raw
    if trim.endswith("\\"):
        trim = trim[:-1]
    if not trim:
        return "", False, say_end
    return _unescape_json_string_partial(trim), False, say_end


def _unescape_json_string_partial(raw: str) -> str:
    """无闭合引号时的 best-effort 解码（中文正文无转义时等于原文）。"""
    try:
        return json.loads('"' + raw + '"')
    except (ValueError, TypeError):
        return raw


def _json_string_body(text: str, start: int) -> tuple[str, bool]:
    """从 ``start``（开引号后）扫描 JSON 字符串字面量，返回 (body, closed)。"""
    i = start
    parts: list[str] = []
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            parts.append(text[i : i + 2])
            i += 2
            continue
        if ch == '"':
            return "".join(parts), True
        parts.append(ch)
        i += 1
    return "".join(parts), False


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
