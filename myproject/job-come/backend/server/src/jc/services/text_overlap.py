"""Character-bigram overlap: the one similarity metric JC measures writing with.

Why a shared module
-------------------
Two different questions about a generated resume both need "is this draft sentence a
rewrite of that source sentence?":

- **Loss** (`resume_coverage`): every source highlight should still be represented
  somewhere in the draft.
- **Addition** (`writing_invariants`): a draft bullet must be judged against *the source
  line it came from*, so a metric or an ownership verb can be traced back.

Before this module each caller would have carried its own copy of the normaliser and the
overlap function. Two copies of a calibrated metric drift: one gets a punctuation class
added, the thresholds tuned against the other stop meaning what they did, and nothing
fails loudly. So the metric lives here once, and the *thresholds* stay with the caller
that calibrated them — they answer different questions and are not interchangeable.

Why bigram containment rather than embeddings
---------------------------------------------
No model call, no latency, identical result on every run, and a surprising verdict can be
explained by reading the two strings. For a rewrite-detection job that is worth more than
semantic nuance: the writer is required to preserve content, not paraphrase freely.

Containment, not Jaccard, on purpose. The writer is *expected* to add words — an outcome,
a scale figure, the target job's vocabulary. Jaccard scores that addition as a loss.
Containment asks only the question we actually have: did the source's content survive.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Punctuation and whitespace carry no content here, and CJK/Latin drafts mix both
#: widths. Stripping them keeps `负责 A/B 实验` and `负责A、B实验` comparable.
_PUNCT_RE = re.compile(
    r"[\s\u3000，。、；：！？（）【】·—‒–()\[\]\-_/\\,.;:!?\"'`]+"
)


def normalize(text: str) -> str:
    """Lowercased, punctuation-free form used for every comparison in this module."""
    return _PUNCT_RE.sub("", str(text or "")).lower()


def bigrams(text: str) -> set[str]:
    """Character bigrams of the normalised text.

    Characters rather than words because Chinese resumes have no spaces and any
    segmenter would become a second thing to calibrate.
    """
    norm = normalize(text)
    if len(norm) < 2:
        return {norm} if norm else set()
    return {norm[i : i + 2] for i in range(len(norm) - 1)}


def containment(source: str, candidate: str) -> float:
    """Share of `source`'s bigrams that appear in `candidate`, in [0, 1].

    An empty source returns 1.0: there was nothing to lose.
    """
    src = bigrams(source)
    if not src:
        return 1.0
    return len(src & bigrams(candidate)) / len(src)


#: Where an excerpt may be cut. Cutting on a character boundary produces fragments like
#: 「满足高质量用」, which read as a rendering bug rather than as a quotation, so the user
#: stops trusting the panel showing them.
_CUT_PUNCT = "，。、；：！？）】,.;:!?)]"


def excerpt(text: str, limit: int = 24) -> str:
    """A quotable prefix of `text`, cut on a phrase boundary rather than mid-word.

    Returns the text unchanged when it already fits. Otherwise it backs up to the last
    punctuation mark inside the limit; failing that it cuts at the limit, because a
    too-long excerpt is worse than a slightly short one. The ellipsis is always appended
    when something was removed, so the reader knows the quotation is partial.
    """
    body = str(text or "").strip()
    if len(body) <= limit:
        return body
    window = body[:limit]
    cut = max(window.rfind(ch) for ch in _CUT_PUNCT)
    # Only honour the boundary if it leaves a readable amount of text. A comma at
    # position 2 would turn the excerpt into noise.
    if cut >= limit // 2:
        return window[: cut + 1].rstrip("".join(_CUT_PUNCT)) + "…"
    return window + "…"


@dataclass(frozen=True, slots=True)
class Match:
    """Best candidate found for one source string."""

    index: int
    text: str
    score: float


def best_match(source: str, candidates: list[str]) -> Match | None:
    """The candidate retaining most of `source`, or None when there are none.

    This is the **loss** direction: "is this source highlight still present in one of
    these draft bullets". The index is returned too, so a caller can report which bullet
    matched rather than only that something did.
    """
    best: Match | None = None
    for idx, candidate in enumerate(candidates):
        score = containment(source, candidate)
        if best is None or score > best.score:
            best = Match(index=idx, text=candidate, score=score)
    return best


def best_origin(text: str, candidates: list[str]) -> Match | None:
    """The candidate whose own content is most fully retained inside `text`.

    This is the **attribution** direction, and it is not the same question as
    `best_match` even though it uses the same metric. Attribution asks "which source
    line was this bullet written from", so the source line is what must survive — scoring
    it the other way round penalises exactly the behaviour the writer is supposed to
    exhibit (adding an outcome makes the bullet longer, so the share of *the bullet's*
    bigrams found in the short source line collapses, and every well-written bullet looks
    unattributable).
    """
    best: Match | None = None
    for idx, candidate in enumerate(candidates):
        score = containment(candidate, text)
        if best is None or score > best.score:
            best = Match(index=idx, text=candidate, score=score)
    return best
