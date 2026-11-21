"""First gate for anything a learner types. Rules only, no model, and a screened message is never forwarded.

The learners are children. Three kinds of input get a fixed, kind reply and go no further:
personal information (in either direction), distress, and content that has no place in a poetry lesson.
The patterns are deliberately short: anything they miss falls through to the router's default decline,
which is also safe. Every reply here is lesson-independent and contains no historical claim.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_PII = re.compile(
    r"1[3-9]\d{9}|\d{6,}|微信|qq|QQ|手机号|电话|住址|家住|我家在|我住在|我叫|我的名字|我姓|"
    r"我在.{1,10}(小学|中学|学校)|哪个学校|身份证|你叫什么|你住"
)
_DISTRESS = re.compile(
    r"不想活|想死|自杀|自残|割腕|被欺负|被打|霸凌|抑郁|好害怕|不想上学|没人爱|没人管|离家出走|太难受了|"
    r"想消失|消失了算了|活着没意思|不想再活|想结束(自己的)?生命|想离开这个世界|不如死了|不想醒来"
)
# Prompt-injection and role-override phrasing. Matched before anything is forwarded; the reply is fixed.
_INJECT = re.compile(
    r"忽略(以上|上面|之前|前面|所有|你的)?.{0,6}(规则|指令|提示|要求|设定)|系统提示|提示词|你的(设定|指令)是什么|"
    r"开发者模式|越狱|扮演.{0,6}(没有|不受).{0,4}限制|从现在开始你是|ignore (all|previous|the above)|system prompt|jailbreak",
    re.IGNORECASE,
)
_CN_DIGIT = str.maketrans({"零": "0", "〇": "0", "一": "1", "二": "2", "两": "2", "三": "3", "四": "4",
                           "五": "5", "六": "6", "七": "7", "八": "8", "九": "9"})
INJECT_REPLY = "这个我不能说。我们接着读诗吧，你最想弄清楚哪一句？"

_UNSAFE = re.compile(r"色情|黄色网|裸|怎么杀人|自制炸|毒品|赌博|政治|选举|台独|法轮")

PII_REPLY = "这些个人的事情不用告诉我，也不要告诉网上的任何人。我们回到这首诗，好吗？"
DISTRESS_REPLY = "听起来你有点难受。这件事很重要，可以告诉爸爸妈妈或者老师，让他们陪着你。等你想读诗的时候，我在这里。"
UNSAFE_REPLY = "这个问题和我们的诗没有关系，我不回答。我们接着读诗吧。"


@dataclass(frozen=True)
class Screen:
    kind: str  # pii | distress | unsafe
    say: str


def _normal(text: str) -> str:
    """Strip separators between digits and map Chinese numerals, so 138-0013-8000 or 一三八 are still caught."""
    t = re.sub(r"(?<=\d)[\s\-—.·()]+(?=\d)", "", text)
    return t.translate(_CN_DIGIT)


def screen(text: str) -> Screen | None:
    if not text:
        return None
    # Distress first: a child in trouble must get the kind reply even if the message also names a school.
    if _DISTRESS.search(text):
        return Screen("distress", DISTRESS_REPLY)
    if _PII.search(text) or re.search(r"1[3-9]\d{9}", _normal(text)):
        return Screen("pii", PII_REPLY)
    if _INJECT.search(text):
        return Screen("inject", INJECT_REPLY)
    if _UNSAFE.search(text):
        return Screen("unsafe", UNSAFE_REPLY)
    return None
