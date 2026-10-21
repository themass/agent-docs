"""Split one spoken-style answer into the separate bullets it actually contains.

The problem this solves
-----------------------
The interview asks 「最值得写的一件事是什么」 and the user answers with five things,
in one breath, because that is how people talk about their own work. Before this
module that whole paragraph landed in a single `highlights[slot]`, so the resume
got one 300-character bullet holding five achievements — the worst possible form:
too long to be read, and the four strongest items buried inside the first.

`profile-interview/references/method.md` already tells the agent 「用户一段话说了
很多，拆成独立的要点」. That instruction was unenforceable from the form-based
interview, which had no way to turn one textarea into several bullets. This is that
missing half.

Why the split is deterministic and not a model call
----------------------------------------------------
Intake is the one path in JC with **no model between the user and their profile**
(`schemas/intake.py` states the trust class). Sending the paragraph to a model to be
segmented would break that for no gain: the model would also normalise wording,
merge two items it judged similar, and occasionally drop the item it found least
interesting — and the user would have no way to tell, because they are looking at a
tidy list. Splitting on the punctuation the user typed cannot invent or lose content,
and the user confirms the result before anything is written.

The preservation invariant
--------------------------
Every content character of the input appears in the output, in order. That is tested
directly (`test_intake_dictation.py`), and it is the property that makes the feature
safe to offer by default: a split can be *badly placed* and the user fixes it in the
confirm step, but it can never silently eat the sentence that was the whole point.
"""

from __future__ import annotations

import re

#: List markers people type when enumerating. Stripped only at a segment's start.
#:
#: `(?!\d)` guards the numeric forms: without it 「1.5 倍的吞吐提升」 reads as marker
#: `1.` plus text `5 倍的吞吐提升`, which deletes a figure — exactly the kind of loss
#: this module promises not to cause.
_MARKER_RE = re.compile(
    r"^\s*(?:[-•*·–—]+|\d{1,2}[.)、](?!\d)|[（(]\d{1,2}[）)]|[①②③④⑤⑥⑦⑧⑨⑩])\s*"
)

#: Sentence ends, kept with the sentence they close. Commas are deliberately absent:
#: 「负责 A，顺便做了 B」 is one thought in Chinese far more often than two, and an
#: over-eager split produces bullet fragments the user has to re-join by hand.
_SENTENCE_RE = re.compile(r"(?<=[。！？!?；;])")

#: Below this a fragment is not a bullet — it is the tail of the previous one
#: (「后来上线了。」「效果不错。」), so it is merged backwards rather than kept.
#:
#: Applied only to fragments the splitter produced. A line the user marked as a list
#: item is never merged however short it is: they already said where the boundary is,
#: and overriding that is how 「- 带了 4 个人」 ends up glued onto the line above it.
_MIN_SEGMENT_CHARS = 8

#: A line shorter than this is left whole even if it contains a full stop. Two short
#: sentences on one line are usually one point stated twice, and splitting them gives
#: the user two half-bullets to merge.
_SPLIT_LINE_CHARS = 40

#: More segments than a reviewer will read under one role. Past this the remainder is
#: joined into the last segment: a cap that *drops* content would violate the
#: preservation invariant, and silently losing the user's last three sentences is
#: worse than one long final bullet they can split again.
_MAX_SEGMENTS = 8


def _strip_marker(text: str) -> tuple[str, bool]:
    """The text without its list marker, and whether it had one."""
    stripped = _MARKER_RE.sub("", text, count=1).strip()
    return stripped, stripped != text.strip()


def split_dictation(text: str) -> tuple[str, ...]:
    """The separate points in one free-form answer, in the order they were said.

    Returns a single-element tuple when the answer is one point, so a caller can treat
    "nothing to split" as the ordinary case rather than a special one. Returns an empty
    tuple only for input with no content at all.
    """
    body = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not body:
        return ()

    # (text, the user marked this boundary themselves)
    raw: list[tuple[str, bool]] = []
    for source_line in body.split("\n"):
        line, marked = _strip_marker(source_line)
        if not line:
            continue
        if len(line) <= _SPLIT_LINE_CHARS:
            raw.append((line, marked))
            continue
        for index, piece in enumerate(_SENTENCE_RE.split(line)):
            text_piece, piece_marked = _strip_marker(piece)
            if text_piece:
                # Only the first fragment of a marked line inherits the marker; the
                # rest are the splitter's own guesses and stay mergeable.
                raw.append((text_piece, piece_marked or (marked and index == 0)))

    merged: list[str] = []
    for piece, marked in raw:
        if merged and not marked and len(piece) < _MIN_SEGMENT_CHARS:
            merged[-1] = f"{merged[-1]}{piece}"
            continue
        merged.append(piece)

    if len(merged) > _MAX_SEGMENTS:
        tail = merged[_MAX_SEGMENTS - 1 :]
        merged = merged[: _MAX_SEGMENTS - 1] + ["".join(tail)]

    return tuple(merged)
