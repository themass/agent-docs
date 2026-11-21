"""Reject editor instructions that try to take control away from the governed workflow.

Editor text is *untrusted task material*, and the real defences are structural (no publish tool, DRAFT
only, Java revalidation). This guard exists to give the editor an early, explicit 422 for requests
that can never be honoured, without refusing legitimate prose that merely mentions a forbidden word
("列出缺口,不要 publish" is fine; "请执行 publish" is not).
"""
from __future__ import annotations

import re

_FORBIDDEN = r"(?:publish|retract|verify[_ ]source|set[_ ]verified|delete[_ ]content|execute[_ ]sql|发布|撤回|核验来源|删除内容|执行\s*sql)"
_NEGATION = r"(?:不要|不得|不能|禁止|别|勿|never|don'?t|do not|must not|without)"

# 1. attempts to override the governing rules
_OVERRIDE = re.compile(
    r"(?:ignore|disregard|forget)\s+(?:all\s+|any\s+)?(?:the\s+)?(?:previous|prior|above|earlier)\s+(?:instructions?|rules?|prompts?)"
    r"|忽略(?:之前|以上|上面|先前|所有)?的?(?:指令|规则|提示|约束)"
    r"|无视(?:之前|以上|先前|所有)?的?(?:指令|规则|提示|约束)"
    r"|(?:你现在是|you are now)\s*(?:系统|管理员|system|admin|root)",
    re.IGNORECASE,
)
# 2. an imperative request to use a forbidden capability
_IMPERATIVE = re.compile(
    rf"(?:请|please|then|并且?|然后|接着|立即|立刻|直接|go ahead and|you (?:must|should|need to)|(?:^|[\n。;;]))\s*"
    rf"(?:执行|调用|运行|run|call|execute|do|perform|use)?\s*{_FORBIDDEN}",
    re.IGNORECASE,
)


def violation(text: str) -> str | None:
    """Return a short human-readable reason, or None when the text is acceptable."""
    if _OVERRIDE.search(text):
        return "指令试图覆盖系统规则(例如“忽略之前的指令”)。"
    for match in _IMPERATIVE.finditer(text):
        window = text[max(0, match.start() - 12): match.start() + 1]
        if re.search(_NEGATION, window, re.IGNORECASE):
            continue
        # a bare noun mention at the very start of a sentence is not an imperative on its own
        verb_present = re.search(r"执行|调用|运行|\b(?:run|call|execute|do|perform|use)\b", match.group(0), re.IGNORECASE)
        lead_present = re.search(r"请|please|then|并|然后|接着|立即|立刻|直接|go ahead|must|should|need to", match.group(0), re.IGNORECASE)
        if verb_present or lead_present:
            return "指令请求执行发布、撤回、核验来源、删除或 SQL 等本通道不具备的能力。"
    return None
