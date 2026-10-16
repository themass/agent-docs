"""Pick personal-bank questions for a mock round."""

from __future__ import annotations

from collections.abc import Sequence


def select_bank_draws(
    questions: Sequence[tuple[str, int]],
    *,
    n: int = 1,
) -> list[str]:
    """Return up to n question ids. Prefer stems the user already practiced."""
    if n <= 0 or not questions:
        return []
    practiced = [qid for qid, attempts in questions if attempts > 0]
    pool = practiced if practiced else [qid for qid, _ in questions]
    return pool[:n]
