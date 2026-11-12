"""数据库连接：连接串怎么拼、连接池多大、总共会占多少连接。

一个进程里有两个池，别混：

- SQLAlchemy 引擎池：业务表（``ca_*``）的读写；
- psycopg 池：LangGraph 的 checkpoint（对话线程）。它是独立的池，所以一个进程实际占用
  ``引擎池上限 + checkpoint 池上限`` 条连接。

Postgres 的连接是进程级资源（每条约占几 MB 内存），上限默认只有 100。服务由多种进程组成
（API、后台任务、语音 worker），所以池大小按**进程角色**分档，并且能算出总预算：
预算超过库的 ``max_connections`` 时，高峰期新请求会拿不到连接，表现是随机超时而不是明确报错。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.engine import URL, make_url

log = logging.getLogger("companion.database")

# 单条 SQL 最长执行时间。聊天链路里没有应该跑超过这个时间的查询，
# 卡住的查询要被打断，否则它会一直占着连接和行锁。
STATEMENT_TIMEOUT_MS = 30_000
# 事务开了却长时间不提交（代码路径里漏了 commit、或进程被挂起）：数据库端直接断开，释放锁。
IDLE_IN_TRANSACTION_TIMEOUT_MS = 60_000


@dataclass(frozen=True)
class PoolProfile:
    """一类进程的连接池规格。"""

    name: str
    pool_size: int        # 引擎池常驻连接数
    max_overflow: int     # 高峰时可额外借出的连接数
    checkpoint_max: int   # checkpoint 池上限

    @property
    def peak(self) -> int:
        """这个进程最多会占用的连接数。"""
        return self.pool_size + self.max_overflow + self.checkpoint_max


# api：处理用户请求，并发最高；
# jobs：后台任务与提醒调度，串行为主；
# voice：LiveKit 为**每个房间**起一个任务进程，所以每个进程要尽量小——同时在线 N 个房间就是 N 份。
PROFILES: dict[str, PoolProfile] = {
    "api": PoolProfile("api", pool_size=10, max_overflow=10, checkpoint_max=10),
    "jobs": PoolProfile("jobs", pool_size=4, max_overflow=4, checkpoint_max=4),
    "voice": PoolProfile("voice", pool_size=2, max_overflow=2, checkpoint_max=2),
}

# 从池里借连接最多等多久。等不到就报错而不是无限排队：排队会让请求堆积、拖垮整个进程。
POOL_TIMEOUT_SEC = 10.0
# 连接存活上限。云数据库和负载均衡会静默回收长空闲的连接，超过它的连接下次使用才发现已断。
POOL_RECYCLE_SEC = 1800


def profile_for(name: str) -> PoolProfile:
    try:
        return PROFILES[name]
    except KeyError:
        raise ValueError(f"unknown pool profile {name!r}, expected one of {sorted(PROFILES)}") from None


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


def server_options(application_name: str) -> dict[str, str]:
    """每条连接建立时带给服务器的参数。

    ``application_name`` 让 ``pg_stat_activity`` 里能分清每条连接属于哪类进程，
    连接数异常时不必靠猜。
    """
    return {
        "application_name": application_name[:63],   # Postgres 的上限
        "options": f"-c statement_timeout={STATEMENT_TIMEOUT_MS} "
                   f"-c idle_in_transaction_session_timeout={IDLE_IN_TRANSACTION_TIMEOUT_MS}",
    }


def make_engine(url: str, profile: PoolProfile, *, process_tag: str = "") -> Any:
    """按进程角色建引擎。非 Postgres（测试用的 SQLite）不套用池参数——它们的池类型不接受这些参数。"""
    from sqlalchemy.ext.asyncio import create_async_engine

    if not is_postgres(url):
        return create_async_engine(url, pool_pre_ping=True)
    app_name = f"companion-{profile.name}" + (f"-{process_tag}" if process_tag else "")
    return create_async_engine(
        url,
        pool_size=profile.pool_size,
        max_overflow=profile.max_overflow,
        pool_timeout=POOL_TIMEOUT_SEC,
        pool_recycle=POOL_RECYCLE_SEC,
        pool_pre_ping=True,
        connect_args=server_options(app_name),
    )


def make_checkpoint_pool(url: str, profile: PoolProfile, *, process_tag: str = "") -> Any:
    """checkpoint 用的 psycopg 池。``open=False``：必须在运行中的事件循环里再 open。

    ``min_size=1``：常驻一条，不在启动时一次性占满上限。
    ``max_lifetime`` / ``timeout`` 与引擎池同一套含义。
    """
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    app_name = f"companion-{profile.name}-ckpt" + (f"-{process_tag}" if process_tag else "")
    opts = server_options(app_name)
    return AsyncConnectionPool(
        to_psycopg_conninfo(url),
        open=False,
        min_size=1,
        max_size=profile.checkpoint_max,
        timeout=POOL_TIMEOUT_SEC,
        max_lifetime=POOL_RECYCLE_SEC,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row,
                "application_name": opts["application_name"], "options": opts["options"]},
    )


def connection_budget(processes: dict[str, int]) -> int:
    """各类进程按数量折算后，最多会占用多少条数据库连接。

    ``processes``：{"api": 2, "jobs": 1, "voice": 8}。
    """
    return sum(profile_for(name).peak * count for name, count in processes.items())


def check_budget(processes: dict[str, int], *, max_connections: int, reserve: int = 10) -> int:
    """预算超过 ``max_connections - reserve`` 时记警告，返回预算。

    ``reserve`` 留给运维直连、迁移、监控和 Java 服务等不归我们管的连接。
    如果库是和别的服务共用的，传入的 ``max_connections`` 应该是分给本服务的份额。
    """
    budget = connection_budget(processes)
    limit = max_connections - reserve
    if budget > limit:
        log.warning("database connection budget %d exceeds %d (max_connections=%d, reserve=%d): %s",
                    budget, limit, max_connections, reserve, processes)
    return budget
