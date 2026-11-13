"""baseline 迁移必须和 schema.py 一致：不连库，只比对文本。

之前出过两次事故：baseline 悄悄漏了一张表（memory.py 把表注册到同一个 metadata，生成时没导入它），
以及加了列却忘了写进 baseline。两种都只有部署到新库才暴露。这里把它变成每次测试都跑的检查。
"""

import importlib.util
import re
from pathlib import Path

import pytest

import companion.agent.memory.sql  # noqa: F401 —— 注册 ca_memory_item
from companion.db.schema import metadata

BASELINE = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0001_baseline.py"


def _module():
    spec = importlib.util.spec_from_file_location("baseline", BASELINE)
    mod = importlib.util.module_from_spec(spec)
    import sys
    sys.modules.setdefault("alembic", type(sys)("alembic"))      # 只读 SQL 文本，不需要真的 alembic.op
    sys.modules["alembic"].op = None
    spec.loader.exec_module(mod)
    return mod


def _tables(sql: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for name, body in re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", sql, flags=re.S):
        cols = set()
        for line in body.splitlines():
            word = line.strip().split(" ", 1)[0].strip("`")   # MySQL 给保留字（如 role）加反引号
            if word and word.isidentifier() and word.upper() not in {"PRIMARY", "UNIQUE", "CONSTRAINT", "KEY", "INDEX"}:
                cols.add(word)
        out[name] = cols
    return out


@pytest.mark.parametrize("dialect", ["PG", "MYSQL"])
def test_every_table_and_column_is_in_the_baseline(dialect):
    created = _tables(getattr(_module(), dialect))
    expected = {t.name: {c.name for c in t.columns} for t in metadata.tables.values()}
    assert set(created) == set(expected), (
        f"missing: {sorted(set(expected) - set(created))}, extra: {sorted(set(created) - set(expected))}")
    for name, cols in expected.items():
        assert created[name] == cols, f"{name}: baseline differs from schema by {sorted(created[name] ^ cols)}"


@pytest.mark.parametrize("dialect", ["PG", "MYSQL"])
def test_every_index_is_in_the_baseline(dialect):
    sql = getattr(_module(), dialect)
    for table in metadata.tables.values():
        for index in table.indexes:
            assert f"INDEX {index.name} ON {table.name}" in sql, f"{index.name} missing"
