"""Did the writer add anything the source does not support?

The gap this closes
-------------------
JC already measures the **loss** side of generation: `resume_coverage` answers "did the
document keep my career". Nothing measured the **addition** side deterministically. That
side was guarded by two things, and neither is a measurement:

1. The writer prompt forbids inventing facts. Prompts are not enforcement — a retry, a
   longer profile or a model swap re-introduces the behaviour.
2. The reviewer is asked to catch it before export. The reviewer is itself a model call,
   so "the reviewer blocks fabrication" is an assumption about model behaviour that
   nothing in the test suite could check.

This module turns the addition side into arithmetic. Given the confirmed profile and a
generated draft, it attributes each draft bullet back to the source line it was written
from and reports what appeared along the way that the source never said.

Scope: a detector, not a gate
-----------------------------
Every finding here is **evidence for a human or a script**, never an automatic export
block. Two reasons:

- A `number` finding can be legitimate. `覆盖 6 条业务线` may be stated in the profile's
  summary rather than in the bullet, so the whole source corpus is searched before
  anything is reported — and even then, a candidate writing `3 年` from dates the profile
  carries structurally is not lying.
- The reviewer is the product's gate and it reads intent. A deterministic check that
  blocked export would fire on the writer doing its job (merging two bullets changes
  which source line a sentence attributes to) and lock users out of their own document —
  the exact failure already fixed once in `_has_blocking_issue`.

What it is for is the question nobody could answer before: **does the pipeline actually
hold its honesty invariant, run after run, across framing angles and models.**
`scripts/evaluate_writing.py` runs this against live model output; the reviewer keeps its
own independent judgement.

Attribution, and why it needs its own threshold
----------------------------------------------
To say "this bullet added a number" we must know which source line it came from.
`text_overlap.best_origin` supplies the candidate, scoring how much of the *source line*
survives in the bullet rather than the reverse — a bullet that correctly gained an outcome
is longer than its source, and scoring it the other way makes good writing look
unattributable. `_ATTRIBUTION_THRESHOLD` then decides whether the match is strong enough
to reason about. It is deliberately lower than the coverage threshold: coverage asks "is
this content still present anywhere" and can afford to be strict, while attribution would
rather pull in a loose match than treat a rewritten bullet as having no source at all. A
bullet that still matches nothing is reported on its own, because no recognisable source
line is the strongest fabrication signal available without a model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from jc.schemas.profile_payload import ProfilePayload
from jc.services.text_overlap import best_origin, normalize

#: Overlap at or above which a draft bullet is considered a rewrite of a source line, so
#: the difference between them can be attributed. See the module docstring for why this
#: differs from `resume_coverage._MATCH_THRESHOLD`.
_ATTRIBUTION_THRESHOLD = 0.30

#: Numbers, percentages, magnitudes and the metric acronyms resumes actually use.
#: Shares vocabulary with `resume_diagnostics`/`elevation_techniques` so one pipeline does
#: not consider a token a metric while another ignores it, and additionally captures the
#: Chinese counter that follows a bare count (`6 个业务线`, `8 人团队`). Without the
#: counter, `6 个` normalises to `6`, gets dropped as ordinal noise, and an invented scope
#: claim — the most common exaggeration in a resume — goes unreported.
#:
#: The magnitude suffix also accepts the internet-slang compound `kw`/`KW` (千万 written
#: as "thousand wan", e.g. `4kw` = 4000万) ahead of the single-letter alternatives, since
#: regex alternation is first-match and `k` alone would otherwise consume the `k` and
#: strand the `w` as an unmatched character outside any token.
#:
#: The acronym branch uses lookaround instead of `\b`: Python's Unicode-aware `\b`
#: treats CJK ideographs as word characters, so `了GMV` (a CJK character directly
#: adjacent to the acronym, which is how resumes actually write it) has no boundary
#: between `了` and `G` and the acronym silently fails to match.
_METRIC_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|％|倍|亿|万|千|[kKwW]{1,2}|[mMxX]"
    r"|个|条|名|人|家|次|套|款|端|轮|地区|业务线|业务方|团队)?"
    r"|(?<![A-Za-z0-9])(?:qps|tps|p99|p95|sla|dau|mau|arr|roi|nps|gmv)(?![A-Za-z0-9])",
    re.IGNORECASE,
)

#: Magnitude suffixes normalised to their multiplier, so `100万` and `100w` collapse to
#: the same numeric value instead of being compared as different strings. Order matters:
#: `kw`/`wk` (千万, 4kw = 4000万) must be checked before the single-letter suffixes they
#: contain, or the compound would be cut short and the trailing letter stranded.
_MAGNITUDE = (
    ("kw", 10_000_000), ("wk", 10_000_000),
    ("亿", 100_000_000),
    ("万", 10_000), ("w", 10_000),
    ("千", 1_000), ("k", 1_000),
    ("%", None), ("％", None), ("倍", None), ("m", None), ("x", None),
)


def _normalise_metric(token: str) -> str:
    """Collapse a unit suffix to its numeric multiplier so `100w` == `100万` == `1000k`.

    `%`/`倍`/`m`/`x` and the bare Chinese counters (个/条/人/...) carry no numeric
    conversion between each other, so they are left as their original suffix: the digits
    in front already disambiguate `6 个` from `6 条`, and collapsing them together would
    let `6 个业务线` match a profile that only ever said `6 条数据`.
    """
    for suffix, multiplier in _MAGNITUDE:
        if token.endswith(suffix) and token[: -len(suffix)].replace(".", "").isdigit():
            digits = token[: -len(suffix)]
            if multiplier is None:
                return f"{digits}{suffix}"
            try:
                value = float(digits) * multiplier
            except ValueError:
                return token
            return f"={value:g}"
    return token

#: Latin/alphanumeric tokens: technology names, products, companies, frameworks. A token
#: in the draft that appears nowhere in the profile is either a real fabrication or a
#: translation of a Chinese term, which is why this is advisory rather than blocking.
_TERM_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.#/_-]{2,}")

#: Verbs that assert the candidate owned the work.
_OWNERSHIP_VERBS = (
    "主导", "牵头", "从 0 到 1", "从0到1", "独立负责", "owned", "led", "architected",
    "spearheaded", "drove",
)

#: Verbs that state the candidate took part in work someone else owned. A draft moving
#: from one of these to an ownership verb is the single most damaging silent change the
#: writer can make: it survives the screen and collapses in the interview.
_PARTICIPATION_VERBS = (
    "参与", "协助", "配合", "参加", "跟进", "involved in", "helped with", "assisted",
    "supported", "contributed to",
)

#: Tokens that are numbers but never claims: years and bare small ordinals that come from
#: the profile's structured dates or from list positions rather than from a result.
_CALENDAR_RE = re.compile(r"^(?:19|20)\d{2}$")


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing the draft says that the source does not.

    `severity` is advice to the caller, not a gate:

    - `fabrication` — the draft asserts something with no support anywhere in the profile.
      A script asserting the honesty invariant should fail on these.
    - `attention` — legitimate in some shapes, worth a human read. Reported so a run can
      be explained, never counted as a failure.
    """

    kind: str
    severity: str
    field_path: str
    draft_text: str
    source_text: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "field_path": self.field_path,
            "draft_text": self.draft_text,
            "source_text": self.source_text,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class WritingAudit:
    """Addition-side audit of one generated draft."""

    draft_bullets: int
    attributed_bullets: int
    findings: list[Finding] = field(default_factory=list)

    @property
    def fabrications(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "fabrication"]

    @property
    def holds(self) -> bool:
        """True when nothing unsupported was asserted."""
        return not self.fabrications

    def to_dict(self) -> dict[str, Any]:
        return {
            "draft_bullets": self.draft_bullets,
            "attributed_bullets": self.attributed_bullets,
            "holds": self.holds,
            "fabrication_count": len(self.fabrications),
            "findings": [f.to_dict() for f in self.findings],
        }


