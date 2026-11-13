"""连接串的纯函数：拼接、识别方言、转 psycopg 连接串。

单独成模块是因为 ``config``（读环境变量）要用它们，而 ``config`` 不能反过来依赖 ``bootstrap``
（分层契约：只有组合根与入口可以引 bootstrap）。这里只依赖 SQLAlchemy 的 URL 类型，没有 I/O。
"""

from __future__ import annotations

from sqlalchemy.engine import URL, make_url


def build_url(*, host: str, port: int, database: str, user: str, password: str,
              driver: str = "postgresql+psycopg") -> URL:
    """用各部分拼连接串。

    密码里常有 ``@``、``:``、``/``、``#``，直接字符串拼接会把它们当成分隔符，
    解析出错误的主机名。``URL.create`` 保存原始值，渲染时才做百分号转义。
    """
    return URL.create(drivername=driver, username=user or None, password=password or None,
                      host=host, port=port, database=database)


def is_postgres(url: str | URL) -> bool:
    return make_url(url).get_backend_name() == "postgresql"


def to_psycopg_conninfo(url: str | URL) -> str:
    """SQLAlchemy 连接串 → psycopg 连接串（去掉驱动后缀，密码保持转义）。非 Postgres 返回空串。"""
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql":
        return ""
    return parsed.set(drivername="postgresql").render_as_string(hide_password=False)
