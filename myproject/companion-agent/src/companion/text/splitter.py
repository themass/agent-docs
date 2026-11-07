"""流式断句。

主脑吐的是任意切分的文本片段，TTS 需要整句才读得自然。这里把片段流还原成句子，
并且**与切分方式无关**：同一段文本无论一次喂完还是逐字喂，吐出的句子序列相同。

代价是句子要等一个字符的确认——"." 后面可能是数字，句号后面可能还跟着 "！！"——
所以一句通常在下一块到达时才吐出，而不是立刻。
"""

from __future__ import annotations

# 一到就断的终止符
_STRONG = frozenset("。！？!?\n")
_ELLIPSIS = "…"
# 终止符后面跟着这些字符时归本句
_CLOSERS = frozenset("\"'”’」』）)］]｝}】》〉〕»")
# 终止符集合，也是断点后要继续吸收成串的字符（"！！"、"……"、"..."）
_TERMINATORS = _STRONG | {_ELLIPSIS, "."}
_COMMAS = frozenset(",，、")

# "." 后面即使有空格，也可能是缩写。"I." / "A." 排除掉，否则 "I." 结尾的句子永不断。
_ABBREVIATIONS = frozenset(
    {
        "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc",
        "fig", "inc", "ltd", "co", "dept", "ave", "blvd", "mt", "no", "approx",
    }
)


def _is_cjk(ch: str) -> bool:
    """中日韩字符与全角标点。"." 后面紧跟它们说明是句末（中文没有空格）。"""
    o = ord(ch)
    return (
        0x4E00 <= o <= 0x9FFF
        or 0x3400 <= o <= 0x4DBF
        or 0xF900 <= o <= 0xFAFF
        or 0x3000 <= o <= 0x303F
        or 0xFF00 <= o <= 0xFFEF
    )


def _is_ascii_letter(ch: str) -> bool:
    return "a" <= ch <= "z" or "A" <= ch <= "Z"


class SentenceSplitter:
    """把任意切分的文本片段攒成整句，纯内存、无副作用。

    ``max_chars`` 是硬上限：缓冲里没有终止符时，在最后一个逗号处（找不到就硬切）
    先吐一段，避免长句把 TTS 饿死。
    """

    DEFAULT_MAX_CHARS = 200

    def __init__(self, *, max_chars: int = DEFAULT_MAX_CHARS) -> None:
        if max_chars < 1:
            raise ValueError("max_chars must be positive")
        self._max_chars = max_chars
        self._buf = ""

    def feed(self, chunk: str) -> list[str]:
        """吃一块文本，返回这之后能确定的完整句子（可能为空）。"""
        if chunk:
            self._buf += chunk
        return self._drain(final=False)

    def flush(self) -> list[str]:
        """收尾：把缓冲里剩下的全部吐出来，之后缓冲清空。"""
        out = self._drain(final=True)
        rest, self._buf = self._buf, ""
        self._push(out, rest)
        return out

    # ---- 内部 ----

    def _drain(self, *, final: bool) -> list[str]:
        out: list[str] = []
        while True:
            brk = self._scan(final=final)
            if brk is not None and brk <= self._max_chars:
                piece, self._buf = self._buf[:brk], self._buf[brk:]
                self._push(out, piece)
                continue
            if len(self._buf) > self._max_chars:
                cut = self._cap_cut()
                piece, self._buf = self._buf[:cut], self._buf[cut:]
                self._push(out, piece)
                continue
            return out

    def _cap_cut(self) -> int:
        head = self._buf[: self._max_chars]
        for i in range(len(head) - 1, 0, -1):
            if head[i] in _COMMAS:
                return i + 1
        return self._max_chars

    def _scan(self, *, final: bool) -> int | None:
        """返回第一个确定断点的下标（不含），没有就 None。"""
        buf = self._buf
        # 断点超过 max_chars 时反正要 cap 切，所以只看这一截，避免大缓冲重复扫描
        limit = min(len(buf), self._max_chars + 1)
        i = 0
        while i < limit:
            ch = buf[i]
            if ch in _TERMINATORS and not (ch == "." and not self._dot_ends(i, final=final)):
                end = self._absorb_end(i + 1)
                # 断点吃到缓冲末尾时，下一块还可能接"！"或收尾引号（"好的。" “好的。”"），
                # 只有看到下一个字符才知道句子到哪为止。所以最后一句留给 flush，其余
                # 每句晚一块吐出——这是流式输出与一次性切分结果完全一致的代价。
                if end >= len(buf) and not final:
                    return None
                return end
            i += 1
        return None

    def _absorb_end(self, i: int) -> int:
        buf = self._buf
        n = len(buf)
        while i < n and (buf[i] in _TERMINATORS or buf[i] in _CLOSERS):
            i += 1
        return i

    def _dot_ends(self, i: int, *, final: bool) -> bool:
        buf = self._buf
        n = len(buf)
        j = i + 1
        while j < n and buf[j] in _CLOSERS:  # 引号/括号先跳过再看后一个字符
            j += 1
        if j >= n:
            return final  # 结尾的点：只有 flush 时才算句末
        nxt = buf[j]
        if not (nxt.isspace() or _is_cjk(nxt)):
            return False  # 3.5 / 1.2.3 / www.example.com
        return not self._is_abbreviation(i)

    def _is_abbreviation(self, i: int) -> bool:
        buf = self._buf
        k = i
        while k > 0 and _is_ascii_letter(buf[k - 1]):
            k -= 1
        word = buf[k:i]
        if not word:
            return False
        if len(word) == 1:
            # "p.m." / "e.g." / "U.S."：前一个点说明这是缩写链的一节
            if word.lower() in {"a", "i"}:
                return False
            return word.isupper() or (k > 0 and buf[k - 1] == ".")
        return word.lower() in _ABBREVIATIONS

    @staticmethod
    def _push(out: list[str], piece: str) -> None:
        s = piece.strip()
        if s:
            out.append(s)


def split_sentences(text: str, *, max_chars: int = SentenceSplitter.DEFAULT_MAX_CHARS) -> list[str]:
    """一次性切分，测试与非流式场景用。"""
    splitter = SentenceSplitter(max_chars=max_chars)
    return splitter.feed(text) + splitter.flush()
