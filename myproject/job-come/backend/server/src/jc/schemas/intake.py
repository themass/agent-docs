"""Conversational intake schemas: building a profile by asking instead of parsing.

The trust class here is the same as `evidence.py` — every value is **typed by the user**,
so it may be written to the profile verbatim. No model is in this path. What makes intake
different from evidence answers is only that it may write to *structured* fields
(`contact.name`, `experiences[i].scope`) rather than only appending to
`evidence_answers`, because an interview that cannot fill in a name can never produce a
document.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from jc.schemas.evidence import MetricCandidateItem


class IntakeQuestionItem(BaseModel):
    id: str
    stage: str
    target_path: str
    #: Where the answer lands, in the user's words. The raw `target_path` is an
    #: implementation detail and must not be the thing shown next to a question.
    label: str = ""
    question: str
    rationale: str
    #: `text` | `long_text` | `list`
    input_kind: str = "text"
    examples: list[str] = Field(default_factory=list)
    #: Clickable sentence shapes, for the achievement questions whose answer is a figure.
    #: Reuses the evidence-panel item type because it is the same affordance asking for
    #: the same thing: a second near-identical shape would drift from this one and give
    #: the two panels different behaviour for one user intent.
    metrics: list[MetricCandidateItem] = Field(default_factory=list)
    required: bool = True


class IntakeAnsweredItem(BaseModel):
    """A question the user already answered, with what they said.

    Carried separately from `questions` on purpose. Putting answered questions back into
    the pending list would break two things at once: the interview would stop being able
    to terminate, and the progress counts would never reach done. But leaving them out of
    the response entirely is what made the interview write-once — the user could see that
    `experiences[0].scope` had been written and had no way to look at it or fix a typo.
    """

    question_id: str
    target_path: str
    question: str
    #: The profile location in the user's words, e.g. 「某某科技 · 后端专家 · 负责范围」.
    label: str
    answer: str


class IntakeStageItem(BaseModel):
    id: str
    label: str
    remaining: int
    done: bool


class IntakePlanResponse(BaseModel):
    #: `empty` | `skeleton` | `stale` | `complete` — what the interview is for.
    mode: str
    role_family: str
    role_label: str
    questions: list[IntakeQuestionItem] = Field(default_factory=list)
    #: Already-answered questions, newest last, so the user can review and revise them.
    answered: list[IntakeAnsweredItem] = Field(default_factory=list)
    stages: list[IntakeStageItem] = Field(default_factory=list)
    answered_count: int = 0
    #: True when the profile holds enough real material to generate a draft.
    can_generate: bool = False
    #: What is still missing before generation, phrased for the user.
    blocking: list[str] = Field(default_factory=list)
    #: Profile version, so the client can tell a stale plan from a current one.
    version: int = 0


class IntakeAnswerInput(BaseModel):
    question_id: str
    target_path: str
    question: str
    answer: str = Field(min_length=1, max_length=4000)


class IntakeAnswerRequest(BaseModel):
    answers: list[IntakeAnswerInput] = Field(default_factory=list, max_length=20)


class IntakeSplitRequest(BaseModel):
    """One dictated answer to be broken into the points it contains."""

    question_id: str
    target_path: str
    answer: str = Field(min_length=1, max_length=8000)


class IntakeSplitSegment(BaseModel):
    """One candidate bullet, with the question id and profile slot it would occupy.

    Both ids are resolved server-side rather than left to the client. The slot a segment
    lands in depends on how many highlights the role already holds, and the question id
    is what marks that slot answered — a client deriving either would be a second
    implementation of the plan's slot rule, and the failure mode is silent: answers that
    mark the wrong question, so the interview keeps asking for a bullet it already has.
    """

    #: The plan's id for the slot this segment fills, so submitting it answers that
    #: question rather than re-recording the one the user was looking at.
    question_id: str
    text: str
    target_path: str
    label: str


class IntakeSplitResponse(BaseModel):
    """What the split *would* write. Nothing is stored by asking.

    A preview rather than a direct write, because a punctuation-based split can land a
    boundary in the wrong place, and the one thing intake guarantees is that the user saw
    what went into their profile. They edit or merge the segments and submit them as
    ordinary answers.
    """

    question_id: str
    segments: list[IntakeSplitSegment] = Field(default_factory=list)
    #: True when the answer held more than one point, i.e. the split is worth showing.
    split: bool = False


class IntakeAppliedWrite(BaseModel):
    """One write that landed on the profile, in terms the user can check.

    `path` is kept for debugging and for the API contract; `label` and `value` are what
    the UI shows. A confirmation the user cannot verify ("已写入 experiences[0].scope")
    is not a confirmation — the whole reason to surface a profile write is that it can be
    checked against what they meant to say.
    """

    path: str
    label: str
    value: str


class IntakeAnswerResponse(BaseModel):
    profile_id: str
    version: int
    stored: int
    #: Structured fields the answers filled in, as dotted paths. Kept for API callers;
    #: the UI reads `applied` instead, which carries human labels and the stored text.
    applied_paths: list[str] = Field(default_factory=list)
    applied: list[IntakeAppliedWrite] = Field(default_factory=list)
    plan: IntakePlanResponse
