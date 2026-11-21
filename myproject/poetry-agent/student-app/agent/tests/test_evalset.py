"""Pins the eval set to the implementation. The runner itself is exercised here on the script path only."""
from __future__ import annotations

import dataclasses
import json
from collections import Counter

from student_agent.config import Settings
from student_agent.evalrun import DEFAULT_CASES, load_cases, run


def test_the_case_file_has_the_agreed_shape():
    cases = load_cases(DEFAULT_CASES)
    assert Counter(c["category"] for c in cases) == {"answer": 22, "unknown": 6, "boundary": 5, "trap": 10}
    assert len({c["id"] for c in cases}) == len(cases)
    for c in cases:
        assert c["step"] in {"read", "arrive", "meet", "return", "recite"} and c["expect"]


def test_the_script_path_passes_the_whole_set_with_zero_fabrications():
    cases = load_cases(DEFAULT_CASES)
    result = run(cases, dataclasses.replace(Settings(), mode_override="script", source="fixture"))
    failed = {c: row["failed"] for c, row in result["categories"].items() if row["failed"]}
    assert not failed, json.dumps(failed, ensure_ascii=False)
    assert result["fabrications"] == []
