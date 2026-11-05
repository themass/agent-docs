"""Migration/ORM parity without connecting to a developer's database."""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect

from jc.db.base import Base
from jc.models.profile_patch_confirm import ProfilePatchConfirm


def test_confirmation_migration_matches_model_and_downgrades(monkeypatch):
    path = Path(__file__).parents[1] / "alembic/versions/014_profile_patch_confirm.py"
    spec = importlib.util.spec_from_file_location("confirm_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite:///:memory:")
    table = ProfilePatchConfirm.__table__
    with engine.begin() as conn:
        Base.metadata.create_all(
            conn, tables=[t for t in Base.metadata.sorted_tables if t != table]
        )
        monkeypatch.setattr(module, "op", Operations(MigrationContext.configure(conn)))
        module.upgrade()
        actual = inspect(conn)
        assert {c["name"] for c in actual.get_columns(table.name)} == set(table.columns.keys())
        assert {i["name"] for i in actual.get_indexes(table.name)} == {
            i.name for i in table.indexes
        }
        assert len(actual.get_foreign_keys(table.name)) == 3
        module.downgrade()
        assert not inspect(conn).has_table(table.name)
        assert inspect(conn).has_table("jc_profile")
    engine.dispose()
