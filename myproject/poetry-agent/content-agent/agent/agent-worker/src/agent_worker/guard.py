"""Heuristics for model output (contract section 6, rules 5 and 6).

Rule 5: a forbidden capability (publish / retract / verify_source / set_verified / delete_content /
execute_sql) used as an *instruction or call* rejects the whole output. A descriptive or negated
mention ("agents cannot publish", "发布前须人工核验") does not.

Rule 6: no item may assert that something *is* verified/published ("已核验", "已发布", "is VERIFIED").
A negated or conditional mention ("尚未核验", "until VERIFIED") is fine.

Both are heuristics over free text. They are one layer of three: the other two are Java's own
vocabulary checks and the absence of any publishing tool in the DeerFlow allow-list. The boundary is
pinned by ``tests/test_guard.py``.

How rule 5 decides, per sentence and per capability mention:

1. exempt if the mention is negated shortly before it ("不能 publish", "do not call publish_x") and no
   strong request word follows the negation ("不要犹豫,请立即发布" is still a request);
2. exempt if the sentence is about a human actor ("请人工发布", "reviewer may publish");
3. exempt if what follows is descriptive ("publish is disabled", "发布流程");
4. otherwise flagged when it has call syntax ``publish(``, follows a request word in its clause
   ("please publish", "请发布", "run execute_sql"), or opens a clause ("Publish the work.").
"""
from __future__ import annotations

import re

_SENTENCE_SPLIT = re.compile(r"[。！？!?；;\n]|\.(?=\s|$)")
_SUBCLAUSE_SPLIT = re.compile(r"[,，、]")

# capability -> compiled patterns that name it
_Z_STOP = "前后人流程状态版本闸门权限环节时之的了过审核门禁能力功能动作者记录日期时间渠道平台计划"
_CAPABILITY_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "publish": [
        re.compile(r"(?<![A-Za-z_])publish(?![A-Za-z_])", re.IGNORECASE),
        re.compile(rf"发布(?![{_Z_STOP}])"),
    ],
    "retract": [
        re.compile(r"(?<![A-Za-z_])retract(?![A-Za-z_])", re.IGNORECASE),
        re.compile(rf"撤回(?![{_Z_STOP}])"),
    ],
    "verify_source": [
        re.compile(r"(?<![A-Za-z0-9_])verify_source(?![A-Za-z0-9_])", re.IGNORECASE),
        re.compile(r"(?:核验|验证)来源(?![的前后人流程状态权限能力功能])"),
    ],
    "set_verified": [
        re.compile(r"(?<![A-Za-z0-9_])set_verified(?![A-Za-z0-9_])", re.IGNORECASE),
        re.compile(r"(?:置为|设为|设置为|标记为)\s*VERIFIED", re.IGNORECASE),
    ],
    "delete_content": [
        re.compile(r"(?<![A-Za-z0-9_])delete_content(?![A-Za-z0-9_])", re.IGNORECASE),
        re.compile(r"删除内容(?![的前后人流程状态权限能力功能])"),
    ],
    "execute_sql": [
        re.compile(r"(?<![A-Za-z0-9_])execute[_ ]sql(?![A-Za-z0-9_])", re.IGNORECASE),
        re.compile(r"执行\s*SQL", re.IGNORECASE),
    ],
}

_NEGATION = re.compile(
    r"请勿|请不要|请别|切勿|严禁|禁止|不得|不能|不可|不应|不会|不许|不准|不允许|不具备|不再|不要|无法|无权|"
    r"没有权限|并非|勿|别|"
    r"\b(?:do\s+not|don'?t|does\s+not|doesn'?t|must\s+not|mustn'?t|should\s+not|shouldn'?t|may\s+not|"
    r"cannot|can'?t|can\s+not|never|not|no|without|unable|forbid\w*|prohibit\w*|disallow\w*|"
    r"isn'?t|aren'?t|won'?t|there\s+is\s+no|has\s+no|have\s+no)\b",
    re.IGNORECASE,
)
# Words that (re)assert a request. After a negation they cancel its exemption.
_STRONG_MARKER = re.compile(
    r"请|务必|必须|立即|立刻|马上|赶紧|现在就|随后|然后|接着|再|"
    r"\b(?:please|kindly|now|then|must|immediately|just|go\s+ahead|make\s+sure\s+to|you\s+should|"
    r"you\s+must|you\s+need\s+to|need\s+to|let'?s|proceed\s+to|first|next|afterwards?)\b",
    re.IGNORECASE,
)
# Adverbs that turn a bare capability name into an order ("直接 verify_source ..."). They count for
# rule 4 only. They must NOT cancel a negation's exemption: "不要直接 publish" is a refusal.
_DIRECT_MARKER = re.compile(r"直接|径直|干脆|\b(?:directly|simply|straight\s+away)\b", re.IGNORECASE)
_WEAK_MARKER_TAIL = re.compile(
    r"(?:\b(?:call|invoke|execute|run|trigger|use|perform)\b|调用|执行|触发|运行|使用|进行)"
    r"\s*(?:the\s+|a\s+)?[`\"'「『（(]*$",
    re.IGNORECASE,
)
_HUMAN_ACTOR = re.compile(
    r"由人工|人工|人类|审核人|审核者|评审人|发布人|编辑|史料审核|reviewer|human|editor|by\s+a\s+person|an?\s+admin",
    re.IGNORECASE,
)
_DESCRIPTIVE_AFTER = re.compile(
    r"^\s*(?:is|are|was|were|has|have|will|would|can|cannot|can't|may|might|should|status|gate|flow|"
    r"workflow|pipeline|permission|capability|tool|action|api|endpoint|step|state|button|right|rights|"
    r"operation|function|command)\b",
    re.IGNORECASE,
)
_CALL_SYNTAX = re.compile(r"^\s*\(")
_BULLET = re.compile(r"^[\s\-*•·>#\d.、)）\]]+")


