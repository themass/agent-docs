"""Question counting and the back-reference check for an interview's questions.

The one-question rule is kept by the server's flow (ADR-008), which writes each question itself; the
model no longer writes a reply to be corrected.
"""

from __future__ import annotations

import re

_QUESTION_MARKS = re.compile(r"[?？]")

def question_count(text: str) -> int:
    return len(_QUESTION_MARKS.findall(text or ""))




# A main question must stand alone. These openings point back at something the candidate said, in
# this interview or another one; as a main question they are asked to a candidate who never said it.
_BACK_REFERENCE = re.compile(
    r"^(你|您)(刚|刚才|刚刚|又|说|提到|讲)|^我没问|^(你|您)(之前|前面|上一)(说|讲|提到)"
    # "上一题你提到…", "前面你说…", "刚才的回答里你讲…": the same back-reference with the
    # earlier answer named first (2026-11-09 round 8: "上一题你提到支付相关的写操作…" was asked).
    r"|^(上一|上个|上道|前一|前面|刚才|刚刚|上面|之前)[^。？?！!]{0,12}?(说|讲|提到|回答|答)"
)


def refers_to_earlier_talk(text: str) -> bool:
    """True for a question that opens by pointing back at an earlier answer ("你刚说……")."""
    return bool(_BACK_REFERENCE.search((text or "").strip()))

