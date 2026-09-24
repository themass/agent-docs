"""Text alignment between reference sentence and ASR transcript."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class WordIssue:
    """A single alignment issue for coach and UI."""

    type: str  # missing | extra | wrong | ok
    word: str
    expected: str | None = None
    spoken: str | None = None
    hint: str = ""


@dataclass(frozen=True)
class AlignmentScore:
    """Scores in [0, 1]."""

    overall: float
    completeness: float
    accuracy: float
    issues: tuple[WordIssue, ...] = field(default_factory=tuple)

    def passes(self, threshold: float = 0.75) -> bool:
        """Return whether overall score meets pass threshold."""
        return self.overall >= threshold


def normalize(text: str) -> str:
    """Lowercase, strip punctuation for word-level compare."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s']", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str) -> list[str]:
    """Split normalized text into words."""
    normalized = normalize(text)
    if not normalized:
        return []
    return normalized.split()


def align(reference: str, transcript: str) -> AlignmentScore:
    """Align reference to transcript and compute scores.

    Args:
        reference: Ground-truth sentence the user should say.
        transcript: ASR output (or typed simulation).

    Returns:
        AlignmentScore with issues suitable for coach + UI highlights.
    """
    ref_words = tokenize(reference)
    spoken_words = tokenize(transcript)

    if not ref_words:
        return AlignmentScore(overall=0.0, completeness=0.0, accuracy=0.0, issues=())

    if not spoken_words:
        issues = tuple(
            WordIssue(type="missing", word=w, expected=w, hint="这句还没听到")
            for w in ref_words
        )
        return AlignmentScore(overall=0.0, completeness=0.0, accuracy=0.0, issues=issues)

    matcher = difflib.SequenceMatcher(None, ref_words, spoken_words, autojunk=False)
    issues: list[WordIssue] = []
    matched_ref = 0
    matched_pairs = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            matched_ref += i2 - i1
            matched_pairs += i2 - i1
            for w in ref_words[i1:i2]:
                issues.append(WordIssue(type="ok", word=w, expected=w, spoken=w))
        elif tag == "replace":
            ref_chunk = ref_words[i1:i2]
            spk_chunk = spoken_words[j1:j2]
            for idx, w in enumerate(ref_chunk):
                spoken = spk_chunk[idx] if idx < len(spk_chunk) else None
                if spoken is None:
                    issues.append(
                        WordIssue(type="missing", word=w, expected=w, hint=f"漏读了「{w}」")
                    )
                elif spoken != w:
                    issues.append(
                        WordIssue(
                            type="wrong",
                            word=w,
                            expected=w,
                            spoken=spoken,
                            hint=f"「{w}」听成了「{spoken}」",
                        )
                    )
                else:
                    matched_ref += 1
                    matched_pairs += 1
                    issues.append(WordIssue(type="ok", word=w, expected=w, spoken=w))
            for extra in spk_chunk[len(ref_chunk) :]:
                issues.append(
                    WordIssue(type="extra", word=extra, spoken=extra, hint=f"多说了「{extra}」")
                )
        elif tag == "delete":
            for w in ref_words[i1:i2]:
                issues.append(
                    WordIssue(type="missing", word=w, expected=w, hint=f"漏读了「{w}」")
                )
        elif tag == "insert":
            for w in spoken_words[j1:j2]:
                issues.append(
                    WordIssue(type="extra", word=w, spoken=w, hint=f"多说了「{w}」")
                )

    completeness = matched_ref / len(ref_words)
    # accuracy: of spoken words, how many align to reference opcodes as equal/replace-match
    accuracy = matched_pairs / max(len(spoken_words), 1)
    overall = 0.6 * completeness + 0.4 * accuracy

    return AlignmentScore(
        overall=round(overall, 3),
        completeness=round(completeness, 3),
        accuracy=round(accuracy, 3),
        issues=tuple(issues),
    )