def _window(before: str) -> str:
    return before[-40:]


def _negated(before: str) -> bool:
    """True if a negation sits shortly before the mention and no strong request word follows it."""
    window = _window(before)
    last = None
    for match in _NEGATION.finditer(window):
        last = match
    if last is None:
        return False
    return _STRONG_MARKER.search(window[last.end():]) is None


def _flagged(sentence: str, start: int, end: int) -> bool:
    before, after = sentence[:start], sentence[end:]
    call = bool(_CALL_SYNTAX.match(after))
    if _negated(before):
        return False
    sub_prefix = _SUBCLAUSE_SPLIT.split(before)[-1]
    if _HUMAN_ACTOR.search(_window(before)) or _HUMAN_ACTOR.search(sub_prefix):
        return False
    if call:
        return True
    if _DESCRIPTIVE_AFTER.match(after):
        return False
    if (_STRONG_MARKER.search(sub_prefix) or _DIRECT_MARKER.search(sub_prefix)
            or _WEAK_MARKER_TAIL.search(sub_prefix)):
        return True
    return _BULLET.sub("", sub_prefix).strip() == "" and ":" not in before and "：" not in before


def find_forbidden_imperatives(text: str) -> list[str]:
    """Capability names used as an instruction or call anywhere in ``text``."""
    found: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(text or ""):
        if not sentence.strip():
            continue
        for capability, patterns in _CAPABILITY_PATTERNS.items():
            if capability in found:
                continue
            for pattern in patterns:
                if any(_flagged(sentence, m.start(), m.end()) for m in pattern.finditer(sentence)):
                    found.append(capability)
                    break
    return found


# ---------------------------------------------------------------------------------------------
# Rule 6: assertions of verified / published state
# ---------------------------------------------------------------------------------------------
_ASSERTION = re.compile(
    r"已(?:经)?(?:核验|验证|发布)|(?:核验|验证)(?:已)?通过|"
    r"(?:状态|标记|标注|置|设|设置|更新)(?:为|成|是|:|：)\s*(?:VERIFIED|PUBLISHED)|"
    r"(?:状态)\s*(?:VERIFIED|PUBLISHED)|"
    r"\b(?:is|are|was|were|been|now|marked|set|status\s*[:=]?|as)\s+(?:to\s+)?(?:verified|published)\b|"
    r"\bstatus\s*[:=]\s*(?:verified|published)\b",
    re.IGNORECASE,
)
_HEDGE = re.compile(
    r"未|尚未|没有|没|无|不|非|待|须|需|才能|才可|之前|之后|前|直到|是否|如果|若|一旦|要求|"
    r"\b(?:not|never|no|until|before|pending|unless|if|once|whether|yet|after|require\w*|needs?|must|should|"
    r"cannot|only)\b",
    re.IGNORECASE,
)


def find_assertions(text: str) -> list[str]:
    """Snippets that state something as already verified/published (not hedged by a negation)."""
    hits: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(text or ""):
        for match in _ASSERTION.finditer(sentence):
            if _HEDGE.search(sentence[max(0, match.start() - 24): match.start()]):
                continue
            hits.append(match.group(0))
    return hits


# ---------------------------------------------------------------------------------------------
# Rule 7 (output hygiene): model output is data; refuse markup that could be rendered or executed
# ---------------------------------------------------------------------------------------------
_ACTIVE_MARKUP = re.compile(
    r"<\s*/?\s*(?:script|iframe|object|embed|style|svg|img|link|meta|form)\b|javascript\s*:|"
    r"\bon(?:error|load|click|mouseover|focus)\s*=|data\s*:\s*text/html",
    re.IGNORECASE,
)
_INVISIBLE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff]")


def find_active_markup(text: str) -> bool:
    return bool(_ACTIVE_MARKUP.search(text or ""))


def has_invisible(text: str) -> bool:
    return bool(_INVISIBLE.search(text or ""))
