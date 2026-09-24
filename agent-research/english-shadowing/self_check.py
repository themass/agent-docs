#!/usr/bin/env python3
"""Runnable check for alignment + pass rules + bilingual coach."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline import evaluate  # noqa: E402


def main() -> None:
    cases: list[tuple[str, str, bool, str]] = [
        ("Hi, I'd like a latte, please.", "Hi I'd like latte please", True, "pass"),
        ("Do you have oat milk?", "Do you have milk", False, "retry"),
        ("Could I have the receipt?", "Could I have the receipt", True, "excellent"),
        ("I need a pen.", "I need pen", True, "pass"),  # missing function word "a"
    ]

    for reference, transcript, should_pass, expected_grade in cases:
        result = evaluate(reference, transcript, use_llm=False)
        assert result.pass_ == should_pass, (
            f"pass mismatch for {reference!r}: got {result.pass_}, want {should_pass}"
        )
        if should_pass:
            assert result.grade in {"pass", "excellent"}, result.grade
        else:
            assert result.grade == "retry"
        if should_pass and expected_grade == "excellent":
            assert result.grade == "excellent"
        assert "zh" in result.coach and "en" in result.coach
        print("---")
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

    lesson = json.loads((_ROOT / "content" / "demo_lesson.json").read_text(encoding="utf-8"))
    assert len(lesson["sentences"]) >= 5
    print(f"\nOK: {len(cases)} cases + bilingual coach + demo lesson ({lesson['lesson_id']})")


if __name__ == "__main__":
    main()
