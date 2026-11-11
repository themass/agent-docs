"""关键词匹配的文本规范化（中、英、阿拉伯语）。

修正 SillyTavern 的几个多语言问题（chat-agent-harness-greenfield.md §5.7）：
- 统一做 NFKC（全角 / 半角）与大小写折叠；
- 阿拉伯语去掉变音符与延长符，统一 alef / ya 的写法；
- 含中日韩字符的关键词一律子串匹配（「猫」命中「猫咪」）；整词匹配只对字母文字生效，
  且用 Unicode 的 \\w 判断边界，阿拉伯字母算作单词字符。
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

_ARABIC_MARKS = re.compile("[ً-ٰٟـ]")
_ALEF = re.compile("[آأإٱ]")
_CJK = re.compile("[぀-ヿ㐀-䶿一-鿿가-힯豈-﫿]")

MAX_REGEX_CHARS = 200


def normalize(text: str, *, case_sensitive: bool = False) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _ARABIC_MARKS.sub("", text)
    text = _ALEF.sub("ا", text).replace("ى", "ي")
    return text if case_sensitive else text.casefold()


@lru_cache(maxsize=1024)
def _regex(pattern: str, flags: str) -> re.Pattern[str] | None:
    """``/pattern/flags`` 形式的关键词。只支持 i、s、m 三个标志；过长或编译失败的模式视为不匹配。"""
    if len(pattern) > MAX_REGEX_CHARS:
        return None
    value = 0
    for flag in flags:
        value |= {"i": re.IGNORECASE, "s": re.DOTALL, "m": re.MULTILINE}.get(flag, 0)
    try:
        return re.compile(pattern, value)
    except re.error:
        return None


def _split_regex(key: str) -> tuple[str, str] | None:
    if len(key) >= 2 and key.startswith("/"):
        end = key.rfind("/")
        if end > 0:
            return key[1:end], key[end + 1:]
    return None


def matches(key: str, text: str, *, case_sensitive: bool = False, whole_word: bool = False) -> bool:
    """``text`` 须已经过 :func:`normalize`（同样的 case_sensitive）。"""
    regex = _split_regex(key)
    if regex is not None:
        compiled = _regex(*regex)
        return bool(compiled and compiled.search(text))
    needle = normalize(key, case_sensitive=case_sensitive)
    if not needle:
        return False
    if not whole_word or _CJK.search(needle):
        return needle in text
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", text) is not None
