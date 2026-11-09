"""One question per interview reply.

The interviewer is asked for one question per turn, and the acceptance checklist counts it, but
the model does not keep to that on its own: a live run put two questions in most replies. So a
practice reply with two question marks is asked once more to keep one, and only the corrected
reply reaches the candidate. Showing the first and correcting it after would leave the candidate
with two questions in front of them.
"""

from __future__ import annotations

import re

_QUESTION_MARKS = re.compile(r"[?？]")

REWRITE_MESSAGE = (
    "你上一条回复里有两个问题。请只保留其中最重要的一个，用同样的语气，"
    "沿用候选人刚说过的原话或数字，把这一条重新说一遍。只输出这条回复本身，"
    "不解释，不要调用任何工具。"
)


def question_count(text: str) -> int:
    return len(_QUESTION_MARKS.findall(text or ""))


def needs_one_question(text: str) -> bool:
    return question_count(text) > 1


# A main question must stand alone. These openings point back at something the candidate said, in
# this interview or another one; as a main question they are asked to a candidate who never said it.
_BACK_REFERENCE = re.compile(
    r"^(你|您)(刚|刚才|刚刚|又|说|提到|讲)|^我没问|^(你|您)(之前|前面|上一)(说|讲|提到)"
)


def refers_to_earlier_talk(text: str) -> bool:
    """True for a question that opens by pointing back at an earlier answer ("你刚说……")."""
    return bool(_BACK_REFERENCE.search((text or "").strip()))

