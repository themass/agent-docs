"""The interviewer's opening, written by the server rather than by the model.

The opening says the same things every time: who the interviewer is, the company and role, how
many questions, and a request for a one-to-two minute self-introduction. A model run for it took
up to ten minutes live (2026-11-08), and the model adds nothing the template does not already say.
So the first reply of an interview is this text, and the model takes over from the candidate's
self-introduction.

The watchdog covers a model run that goes quiet: after WATCHDOG_SEC without a first event the run
is cancelled and the candidate gets the opening (when none has been said yet) or a holding line.
"""

from __future__ import annotations

#: How long a model run may stay silent before the server answers in its place.
WATCHDOG_SEC = 60.0

#: Said to the model once, before its first turn after the opening, so it does not greet again.
BRIEF_AFTER_OPENING = (
    "（系统：面试开场白已由系统发出，内容是「{opening}」。不要重复开场，"
    "直接回应候选人接下来的自我介绍，然后问第一个正式问题。）\n"
)

HOLDING_TEXT = "面试官这边稍有延迟，请稍等片刻；如果您想先补充刚才的回答，可以直接再发一次。"


def opening_text(company: str | None, title: str | None) -> str:
    where = f"{company or ''}{title or ''}".strip()
    role = f"{where}的面试官" if where else "这个岗位的面试官"
    head = f"你好，我是{role}，今天由我来面你。"
    return (
        f"{head}大概五到六个问题，中间我会顺着你的回答追问，你随时可以说“结束”。"
        "先请你用一到两分钟做个自我介绍吧。"
    )


def opening_due(state: dict) -> bool:
    """True before any question has been asked in this interview and before the opening was said."""
    return not state.get("asked") and not state.get("opening_sent")
