"""从 adapters/store/mysql/schema.py 生成 0001 迁移的 DDL（MySQL 5.6 兼容，见 D §3）。

用法：PYTHONPATH=src python scripts/gen_ddl.py > migrations/versions/0001_initial.py
修改模型后重新生成；不要手改生成的迁移。
"""

from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable, DropTable

from companion.adapters.store.mysql.schema import metadata


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=mysql.dialect())).strip()


def main() -> None:
    tables = list(metadata.sorted_tables)
    create = [_sql(CreateTable(t)) for t in tables]
    drop = [f"DROP TABLE IF EXISTS {t.name}" for t in reversed(tables)]
    lines = [
        '"""initial schema（D §3、O §2.1、O §10）。由 scripts/gen_ddl.py 从 schema.py 生成，勿手改。',
        '',
        'MySQL 5.6 兼容：无 JSON 列，表名统一带 ca_ 前缀（共用 vpn 库）。',
        '"""',
        '',
        'from alembic import op',
        '',
        'revision = "0001_initial"',
        'down_revision = None',
        'branch_labels = None',
        'depends_on = None',
        '',
        'UPGRADE_SQL = """',
    ]
    lines += [s + ";" for s in create]
    lines += ['"""', '', 'DOWNGRADE_SQL = """']
    lines += [s + ";" for s in drop]
    lines += [
        '"""',
        '',
        '',
        'def upgrade() -> None:',
        '    for stmt in [s.strip() for s in UPGRADE_SQL.split(";") if s.strip()]:',
        '        op.execute(stmt)',
        '',
        '',
        'def downgrade() -> None:',
        '    for stmt in [s.strip() for s in DOWNGRADE_SQL.split(";") if s.strip()]:',
        '        op.execute(stmt)',
        '',
    ]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
