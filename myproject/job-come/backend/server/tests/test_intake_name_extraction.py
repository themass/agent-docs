"""An answer to 「你的姓名是？」 must become a name, not the sentence.

Production found this: typing "我的名字叫李测试" in the intake interview stored exactly
that string in `contact.name`, which the review step shows and the exported resume
prints. The intake module's own contract is "store the user's text as typed" — and that
contract is right, because paraphrasing is how invented facts get in. Recovering the one
token the question asked for is not paraphrasing.

The failure was silent in the way that matters: nothing errored, the profile looked
filled in, and the bad value only surfaced on a resume that went to a real employer.
"""

from __future__ import annotations

import pytest

from jc.schemas.profile_payload import ProfilePayload
from jc.services.intake_service import extract_name, record_intake_answers

#: (answer the user typed, name that belongs in the field)
SPOKEN_FORMS = [
    ("我的名字叫李测试", "李测试"),
    ("我叫李四", "李四"),
    ("我是王五", "王五"),
    ("我的名字是李四", "李四"),
    ("我的姓名是 Tom", "Tom"),
]

#: The label form a person filling a form would type.
LABELLED_FORMS = [
    ("姓名：王五", "王五"),
    ("名字: 王五", "王五"),
]

#: Trailing clauses the same sentence tends to carry.
TRAILING = [
    ("我的名字叫李测试，叫我小李就行", "李测试"),
    ("张三，来自北京", "张三"),
]

#: Bare values, including non-Chinese names, must pass through untouched.
BARES = [
    ("李测试", "李测试"),
    ("Tom Smith", "Tom Smith"),
    ("欧阳娜娜", "欧阳娜娜"),
]

#: Answers that carry nothing to strip keep their original — writing an empty name would
#: be worse than an awkward one the user can correct on the next screen.
UNCHANGED = [
    "我叫",
    "a",
]


@pytest.mark.parametrize("typed,expected", SPOKEN_FORMS + LABELLED_FORMS + TRAILING + BARES)
def test_extract_name_recovers_the_name(typed, expected):
    assert extract_name(typed) == expected


@pytest.mark.parametrize("typed", UNCHANGED)
def test_extract_name_never_returns_empty(typed):
    assert extract_name(typed).strip()


def test_a_name_answer_lands_in_the_field_as_just_the_name():
    """End to end through the same write path both callers use."""
    from jc.schemas.intake import IntakeAnswerInput

    payload = ProfilePayload()
    applied, stored = record_intake_answers(
        payload,
        [
            IntakeAnswerInput(
                question_id="q_name",
                question="你的姓名是？",
                target_path="contact.name",
                answer="我的名字叫李测试",
            )
        ],
    )
    assert stored == 1
    assert [w.path for w in applied] == ["contact.name"]
    assert payload.contact.name == "李测试", (
        "the whole sentence reached the name field, which is what the exported resume "
        "would then print"
    )
