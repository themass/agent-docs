"""Build a profile from nothing, by asking.

The gap this closes
-------------------
Every path into JC required a file. `ProfileIngestService.parse` needs bytes, and
`evidence_gaps` can only find holes in bullets that already exist — its scanner takes a
bullet as input. So the two users with the most to gain were the two we served worst:

- the person who has **no resume at all** (first real job search, or always hired through
  referrals), and
- the person whose resume is **four years stale**, where the file that exists describes a
  job two levels below the one they now hold.

Both were told to upload something, and both would have had to write the resume
themselves first — which is the work they came here to not do.

Why a separate module from `evidence_gaps`
------------------------------------------
They look similar and are not. `evidence_gaps` asks "this bullet should carry an outcome
and does not" — it is a *repair* pass over existing content, and every question it asks is
anchored to a `field_path` that already exists. Intake has no content to anchor to: it has
to decide **what to ask first when the page is blank**, keep a conversation's worth of
state, and know when there is enough to generate a document. Folding that into the gap
scanner would make a pure function stateful and would give it two incompatible notions of
"next question".

What they share, deliberately, is the trust carrier: an intake answer becomes an
`EvidenceAnswer` on the profile exactly like a gap answer, and the writer and reviewer
already treat those as user-authored source facts. So nothing downstream needs to learn a
new concept, and no model output is ever written into the profile as fact.

Design: a fixed plan, not a free conversation
---------------------------------------------
The questions are a deterministic, ordered plan derived from what the profile is missing,
not a model deciding what to ask next. Three reasons:

1. **It terminates.** A model-driven interview has no natural end and users abandon it.
   Here the user can always see how many steps remain.
2. **It cannot drift.** A free-form interviewer asks a designer for QPS figures, or asks
   for a salary history, or asks the same thing twice in different words.
3. **It is resumable.** State lives in the profile, so closing the tab loses nothing and
   the next question is recomputed rather than remembered.

The model still does the writing — turning answers into resume prose is exactly what the
writer is for. Intake's job is only to collect true material.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

from jc.domain.role_families import RolePlaybook, get_playbook
from jc.schemas.profile_payload import (
    ProfileExperience,
    ProfilePayload,
)
from jc.services.metric_prompts import MetricCandidate, candidates_for

#: An experience with fewer than this many highlights cannot be written up as a role; it
#: renders as a job title with nothing under it, which reads worse than omitting it.
_MIN_HIGHLIGHTS_PER_ROLE = 2

#: Experiences beyond this are not interviewed in detail. A recruiter reads the last two
#: roles closely and skims the rest, so spending 20 questions on a 2012 internship trades
#: the user's patience for a line nobody reads.
_DETAILED_ROLES = 2

#: Below this the profile cannot produce a document at all, regardless of question count.
_MIN_VIABLE_HIGHLIGHTS = 3

#: The most recent role is interviewed until it alone clears the viability floor. Asking
#: two questions and then refusing to generate because three answers were needed is the
#: plan contradicting itself: a plan that can be completed must be a plan that produces a
#: document. `test_the_plan_can_always_reach_viability` locks this relationship.
_MIN_HIGHLIGHTS_LEAD_ROLE = max(_MIN_HIGHLIGHTS_PER_ROLE, _MIN_VIABLE_HIGHLIGHTS)

#: How a highlight slot is introduced, by position. Past the end of this the wording falls
#: back to a plain ordinal rather than inventing superlatives for a fifth item.
_HIGHLIGHT_PROMPTS: tuple[str, ...] = (
    "最有代表性的一件事",
    "第二件值得写的事",
    "还有第三件事吗",
)

_DATE_RE = re.compile(r"(19|20)\d{2}")

#: `experiences[0].scope` -> root / idx / rest. Shared by the plan and `describe_path`.
_INDEXED_PATH_RE = re.compile(r"^(?P<root>[a-z_]+)\[(?P<idx>\d+)\](?:\.(?P<rest>.+))?$")


@dataclass(frozen=True, slots=True)
class IntakeQuestion:
    """One question in the plan, with everything the UI needs to render it.

    `target_path` names where the answer *belongs* in the profile. It is recorded on the
    stored `EvidenceAnswer` so the writer knows which role an answer describes, but
    nothing writes to that path automatically — the user confirms the profile exactly as
    they do after a file upload.
    """

    id: str
    stage: str
    target_path: str
    question: str
    #: Why we are asking, in the user's terms. Shown under the question.
    rationale: str
    #: Where the answer lands, in the user's words. Filled in by `build_intake_plan`,
    #: which is the only place that has the profile needed to resolve it.
    label: str = ""
    #: Shape of answer expected, so the UI can pick an input. `text` | `long_text` | `list`
    input_kind: str = "text"
    #: Role-appropriate examples. Never pre-filled into the answer.
    examples: tuple[str, ...] = ()
    #: Clickable sentence shapes for an achievement question, carried structurally so the
    #: UI can insert one and place the caret on its blank. `examples` stays as the plain
    #: text fallback for questions whose answer is not a figure.
    metrics: tuple[MetricCandidate, ...] = ()
    #: True when the profile cannot produce a resume without this.
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "stage": self.stage,
            "target_path": self.target_path,
            "label": self.label,
            "question": self.question,
            "rationale": self.rationale,
            "input_kind": self.input_kind,
            "examples": list(self.examples),
            "metrics": [m.to_dict() for m in self.metrics],
            "required": self.required,
        }


@dataclass(frozen=True, slots=True)
class IntakeStage:
    id: str
    label: str
    #: Questions remaining in this stage.
    remaining: int
    done: bool

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "remaining": self.remaining, "done": self.done}


@dataclass(frozen=True, slots=True)
class AnsweredQuestion:
    """A question already answered, carried so the user can review and revise it."""

    question_id: str
    target_path: str
    question: str
    label: str
    answer: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "target_path": self.target_path,
            "question": self.question,
            "label": self.label,
            "answer": self.answer,
        }


@dataclass(frozen=True, slots=True)
class IntakePlan:
    """Where this profile is in the interview, and what to ask next."""

    mode: str
    role_family: str
    role_label: str
    questions: list[IntakeQuestion] = field(default_factory=list)
    #: Already answered, oldest first. Kept out of `questions` so the plan still
    #: terminates and the stage counts still reach done.
    answered: list[AnsweredQuestion] = field(default_factory=list)
    stages: list[IntakeStage] = field(default_factory=list)
    answered_count: int = 0
    #: True when the profile holds enough real material to generate a draft.
    can_generate: bool = False
    #: What is still missing before generation, phrased for the user.
    blocking: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "role_family": self.role_family,
            "role_label": self.role_label,
            "questions": [q.to_dict() for q in self.questions],
            "answered": [a.to_dict() for a in self.answered],
            "stages": [s.to_dict() for s in self.stages],
            "answered_count": self.answered_count,
            "can_generate": self.can_generate,
            "blocking": list(self.blocking),
        }


#: Ordered stages. Identity first because it is quick and makes the page stop looking
#: empty; the most recent role next because it carries most of the hiring decision.
_STAGE_LABELS: tuple[tuple[str, str], ...] = (
    ("identity", "基本信息"),
    ("current_role", "最近一份工作"),
    ("achievements", "关键成果"),
    ("history", "更早的经历"),
    ("direction", "目标与方向"),
)


def count_written_evidence(profile: ProfilePayload) -> int:
    """How many pieces of resume material this profile actually holds.

    Counts highlights on experiences and projects, and nothing else. In particular it
    does **not** count `evidence_answers`, which is the bug this function exists to make
    unrepeatable: that list holds every interview answer including 「你的姓名是？」 and
    「留一个联系方式」, so counting its length let a profile pass the viability floor on
    three answers that contained no career content at all. The user was then shown a green
    「可以生成」 over a profile with zero highlights, and the draft that came back was a
    name and a job title.

    Nothing is lost by excluding them, because an interview answer that *is* career
    material gets written into a structured field by `intake_service.apply_answer` and is
    counted here in that form. Gap answers (`missing_outcome` and friends) are excluded on
    purpose too: they add an outcome to a bullet that already exists, so counting them
    would credit the same bullet twice.

    One counter rather than two: `classify_mode` and the generation gate previously each
    computed their own total and disagreed, which is how a profile could be classified
    `complete` and still be refused generation.
    """
    total = sum(len(e.highlights or []) for e in profile.experiences)
    total += sum(len(p.highlights or []) for p in profile.projects)
    return total


def classify_mode(profile: ProfilePayload) -> str:
    """How much the user already has, which decides what the interview is for.

    - `empty` — nothing to work from. The interview builds the profile.
    - `skeleton` — roles exist but carry almost no evidence. This is the shape a stale
      resume has after the user deleted the parts that no longer apply.
    - `stale` — roles have content, but the most recent one ends in the past. A profile
      whose latest role closed two years ago is describing someone else's career.
    - `complete` — enough to generate; the interview becomes optional enrichment.
    """
    if not profile.experiences:
        return "empty"

    if count_written_evidence(profile) < _MIN_VIABLE_HIGHLIGHTS:
        return "skeleton"

    latest = profile.experiences[0]
    if latest.end_date and _DATE_RE.search(latest.end_date):
        return "stale"
    return "complete"


def _identity_questions(profile: ProfilePayload) -> list[IntakeQuestion]:
    out: list[IntakeQuestion] = []
    if not (profile.contact.name or "").strip():
        out.append(
            IntakeQuestion(
                id="identity.name",
                stage="identity",
                target_path="contact.name",
                question="你的姓名是？",
                rationale="简历顶部要用。只会出现在你导出的文件里。",
            )
        )
    if not (profile.contact.email or "").strip() and not (profile.contact.phone or "").strip():
        out.append(
            IntakeQuestion(
                id="identity.contact",
                stage="identity",
                target_path="contact.email",
                question="留一个联系方式（邮箱或手机号）。",
                rationale="没有联系方式的简历，招聘方读完也联系不上你。",
            )
        )
    return out


def _role_label(exp: ProfileExperience | None, idx: int) -> str:
    """How a role is named to the user. One rule, used by questions and by path labels.

    Two places need this and they must agree: a question that says 「在「某某科技 ·
    后端专家」」 and a confirmation that says 「experiences[0]」 read as if they are about
    different things.
    """
    if exp is not None:
        where = f"{exp.company} · {exp.title}".strip(" ·")
        if where:
            return where
    return "最近这份工作" if idx == 0 else f"第 {idx + 1} 段经历"


#: Profile paths that name one fixed field, in the user's words. Indexed paths
#: (`experiences[0].scope`) cannot be a table because the label depends on which company
#: sits at that index, so they are resolved in `describe_path`.
_PLAIN_PATH_LABELS: dict[str, str] = {
    "contact.name": "姓名",
    "contact.email": "邮箱",
    "contact.phone": "手机号",
    "contact.location": "所在城市",
    "summary": "个人简介",
    "preferences.target_roles": "目标岗位",
}


def describe_path(profile: ProfilePayload, path: str) -> str:
    """A profile path in the user's words, e.g. 「某某科技 · 后端专家 · 负责范围」.

    Dotted paths are an implementation detail that leaked into the UI: a user told
    「已写入档案：experiences[0].scope」 cannot tell whether we recorded the right thing,
    which defeats the purpose of showing the write at all. The point of surfacing a write
    is that it can be checked, and it can only be checked in terms the user recognises.

    Falls back to the raw path rather than inventing a name — a wrong label is worse than
    an ugly one, because the user would be checking the wrong field.
    """
    raw = (path or "").strip()
    if not raw:
        return ""
    plain = _PLAIN_PATH_LABELS.get(raw)
    if plain:
        return plain
    if raw == NEW_EXPERIENCE_PATH:
        # Not an index, so `_INDEXED_PATH_RE` would fall through and show the user the
        # raw path. Labelled by what the write does, because that is the part they need
        # to check: the answer becomes a role, ahead of the ones already there.
        return "新的最近一段经历"

    match = _INDEXED_PATH_RE.match(raw)
    if not match or match.group("root") != "experiences":
        return raw
    idx = int(match.group("idx"))
    exp = profile.experiences[idx] if idx < len(profile.experiences) else None
    label = _role_label(exp, idx)
    rest = match.group("rest")
    if not rest:
        return f"{label} · 公司与职位"
    if rest == "scope":
        return f"{label} · 负责范围"
    slot_match = re.match(r"^highlights\[(\d+)\]$", rest)
    if slot_match:
        return f"{label} · 第 {int(slot_match.group(1)) + 1} 条成果"
    if rest == "highlights":
        return f"{label} · 成果"
    return f"{label} · {rest}"


#: `experiences[0].highlights[2]` -> role index / slot. The one parser for the only
#: path shape that can hold more than one point, so the plan and the dictation split
#: cannot disagree about which slot a bullet belongs to.
_HIGHLIGHT_TARGET_RE = re.compile(r"^experiences\[(?P<idx>\d+)\]\.highlights\[(?P<slot>\d+)\]$")


def highlight_slot_ids(idx: int, slot: int) -> tuple[str, str]:
    """The question id and target path for one achievement slot.

    Both are derived here because they are a pair: the plan drops a question whose id is
    already answered, and the answer's id is what marks it answered. A caller that built
    one of the two by hand would produce a question that can never be satisfied or an
    answer that satisfies the wrong slot.
    """
    return f"role.{idx}.highlight.{slot}", f"experiences[{idx}].highlights[{slot}]"


def parse_highlight_target(path: str) -> tuple[int, int] | None:
    """Role index and slot for an achievement path, or None for any other path."""
    match = _HIGHLIGHT_TARGET_RE.match((path or "").strip())
    if not match:
        return None
    return int(match.group("idx")), int(match.group("slot"))


def _highlight_prompt(slot: int) -> str:
    if slot < len(_HIGHLIGHT_PROMPTS):
        return _HIGHLIGHT_PROMPTS[slot]
    return f"第 {slot + 1} 件值得写的事"


def _highlight_metrics(playbook: RolePlaybook) -> tuple[MetricCandidate, ...]:
    """Fillable sentence shapes for an achievement question, not a list of nouns.

    The question used to show `playbook.outcome_metrics`, i.e. 「P99/P95 延迟」「QPS」.
    Those are the right dimensions and the wrong affordance: a user staring at an empty
    box does not learn what to type from a noun. They have to invent the sentence, pick
    the unit, and guess what shape of answer is usable — which is the work they came here
    to have done.

    `metric_prompts` already solved this for the gap-repair flow, and reusing it keeps
    both flows asking for evidence in the same voice. The blanks stay blank: a skeleton
    carries no value, because a plausible-looking default is a fabricated fact the user
    will accept and then have to defend in an interview.

    Returned structurally rather than as text so the UI can offer them the same way the
    evidence panel does — click one, it lands in the textarea with the caret on the
    blank. Rendering them as a 「例如：」 line would be the same information with the
    affordance removed.
    """
    return tuple(candidates_for(playbook, limit=3))


def _role_questions(
    *, idx: int, exp: ProfileExperience | None, playbook: RolePlaybook
) -> list[IntakeQuestion]:
    """Questions for one role, from "which company" through to evidence."""
    stage = "current_role" if idx == 0 else "history"
    label = _role_label(exp, idx)
    out: list[IntakeQuestion] = []

    if exp is None or not (exp.company or "").strip() or not (exp.title or "").strip():
        out.append(
            IntakeQuestion(
                id=f"role.{idx}.identity",
                stage=stage,
                target_path=f"experiences[{idx}]",
                question=(
                    "先说最近这份工作：公司、你的职位、起止时间。"
                    if idx == 0
                    else f"再说{label}：公司、职位、起止时间。"
                ),
                rationale="公司和职级是招聘方判断你量级的第一依据。",
                examples=("某某科技 · 后端技术专家 · 2021-03 至今",),
            )
        )
        return out

    # The scope line is a stored fact now, so a profile that already has one is not
    # asked again. Re-asking a question the user has already answered is the fastest way
    # to make an interview feel broken.
    if not (exp.scope or "").strip():
        out.append(
            IntakeQuestion(
                id=f"role.{idx}.scope",
                stage=stage,
                target_path=f"experiences[{idx}].scope",
                question=f"在「{label}」，你具体负责什么、管多大的范围？",
                rationale="这一句会成为这段经历的开头，决定读者如何理解下面每一条要点。",
                input_kind="long_text",
                examples=(
                    "带 8 人后端团队，负责订单与结算两条主链路",
                    "独立负责一条业务线的全部产品工作，对接 3 个研发团队",
                ),
            )
        )

    # Highlight questions are keyed by their *absolute* slot, not by how many are still
    # missing. Keying them by the shortfall made the id shift every time an answer landed
    # (answer `highlight.0`, the list grows, the next question is computed as `highlight.0`
    # again and is then dropped as already answered) — so the interview silently stopped
    # one answer short of being able to generate.
    have = len(exp.highlights or [])
    minimum = _MIN_HIGHLIGHTS_LEAD_ROLE if idx == 0 else _MIN_HIGHLIGHTS_PER_ROLE
    for slot in range(have, minimum):
        question_id, target_path = highlight_slot_ids(idx, slot)
        out.append(
            IntakeQuestion(
                id=question_id,
                stage="achievements" if idx == 0 else stage,
                target_path=target_path,
                question=(
                    f"在「{label}」，{_highlight_prompt(slot)}？做了什么、最后怎么样了，"
                    "一两句话说清就行。"
                ),
                rationale="这是简历里真正被读的部分。先讲事实，措辞我们来处理。",
                input_kind="long_text",
                metrics=_highlight_metrics(playbook),
            )
        )
    return out


#: Target path meaning "a new most-recent role", as opposed to `experiences[0]` which
#: means "the role currently at index 0". The interview needs both: filling in a blank
#: newest role is an edit, while a stale profile's current job is an **insertion** that
#: pushes the old role down. Spelled as a path rather than a flag on the question so the
#: existing contract (a question names a path, `apply_answer` writes it) still holds and
#: the API schema does not grow a field that only one question would ever set.
NEW_EXPERIENCE_PATH = "experiences[new]"


def _stale_questions(profile: ProfilePayload) -> list[IntakeQuestion]:
    """What to ask when the profile describes a career that stopped some years ago.

    `stale` was classified and then interviewed exactly like `complete`, which made the
    classification pointless: the newest role already has a company, a title and three
    highlights, so every role question was satisfied and the user got asked 「在这之前还
    有别的工作经历吗」 — about the past, when what is missing is the present. A senior
    engineer whose file ends at 2022 would be handed a resume for the job they left.

    One question only. Once the current role is recorded the profile stops being stale,
    and the newest role is then an ordinary empty role — so the existing machinery asks
    for its scope and its highlights with no special case. Asking for an achievement in
    the same breath would have to target `experiences[0]`, which at that moment still
    means the *old* job.

    Optional, not blocking: the user may genuinely be between roles, and refusing to
    generate until they describe a job they do not have is worse than a resume that ends
    last year.
    """
    latest = profile.experiences[0] if profile.experiences else None
    if latest is None:
        return []
    ended = (latest.end_date or "").strip()
    return [
        IntakeQuestion(
            id="history.current",
            stage="current_role",
            target_path=NEW_EXPERIENCE_PATH,
            question=(
                f"档案里最近一段经历结束在 {ended}。现在这份工作是什么？"
                "公司、职位、起止时间。"
            ),
            rationale=(
                "填进来会作为最近一段经历排在最前面，原来那段自动往后移，不会被覆盖。"
                "之后我们再问这段的具体成果。如果目前确实在空档期，跳过就好。"
            ),
            examples=("某某科技 · 后端技术专家 · 2022-07 至今",),
            required=False,
        )
    ]


def _direction_questions(profile: ProfilePayload) -> list[IntakeQuestion]:
    if profile.preferences.target_roles:
        return []
    return [
        IntakeQuestion(
            id="direction.target",
            stage="direction",
            target_path="preferences.target_roles",
            question="接下来想找什么岗位？写得具体一点更好。",
            rationale="决定简历按哪类读者来写：同一段经历，写给技术负责人和写给业务负责人不一样。",
            examples=("后端技术专家 / 架构师", "B 端产品经理"),
            required=False,
        )
    ]


#: Prefix identifying an evidence answer that came from the interview. Duplicated from
#: `intake_service` rather than imported: that module imports this one, and the constant
#: is a stored-data format, so it changes only as a migration.
_INTAKE_KIND_PREFIX = "intake:"


def _answered_questions(profile: ProfilePayload) -> list[AnsweredQuestion]:
    """Interview answers already on the profile, oldest first.

    Read back from `evidence_answers` for the same reason `answered_ids` is: the
    interview has no server-side session, so the profile is the only record of it.
    """
    out: list[AnsweredQuestion] = []
    for answer in profile.evidence_answers:
        kind = (answer.kind or "").strip()
        if not kind.startswith(_INTAKE_KIND_PREFIX):
            continue
        path = answer.field_path or ""
        out.append(
            AnsweredQuestion(
                question_id=kind[len(_INTAKE_KIND_PREFIX) :],
                target_path=path,
                question=answer.question,
                label=describe_path(profile, path),
                answer=answer.answer,
            )
        )
    return out


def build_intake_plan(
    profile: ProfilePayload,
    *,
    role_family: str | None = None,
    answered_ids: frozenset[str] = frozenset(),
    limit: int = 6,
) -> IntakePlan:
    """The next few questions for this profile, plus whether it can generate yet.

    `answered_ids` are the question ids already answered, so a resumed session does not
    re-ask. Ids are stable functions of the profile shape, which is what makes resumption
    work without storing conversation state.
    """
    playbook = get_playbook(role_family)
    mode = classify_mode(profile)

    planned: list[IntakeQuestion] = list(_identity_questions(profile))

    role_count = max(len(profile.experiences), 1)
    for idx in range(min(role_count, _DETAILED_ROLES)):
        exp = profile.experiences[idx] if idx < len(profile.experiences) else None
        planned.extend(_role_questions(idx=idx, exp=exp, playbook=playbook))

    if mode == "stale":
        planned.extend(_stale_questions(profile))

    # A profile with no second role gets one invitation to add one, not an interview for
    # a job that may not exist. Not in `stale` mode: there the missing role is the
    # current one, and asking about earlier jobs instead is the bug `_stale_questions`
    # exists to fix.
    if len(profile.experiences) == 1 and mode != "stale":
        planned.append(
            IntakeQuestion(
                id="history.more",
                stage="history",
                target_path="experiences[1]",
                question="在这之前还有别的工作经历吗？有的话说公司、职位、起止时间。",
                rationale="跳过也可以。一段经历也能生成简历，只是会偏短。",
                required=False,
            )
        )

    planned.extend(_direction_questions(profile))

    pending = [
        replace(q, label=describe_path(profile, q.target_path))
        for q in planned
        if q.id not in answered_ids
    ]

    by_stage: dict[str, int] = {}
    for q in pending:
        by_stage[q.stage] = by_stage.get(q.stage, 0) + 1
    stages = [
        IntakeStage(
            id=sid,
            label=label,
            remaining=by_stage.get(sid, 0),
            done=by_stage.get(sid, 0) == 0,
        )
        for sid, label in _STAGE_LABELS
    ]

    blocking: list[str] = []
    if not (profile.contact.name or "").strip():
        blocking.append("还没有姓名")
    if not profile.experiences:
        blocking.append("还没有任何工作经历")
    else:
        evidence = count_written_evidence(profile)
        if evidence < _MIN_VIABLE_HIGHLIGHTS:
            blocking.append(
                f"经历要点太少（当前 {evidence} 条，至少需要 {_MIN_VIABLE_HIGHLIGHTS} 条）"
            )

    return IntakePlan(
        mode=mode,
        role_family=playbook.id,
        role_label=playbook.label,
        questions=pending[:limit],
        answered=_answered_questions(profile),
        stages=stages,
        answered_count=len(answered_ids),
        can_generate=not blocking,
        blocking=blocking,
    )
