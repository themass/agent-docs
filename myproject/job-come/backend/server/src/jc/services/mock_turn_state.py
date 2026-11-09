"""The interview's state, and the one place it changes (ADR-008 step 2).

Pure: no database, no model. `apply(state, event)` is the only transition for a candidate's
message. It returns the new state, what the interviewer says (as kinds; the text is written by
the caller), and whether `mock_flow.decide` must choose the next step. `ask`, `open_qa` and
`remember` are the other transitions: the server asking a question, opening the candidate's turn,
and recording what was last said. The state converts to `mock_flow.FlowState`, so `decide` is the
only rule for what comes next.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from jc.services.mock_flow import FlowState, Turn
from jc.services.mock_turn_events import Event


class Say:
    """What the interviewer says, by kind. Fixed wording is supplied here; written wording is None
    and is supplied by the caller (the opening needs the company and title, a question is worded
    by the model)."""

    OPENING = "opening"              # text from the caller
    INTRO_ACK = "intro_ack"          # fixed
    SKIP_ACK = "skip_ack"            # fixed
    REPEAT = "repeat"                # the last thing said, exactly
    CLOSING = "closing"              # fixed
    QA_OPEN = "qa_open"              # fixed
    CANDIDATE_ANSWER = "candidate_answer"  # text from the caller (model, checked)


FIXED = {
    Say.INTRO_ACK: "好，谢谢你的介绍。",
    Say.SKIP_ACK: "好，我们换一题。",
    Say.CLOSING: "今天的面试就到这里，谢谢你的时间。这场面试的报告可以在“面试归档”里查看。",
    Say.QA_OPEN: "我的问题都问完了。你有什么想问我的吗？",
}


@dataclass(frozen=True)
class Said:
    kind: str
    text: str | None = None   # None: the caller supplies it (see Say)


@dataclass(frozen=True)
class TurnState:
    opening_sent: bool = False
    intro_done: bool = False
    #: Every question put to the candidate, in order (kind, parent for follow-ups).
    asked: tuple[Turn, ...] = ()
    #: How many of `asked` have been answered or skipped. The one not counted is on the table.
    answered: int = 0
    closed_mains: frozenset[str] = frozenset()
    candidate_qa: bool = False
    ended: bool = False
    #: What the interviewer said last, exactly. "没听清" repeats it.
    last_said: str | None = None

    @property
    def on_table(self) -> bool:
        return bool(self.asked) and self.answered < len(self.asked)

    def flow(self, *, main_limit: int, followup_limit: int) -> FlowState:
        return FlowState(
            opening_sent=self.opening_sent,
            intro_done=self.intro_done,
            asked=self.asked,
            answered=self.answered,
            closed_mains=self.closed_mains,
            candidate_qa=self.candidate_qa,
            ended=self.ended,
            main_limit=main_limit,
            followup_limit=followup_limit,
        )


@dataclass(frozen=True)
class Result:
    state: TurnState
    says: tuple[Said, ...] = ()
    #: True when `decide` must choose the next step on the new state.
    advance: bool = False


def _said(kind: str) -> Said:
    return Said(kind, FIXED.get(kind))


def apply(state: TurnState, event: Event) -> Result:
    """The transition for one candidate message. One row per case of ADR-008 §3."""
    if event is Event.EMPTY:
        return Result(state)

    if event is Event.END:
        return Result(replace(state, ended=True), (_said(Say.CLOSING),))

    if event is Event.OPEN:
        if state.opening_sent:
            return Result(state)
        return Result(replace(state, opening_sent=True), (Said(Say.OPENING),))

    if not state.opening_sent:
        raise ValueError(f"{event} before the opening: the server sends the opening first")

    if event is Event.INTRO:
        if state.intro_done:
            raise ValueError("the introduction is already done")
        return Result(replace(state, intro_done=True), (_said(Say.INTRO_ACK),), advance=True)

    if event is Event.ANSWER:
        if not state.on_table:
            return Result(state)
        return Result(replace(state, answered=len(state.asked)), advance=True)

    if event is Event.SKIP:
        if not state.on_table:
            return Result(state, advance=True)
        on_table = state.asked[-1]
        # Skipping a main, or a follow-up on it, moves on from that main: it is not followed up.
        main_id = on_table.question_id if on_table.kind == "main" else on_table.parent_question_id
        closed = state.closed_mains | ({main_id} if main_id else frozenset())
        return Result(
            replace(state, answered=len(state.asked), closed_mains=closed),
            (_said(Say.SKIP_ACK),),
            advance=True,
        )

    if event is Event.REPEAT:
        if not state.last_said:
            return Result(state)
        return Result(state, (Said(Say.REPEAT, state.last_said),))

    if event is Event.TALK:
        # Words with nothing on the table are not an answer. Nothing is asked for them either: the
        # interview's next step is decided as it would be after any turn with no question out.
        return Result(state, advance=True)

    if event is Event.CANDIDATE_QUESTION:
        return Result(state, (Said(Say.CANDIDATE_ANSWER),))

    raise ValueError(f"no transition for {event}")


def ask(
    state: TurnState, question_id: str, *, kind: str, parent_id: str | None = None,
) -> TurnState:
    """The server puts a question to the candidate. Only when nothing is on the table."""
    if state.on_table:
        raise ValueError("a question is already on the table")
    if kind not in ("main", "followup"):
        raise ValueError("kind must be 'main' or 'followup'")
    if kind == "followup" and parent_id is None:
        raise ValueError("a follow-up needs its main question")
    return replace(state, asked=(*state.asked, Turn(question_id, kind, parent_id)))


def open_qa(state: TurnState) -> Result:
    """The candidate's turn to ask questions. The caller has checked the interview may end here."""
    if state.candidate_qa:
        return Result(state)
    if state.on_table:
        raise ValueError("cannot open the candidate's turn with a question on the table")
    return Result(replace(state, candidate_qa=True), (_said(Say.QA_OPEN),))


def remember(state: TurnState, text: str) -> TurnState:
    """Record the exact words the interviewer just said, so "没听清" can repeat them."""
    return replace(state, last_said=text)
