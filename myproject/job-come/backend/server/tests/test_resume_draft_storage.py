"""Regression tests for generated resume drafts larger than MySQL TEXT."""

from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from jc.db.base import Base
from jc.db.types import JSONLongText
from jc.models.resume import ResumeDraft


def test_resume_draft_json_columns_compile_to_longtext() -> None:
    for name in ("sections", "elevation_map"):
        column_type = ResumeDraft.__table__.c[name].type.compile(dialect=mysql.dialect())
        assert column_type == "LONGTEXT"


def test_resume_draft_round_trips_sections_larger_than_mysql_text() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[ResumeDraft.__table__])
    # This is deliberately larger than MySQL TEXT's 65,535-byte limit. SQLite
    # makes the test deterministic without needing a developer MySQL instance.
    sections = {
        "header": {"name": "张三"},
        "experiences": [{"bullets": ["事实 " + ("很长" * 40_000)]}],
    }
    with Session(engine) as db:
        draft = ResumeDraft(
            id="draft-large",
            profile_id="profile",
            profile_version=1,
            elevation_level="elevated",
            locale="zh-CN",
            template_id="zh-one-page",
            sections=sections,
            elevation_map=[{"section": "experiences", "source": "profile"}],
        )
        db.add(draft)
        db.commit()
        loaded = db.scalar(select(ResumeDraft).where(ResumeDraft.id == draft.id))
        assert loaded is not None
        assert loaded.sections == sections
        assert len(loaded.sections["experiences"][0]["bullets"][0]) > 65_535
    engine.dispose()


def test_json_long_text_uses_text_on_sqlite() -> None:
    engine = create_engine("sqlite:///:memory:")
    assert JSONLongText().compile(dialect=engine.dialect) == "TEXT"
    engine.dispose()
