"""The system records what the candidate says in a mock interview (SPEC-MOCK-INTERVIEW-V2 §3.3).

The interviewer used to be asked to save each answer with a tool, so one forgotten call left the
question "unanswered" in the report. The answer is now written by the service before the model runs,
onto the question on the table: the last question asked, if it was not skipped or swapped away.
Words that arrive when nothing is on the table (the greeting, the self-introduction, "下一题"
after a skip) are not an answer and are not recorded.
"""

from __future__ import annotations

import copy
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
        r"(我想|我要|请|麻烦)?跳过(这|本|此)?(一)?(个|题|道|道题|个问题)?(吧|吗|啊|呀|了)?",
        r"(我想|我要|请|麻烦)?(结束|终止|停止)(这场|本场|面试|吧|了)*",
        r"没听(清|清楚|见|明白)(楚)?",
        r"(能|可以|麻烦|请)?(再|重新)(说|讲|问|念)(一|1)?(遍|次|下)(吗|吧|啊)?",
        r"(请|麻烦)?重复(一下|一遍|下)?(问题|题目|刚才的问题)?(吗|吧)?",
    )
)
#: Said before a steering phrase and meaning nothing by themselves ("好的，下一题", "嗯，没听清").
_FILLERS = frozenset({"好", "好的", "嗯", "嗯嗯", "那", "那就", "行", "好吧", "呃", "哦"})
_NOT_WORDS = re.compile(r"[\s。，、！？!?,.;；：:~…\-—]+")
#: How many recent message ids a session remembers. A resend comes seconds after the first try, so
#: the last few are enough; the list lives in `coverage` and must not grow with the interview.
_REMEMBERED_MESSAGES = 50


def is_steering_message(text: str) -> bool:
    """True for a message that talks to the interview rather than to the question: 下一题, 换一题,
    跳过, 结束, 没听清, 能再说一遍吗. Such a message is not part of the answer."""
    words = _NOT_WORDS.sub("", text)
    if not words:
        return False
    # "没听清，能再说一遍吗" is two steering phrases in one breath, and "好的，下一题" is one with a
    # filler in front. A filler on its own is an answer ("好的" to "可以开始吗？").
    parts = [part for part in _NOT_WORDS.split(text.strip()) if part]
    while len(parts) > 1 and parts[0] in _FILLERS:
        parts = parts[1:]
    joined = _NOT_WORDS.sub("", "".join(parts))
    # Unpunctuated, the filler is glued to the phrase ("那就换一题吧"): try it with the filler off.
    candidates = [joined] + [
        joined[len(f):] for f in sorted(_FILLERS, key=len, reverse=True)
        if joined.startswith(f)
    ]
    return any(p.fullmatch(c) for c in candidates for p in _STEERING) or all(
        any(p.fullmatch(part) for p in _STEERING) for part in parts
    )


def records_mock_answer(
    *, turn: str | None, runtime_skill: str, default_skill: str, mock_session_id: str | None
) -> bool:
    """Only the practice skill of the interview turn records answers. A turn that switched to
    another skill of the role, such as archiving a real interview, is not a mock answer."""
    return turn == "mock_session" and runtime_skill == default_skill and bool(mock_session_id)


async def record_mock_answer(
    db: AsyncSession,
    *,
    profile_id: str,
    mock_session_id: str,
    text: str,
    message_id: str | None = None,
) -> str | None:
    """Write `text` as the answer to the question on the table. Returns the attempt id, or None
    when nothing is on the table. Further words on the same question extend the same answer.

    `message_id` is the id the client gave this message. The same id again is a resend (the retry
    button, a double click) and is not recorded twice; the same words under a new id are a new
    message, because a candidate can say "是的" twice and mean it. No id means no de-duplication."""
    session = await InterviewStore(db).get_mock_session(mock_session_id)
    if session is None or session.profile_id != profile_id:
        raise PermissionError("Mock session outside this profile")
    words = text.strip()
    if session.status != MockSessionStatus.ACTIVE or not words or is_steering_message(words):
        return None

    state = session.coverage or {}
    # Checked before looking at the table: a retry can arrive after the interviewer has already
    # moved on, and the first try's answer must stay under the question it was given to.
    if message_id and message_id in (state.get("recorded_messages") or []):
        return None
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
    if message_id:
        # A new dict, as the guards do: an in-place change to a JSON column is not noticed.
        remembered = copy.deepcopy(state)
        kept = [*(remembered.get("recorded_messages") or []), message_id]
        remembered["recorded_messages"] = kept[-_REMEMBERED_MESSAGES:]
        session.coverage = remembered
    await db.commit()
    return attempt_id
