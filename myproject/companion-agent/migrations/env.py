"""Alembic 环境。连接串来自 COMPANION_MYSQL_URL（O §8.1），不进仓库。"""

import os

from alembic import context

from companion.adapters.store.mysql.schema import metadata

config = context.config
target_metadata = metadata
# vpn 库里已有别的应用的 alembic_version，版本表必须带前缀。
VERSION_TABLE = "ca_alembic_version"


def _url() -> str:
    url = os.environ.get("COMPANION_MYSQL_URL", "")
    if not url:
        raise RuntimeError("COMPANION_MYSQL_URL 未设置")
    return url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, render_as_batch=False,
                      version_table=VERSION_TABLE)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine

    # 迁移是同步执行的：把运行时的异步驱动换成同步驱动，连接串其它部分不变。
    engine = create_engine(_url().replace("+aiomysql", "+pymysql"))
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, version_table=VERSION_TABLE)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