def _metrics(text: str) -> set[str]:
    """Metric tokens in `text`, whitespace-normalised, unit-normalised and calendar
    years removed.

    Unit normalisation runs after the calendar-year check: `_normalise_metric` only
    touches tokens with a known magnitude suffix, and a bare 4-digit year has none, so
    the order does not change which years are excluded — it just keeps the exclusion
    reading on the token actually typed in the text, which is clearer in a traceback.
    """
    out: set[str] = set()
    for raw in _METRIC_RE.findall(text or ""):
        token = "".join(str(raw).split()).lower()
        if not token or _CALENDAR_RE.match(token):
            continue
        out.add(_normalise_metric(token))
    return out


def _terms(text: str) -> set[str]:
    return {t.lower() for t in _TERM_RE.findall(text or "")}


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    low = (text or "").lower()
    return any(n.lower() in low for n in needles)


def _source_corpus(profile: ProfilePayload) -> str:
    """Everything the user confirmed, as one searchable blob.

    A number the writer legitimately used may live in the summary, in a different
    bullet, in a skill's evidence, or in an answer the user typed to an evidence
    question. Checking a bullet only against its own source line would report all of
    those as fabrications, which would make the check useless.
    """
    parts: list[str] = [profile.summary or ""]
    for exp in profile.experiences:
        parts += [exp.company, exp.title, exp.start_date or "", exp.end_date or ""]
        parts += list(exp.highlights or [])
        parts += list(exp.skills or [])
    for proj in profile.projects:
        parts += [proj.name, proj.role or "", proj.description or ""]
        parts += list(proj.highlights or [])
    for edu in profile.education:
        parts += [edu.school, edu.degree or "", edu.major or ""]
    for skill in profile.skills:
        parts += [skill.name, *(skill.evidence or [])]
    # User-typed answers are source material of the same standing as a bullet.
    parts += [a.answer for a in profile.evidence_answers]
    parts += list(profile.preferences.target_roles or [])
    return "\n".join(str(p) for p in parts if p)


