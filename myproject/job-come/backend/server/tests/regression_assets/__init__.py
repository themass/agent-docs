"""Regression assets — 5 resumes + 10 JDs + mock golden on disk."""

from pathlib import Path

ASSETS_ROOT = Path(__file__).resolve().parent
RESUMES_DIR = ASSETS_ROOT / "resumes"
JDS_DIR = ASSETS_ROOT / "jds"


def list_resume_fixtures() -> list[Path]:
    return sorted(RESUMES_DIR.glob("*.txt"))


def list_jd_fixtures() -> list[Path]:
    return sorted(JDS_DIR.glob("jd_*.txt"))


def assert_fixture_counts() -> None:
    assert len(list_resume_fixtures()) >= 5, "need >= 5 resume fixtures"
    assert len(list_jd_fixtures()) >= 10, "need >= 10 JD fixtures"
