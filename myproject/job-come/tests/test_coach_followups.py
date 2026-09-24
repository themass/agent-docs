"""Coach follow-up library tests."""

from __future__ import annotations

from jobcome.coach.followups import followups_for_role, load_industry_followups


def test_industry_followups_loaded() -> None:
    bank = load_industry_followups()
    assert "backend" in bank
    assert len(bank["general"]) >= 2


def test_followups_for_backend_role() -> None:
    qs = followups_for_role("高级后端工程师")
    assert qs
    assert any("并发" in q or "P99" in q or "一致性" in q for q in qs)