def _source_lines(profile: ProfilePayload) -> list[str]:
    """Candidate origin lines for attribution, in profile order."""
    lines: list[str] = []
    for exp in profile.experiences:
        lines += [str(h).strip() for h in (exp.highlights or []) if str(h).strip()]
    for proj in profile.projects:
        if proj.description and str(proj.description).strip():
            lines.append(str(proj.description).strip())
        lines += [str(h).strip() for h in (proj.highlights or []) if str(h).strip()]
    lines += [str(a.answer).strip() for a in profile.evidence_answers if str(a.answer).strip()]
    return lines


def _ownership_window(corpus_norm: str, origin: str) -> str:
    """Text around `origin` inside the corpus, used to check nearby ownership wording.

    A profile sometimes states ownership next to the line rather than inside it — a
    project's `role` field saying `负责人`, or the preceding highlight establishing that
    the candidate led the workstream. Looking only at the matched line would report that
    as an upgrade. The window is small on purpose: ownership stated three paragraphs away
    is not ownership of *this* work.
    """
    key = normalize(origin)
    if not key:
        return ""
    at = corpus_norm.find(key)
    if at < 0:
        return ""
    return corpus_norm[max(0, at - 40) : at + len(key) + 40]


def _draft_bullets(sections: dict[str, Any]) -> list[tuple[str, str]]:
    """(field_path, text) for every bullet in the draft, in document order."""
    out: list[tuple[str, str]] = []
    for key in ("experience_blocks", "project_blocks"):
        for b_idx, block in enumerate(sections.get(key) or []):
            if not isinstance(block, dict):
                continue
            for idx, bullet in enumerate(block.get("bullets") or []):
                if isinstance(bullet, str) and bullet.strip():
                    out.append((f"{key}[{b_idx}].bullets[{idx}]", bullet.strip()))
    return out


def audit_additions(
    sections: dict[str, Any],
    profile: ProfilePayload | None,
) -> WritingAudit:
    """Report everything the draft asserts that the confirmed profile does not support.

    Bilingual drafts are audited on their 中文 track, matching `resume_coverage`: the
    English track restates the same facts, so auditing both double-counts every finding,
    and the overlap metric is calibrated on Chinese text.
    """
    if sections.get("track") == "bilingual":
        sections = sections.get("zh_sections") or {}

    bullets = _draft_bullets(sections)
    if profile is None:
        return WritingAudit(draft_bullets=len(bullets), attributed_bullets=0)

    corpus = _source_corpus(profile)
    corpus_norm = normalize(corpus)
    corpus_metrics = _metrics(corpus)
    corpus_terms = _terms(corpus)
    lines = _source_lines(profile)

    findings: list[Finding] = []
    attributed = 0

    for field_path, text in bullets:
        match = best_origin(text, lines)
        origin = match.text if match and match.score >= _ATTRIBUTION_THRESHOLD else ""
        if origin:
            attributed += 1
        elif lines:
            # No source line resembles this bullet. Either the writer merged several
            # (legitimate) or wrote something from nothing. Reported as attention, since
            # the per-token checks below still run against the full corpus and will
            # catch an actual invented claim.
            findings.append(
                Finding(
                    kind="unattributed_bullet",
                    severity="attention",
                    field_path=field_path,
                    draft_text=text,
                    source_text="",
                    detail=(
                        "没有找到与这条要点对应的源文（最高重合 "
                        f"{match.score:.2f}）。可能是合并了多条，也可能是凭空生成。"
                    ),
                )
            )

        for token in sorted(_metrics(text) - corpus_metrics):
            # A bare digit with no unit ("第 2 期", "Top 3") is ordinal noise, not a
            # claim. A digit *with* a unit is a scope claim and is always checked.
            if token.isdigit():
                continue
            findings.append(
                Finding(
                    kind="unsupported_number",
                    severity="fabrication",
                    field_path=field_path,
                    draft_text=text,
                    source_text=origin,
                    detail=f"数字 `{token}` 在档案任何位置都找不到依据。",
                )
            )

        for token in sorted(_terms(text) - corpus_terms):
            findings.append(
                Finding(
                    kind="unsupported_term",
                    severity="attention",
                    field_path=field_path,
                    draft_text=text,
                    source_text=origin,
                    detail=(
                        f"术语 `{token}` 不在档案里。可能是中文词的英文写法，"
                        "也可能是新增的技术栈声明。"
                    ),
                )
            )

        if (
            origin
            and _has_any(text, _OWNERSHIP_VERBS)
            and not _has_any(origin, _OWNERSHIP_VERBS)
            and _has_any(origin, _PARTICIPATION_VERBS)
            and not _has_any(_ownership_window(corpus_norm, origin), _OWNERSHIP_VERBS)
        ):
            findings.append(
                Finding(
                    kind="ownership_upgrade",
                    severity="fabrication",
                    field_path=field_path,
                    draft_text=text,
                    source_text=origin,
                    detail="源文写的是参与类动词，这条要点改写成了主导类动词。",
                )
            )

    return WritingAudit(
        draft_bullets=len(bullets),
        attributed_bullets=attributed,
        findings=findings,
    )
