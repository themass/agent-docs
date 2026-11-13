"""Alembic 环境。连接串来自 COMPANION_DATABASE_URL（Postgres）或 COMPANION_MYSQL_URL（O §8.1），不进仓库。

连接串的来源与运行时的 ``Settings`` 一致：先看进程环境变量，再看项目根目录的 ``.env``。
以前只读 ``os.environ``，结果 ``./run.sh migrate`` 能用（脚本里 source 了 .env）、
直接跑 ``alembic upgrade head`` 却报"未设置"——部署脚本踩的就是这一条。
"""

import os
from pathlib import Path

from alembic import context

from companion.adapters.store.sql.schema import metadata
import companion.adapters.store.sql.memory  # noqa: F401 — 注册 ca_memory_item 到同一个 metadata

config = context.config
target_metadata = metadata
# vpn 库里已有别的应用的 alembic_version，版本表必须带前缀。
VERSION_TABLE = "ca_alembic_version"

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _env(name: str) -> str:
    """环境变量优先；没有就读 .env。只取值，不把整个 .env 灌进环境（迁移不需要别的配置）。"""
    value = os.environ.get(name)
    if value:
        return value
    env_file = PROJECT_ROOT / ".env"
    if not env_file.is_file():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        if key.strip() != name:
            continue
        return raw.strip().strip('"').strip("'")
    return ""


def _url() -> str:
    url = _env("COMPANION_DATABASE_URL") or _env("COMPANION_MYSQL_URL")
    if url:
        return url
    # 分开给的各部分（密码里有 @ : / 时用这组，运行时由 dburl.build_url 负责转义）
    host, name = _env("COMPANION_DB_HOST"), _env("COMPANION_DB_NAME")
    if host and name:
        from companion.dburl import build_url
        return build_url(host=host, port=int(_env("COMPANION_DB_PORT") or 5432), database=name,
                         user=_env("COMPANION_DB_USER"), password=_env("COMPANION_DB_PASSWORD")
                         ).render_as_string(hide_password=False)
    raise RuntimeError("没有数据库连接：COMPANION_DATABASE_URL、COMPANION_MYSQL_URL "
                       "或 COMPANION_DB_HOST + COMPANION_DB_NAME 至少给一组")


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, render_as_batch=False,
                      version_table=VERSION_TABLE)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine

    # 迁移是同步执行的：把运行时的异步驱动换成同步驱动，连接串其它部分不变。
    # psycopg（3）同时支持同步与异步，Postgres 连接串不用改；asyncpg 换成 psycopg。
    engine = create_engine(_url().replace("+aiomysql", "+pymysql").replace("+asyncpg", "+psycopg"))
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, version_table=VERSION_TABLE)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
