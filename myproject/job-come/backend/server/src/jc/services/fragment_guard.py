"""Merge back a source paragraph the structurer split into several `highlights` entries.

`profile_structurer.md` says plainly not to do this -- "Do not split a source unit on
semicolons, sentences, metrics or visual line wraps" -- and nothing downstream checks it.
Every evaluator measures the *extracted* `highlights` against the rest of the document, so
once a paragraph is split, every later stage treats the fragments as the ground truth: the
writer keeps one bullet per fragment (`_preserve_source_units` enforces that faithfully),
`evaluate_blueprint` scores the fragment count, and the result reads as a flat list of short
lines where the resume once had a structured account of one piece of work. The instruction
not to split was correct; it was just the only thing stopping it, and prompts are not
enforcement (`writing_invariants.py` makes the same point about the writing stage).

This is the ingest-side equivalent: a deterministic check, run once after the structurer
returns, with the raw source text as the proof. It does not guess whether a paragraph "looks"
fragmented -- a resume legitimately lists several short, independent achievements under one
role, and merging those would be its own kind of data loss. It only acts when the source
itself proves the split wrong: the source's own bullet markers (•, -, 1., 一、, ...) are the
one place "how many real units are there" is actually recorded, and it is recorded by whoever
wrote the resume, not by this model call.

Conservative by construction, in the direction that matters -- it would rather miss a real
split than invent a merge:

- No markers found in a block's source span -> no-op. A prose paragraph with no bullets could
  legitimately become either one `highlights` entry or several; without markers there is
  nothing to compare the extraction against.
- Markers found but their count is >= the extracted `highlights` count -> no-op. The
  extraction is already at least as coarse as the source, which is the failure mode this
  guard does not need to fix.
- Anchor text (`company`/`title`/project `name`) not found verbatim in the source -> no-op
  for that block. A wrong span is worse than no span.

When it does act, it is lossless: every character of every original `highlights` string is
kept, only regrouped and joined with `；`. No sentence is reworded, no content is dropped.
"""

from __future__ import annotations

import re

from jc.schemas.profile_payload import ProfilePayload

#: A line that opens with a bullet marker, numbered item, or a Chinese ordinal -- the
#: punctuation resume authors actually use to mark "this is one item". `[-*]` requires
#: trailing whitespace so a date range like `2020-2023` or an em-dash mid-sentence never
#: counts; everything else is anchored to the start of the line.
_BULLET_LINE_RE = re.compile(
    r"^[ \t]*(?:"
    r"[•◦▪▶➤✦‣⁃·]"
    r"|[-*](?=[ \t])"
    r"|\d{1,2}[.)、](?=[ \t])"
    r"|\(\d{1,2}\)"
    r"|[①②③④⑤⑥⑦⑧⑨⑩]"
    r"|[一二三四五六七八九十]+[、.]"
    r")",
    re.MULTILINE,
)

#: Below this, an anchor (a company/project name) is too short to locate reliably -- a
#: one- or two-character match risks landing on an unrelated part of the document, and a
#: wrong span is worse than skipping the block entirely.
_MIN_ANCHOR_CHARS = 2

#: Joins merged fragments back into one entry. Semicolon rather than a space: the pieces
#: were independent sentences before the over-split, and a space would read as one run-on
#: sentence where the source had several.
_MERGE_JOINER = "；"


def _anchor_pattern(anchor: str) -> re.Pattern[str] | None:
    """A regex that finds `anchor` in raw text tolerating whitespace/newline differences.

    PDF and OCR extraction reflow text, so a company name that is one token in the
    structured payload can be wrapped across a line break in the source. Collapsing
    internal whitespace in the needle into `\\s+` survives that without needing to
    normalize the (much larger) haystack.
    """
    stripped = anchor.strip()
    if len(stripped) < _MIN_ANCHOR_CHARS:
        return None
    parts = [re.escape(tok) for tok in stripped.split()]
    if not parts:
        return None
    try:
        return re.compile(r"\s*".join(parts) if len(parts) == 1 else r"\s+".join(parts))
    except re.error:
        return None


def _block_span(raw_text: str, anchor: str, next_anchor: str | None) -> str | None:
    """The raw-text slice between one block's anchor and the next block's, or EOF."""
    pattern = _anchor_pattern(anchor)
    if pattern is None:
        return None
    match = pattern.search(raw_text)
    if match is None:
        return None
    start = match.end()
    end = len(raw_text)
    if next_anchor:
        next_pattern = _anchor_pattern(next_anchor)
        if next_pattern is not None:
            next_match = next_pattern.search(raw_text, start)
            if next_match is not None:
                end = next_match.start()
    return raw_text[start:end]


def _marker_count(span: str) -> int:
    return len(_BULLET_LINE_RE.findall(span))


def _merge_into_groups(items: list[str], group_count: int) -> list[str]:
    """Partition `items` into `group_count` contiguous groups, weighted by length.

    Only the *count* of real units is known (from the marker count), not where their
    boundaries fall relative to the model's fragments -- recovering that would mean fuzzy
    text matching against noisy OCR/markdown, which trades one guess for another. Sizing
    each group by cumulative character length rather than splitting evenly keeps a single
    long fragment from being paired against its will with a short neighbour from a
    different sentence; it is still a heuristic, not a proof, which is exactly why the
    join is lossless -- a wrong boundary loses no text, only groups it differently than
    the source would have.
    """
    if group_count <= 1 or len(items) <= group_count:
        return [_MERGE_JOINER.join(items)] if group_count <= 1 else list(items)
    total = sum(len(i) for i in items) or 1
    target = total / group_count
    groups: list[list[str]] = [[] for _ in range(group_count)]
    gi, acc = 0, 0
    for idx, item in enumerate(items):
        remaining_items = len(items) - idx
        remaining_groups = group_count - gi
        groups[gi].append(item)
        acc += len(item)
        more_to_place = remaining_items - 1
        # Never let a group starve the groups still waiting for at least one item.
        must_advance = more_to_place <= remaining_groups - 1
        if gi < group_count - 1 and (must_advance or acc >= target):
            gi += 1
            acc = 0
    return [_MERGE_JOINER.join(g) for g in groups if g]


def _merge_block(highlights: list[str], span: str | None) -> list[str]:
    if span is None or len(highlights) < 2:
        return highlights
    markers = _marker_count(span)
    if markers == 0 or markers >= len(highlights):
        return highlights
    return _merge_into_groups(highlights, markers)


def merge_oversplit_highlights(payload: ProfilePayload, raw_text: str) -> ProfilePayload:
    """Merge `highlights` fragments the structurer invented beyond what the source marks.

    No-op when `raw_text` is empty -- the vision/OCR ingest routes have no intermediate
    text to check against, so this only runs on the text-extraction route. Mutates and
    returns the same `payload`; every call site already treats structuring as producing
    a fresh object, so there is no second owner to surprise.
    """
    if not raw_text.strip():
        return payload
    for index, exp in enumerate(payload.experiences):
        next_anchor = (
            payload.experiences[index + 1].company
            if index + 1 < len(payload.experiences)
            else None
        )
        span = _block_span(raw_text, exp.company, next_anchor)
        exp.highlights = _merge_block(exp.highlights, span)
    for index, proj in enumerate(payload.projects):
        next_anchor = payload.projects[index + 1].name if index + 1 < len(payload.projects) else None
        span = _block_span(raw_text, proj.name, next_anchor)
        proj.highlights = _merge_block(proj.highlights, span)
    return payload
