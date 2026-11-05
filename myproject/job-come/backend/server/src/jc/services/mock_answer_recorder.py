"""The system records what the candidate says in a mock interview (SPEC-MOCK-INTERVIEW-V2 §3.3).

The interviewer used to be asked to save each answer with a tool, so one forgotten call left the
question "unanswered" in the report. The answer is now written by the service before the model runs,
onto the question on the table: the last question asked, if it was not skipped or swapped away.
Words that arrive when nothing is on the table (the greeting, the self-introduction, "下一题"
after a skip) are not an answer and are not recorded.
"""

from __future__ import annotations

import re

from agentkit.common.ids import new_id
from sqlalchemy.ext.asyncio import AsyncSession

from jc.models.enums import MockSessionStatus
from jc.models.interview import AnswerAttempt
from jc.stores.interview_store import InterviewStore

# The whole message, once spaces and punctuation are gone, has to be one of these. A closed list
# on purpose: a sentence that merely contains "跳过" or "结束" is an answer, and must stay one.
_STEERING = tuple(
    re.compile(pattern)
    for pattern in (
        r"(我想|我要|请|麻烦|直接|好的|好)?(出|来)?(下一|换一|换个|换)(题|道|道题|个题|个问题|下)(吧|吗|啊|呀|了)?",
        r"(请|麻烦)?(继续|接着)(出题|提问|下一题)(吧|吗|啊|呀)?",
        r"(我想|我要|请|麻烦)?跳过(这|本|此)?(一)?(题|道|道题|个问题)?(吧|吗|啊|呀|了)?",
        r"(我想|我要|请|麻烦)?(结束|终止|停止)(这场|本场|面试|吧|了)*",
        r"没听(清|清楚|见|明白)(楚)?",
        r"(能|可以|麻烦|请)?(再|重新)(说|讲|问|念)(一|1)?(遍|次|下)(吗|吧|啊)?",
        r"(请|麻烦)?重复(一下|一遍|下)?(问题|题目|刚才的问题)?(吗|吧)?",
    )
)
_NOT_WORDS = re.compile(r"[\s。，、！？!?,.;；：:~…\-—]+")


def is_steering_message(text: str) -> bool:
    """True for a message that talks to the interview rather than to the question: 下一题, 换一题,
    跳过, 结束, 没听清, 能再说一遍吗. Such a message is not part of the answer."""
    words = _NOT_WORDS.sub("", text)
    if not words:
        return False
    # "没听清，能再说一遍吗" is two steering phrases in one breath.
    parts = [part for part in _NOT_WORDS.split(text.strip()) if part]
    return any(p.fullmatch(words) for p in _STEERING) or all(
        any(p.fullmatch(part) for p in _STEERING) for part in parts
    )


def records_mock_answer(
    *, turn: str | None, runtime_skill: str, default_skill: str, mock_session_id: str | None
) -> bool:
    """Only the practice skill of the interview turn records answers. A turn that switched to
    another skill of the role, such as archiving a real interview, is not a mock answer."""
    return turn == "mock_session" and runtime_skill == default_skill and bool(mock_session_id)


async def record_mock_answer(
    db: AsyncSession, *, profile_id: str, mock_session_id: str, text: str
) -> str | None:
    """Write `text` as the answer to the question on the table. Returns the attempt id, or None
    when nothing is on the table. Further words on the same question extend the same answer."""
    session = await InterviewStore(db).get_mock_session(mock_session_id)
    if session is None or session.profile_id != profile_id:
        raise PermissionError("Mock session outside this profile")
    words = text.strip()
    if session.status != MockSessionStatus.ACTIVE or not words or is_steering_message(words):
        return None

    state = session.coverage or {}
    asked = state.get("asked") or []
    if not asked or state.get("table_closed"):
        return None
    on_table = asked[-1]
    if on_table.get("skipped"):
        return None

    store = InterviewStore(db)
    question = await store.get_question(on_table["question_id"])
    if question is None or question.profile_id != profile_id:
        return None

    attempt = await store.get_latest_attempt_in_session(question.id, mock_session_id)
    if attempt is not None:
        attempt.user_answer = f"{attempt.user_answer}\n{words}"
        attempt_id = attempt.id
    else:
        attempt_id = new_id("attm")
        await store.add_attempt(AnswerAttempt(
            id=attempt_id,
            question_id=question.id,
            profile_id=profile_id,
            mock_session_id=mock_session_id,
            user_answer=words,
            coach_feedback={},
            reference_answer=None,
            is_best=False,
        ))
        question.attempt_count += 1
    await db.commit()
    return attempt_id
