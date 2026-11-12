"""连接串怎么拼、池怎么配、连接预算怎么算。都不需要真实数据库（引擎是惰性的）。"""

import logging

import pytest

from companion import dburl
from companion.bootstrap import database as db
from companion.config import Settings

@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """导入 DeerFlow 的测试会把 .env 加载进进程环境，Settings 即使不读文件也会读到它们。
    这里的断言是关于“配置怎么拼成连接串”，必须不受本机环境影响。"""
    for name in ("COMPANION_DATABASE_URL", "COMPANION_MYSQL_URL", "COMPANION_CHECKPOINT_URL", "COMPANION_DB_HOST",
                 "COMPANION_DB_PORT", "COMPANION_DB_NAME", "COMPANION_DB_USER", "COMPANION_DB_PASSWORD"):
        monkeypatch.delenv(name, raising=False)


PASSWORD = "Pa@ss:w/rd#1"   # 故意放进所有会被当成分隔符的字符


def test_special_characters_in_the_password_survive_the_url():
    url = dburl.build_url(host="db.internal", port=5432, database="app", user="svc", password=PASSWORD)
    rendered = url.render_as_string(hide_password=False)
    # 渲染出的串能被重新解析回原样；直接字符串拼接做不到
    parsed = dburl.make_url(rendered)
    assert (parsed.host, parsed.port, parsed.username, parsed.password) == ("db.internal", 5432, "svc", PASSWORD)


def test_the_password_is_hidden_when_the_url_is_printed():
    url = dburl.build_url(host="h", port=1, database="d", user="u", password=PASSWORD)
    assert PASSWORD not in str(url)


def test_psycopg_conninfo_keeps_the_escaped_password_and_drops_the_driver():
    url = dburl.build_url(host="h", port=1, database="d", user="u", password=PASSWORD)
    info = dburl.to_psycopg_conninfo(url)
    assert info.startswith("postgresql://") and "+psycopg" not in info
    assert dburl.make_url(info).password == PASSWORD


def test_non_postgres_has_no_checkpoint_conninfo():
    assert dburl.to_psycopg_conninfo("sqlite+aiosqlite:///:memory:") == ""


def test_settings_build_the_url_from_parts():
    s = Settings(_env_file=None, companion_db_host="h", companion_db_name="d", companion_db_user="u",
                 companion_db_password=PASSWORD, companion_db_port=6543)
    assert dburl.make_url(s.database_url).password == PASSWORD
    assert dburl.make_url(s.checkpoint_url).port == 6543


def test_a_full_url_wins_over_parts():
    s = Settings(_env_file=None, companion_database_url="postgresql+psycopg://a:b@x/y",
                 companion_db_host="other", companion_db_name="other")
    assert dburl.make_url(s.database_url).host == "x"


def test_parts_without_a_host_do_not_make_a_url():
    s = Settings(_env_file=None, companion_db_user="u", companion_db_password="p")
    assert s.database_url == "" and s.checkpoint_url == ""


@pytest.mark.parametrize("name", ["api", "jobs", "voice"])
def test_every_profile_has_a_bounded_peak(name):
    p = db.profile_for(name)
    assert p.peak == p.pool_size + p.max_overflow + p.checkpoint_max
    assert 0 < p.peak <= 40


def test_voice_is_the_smallest_profile_because_each_room_is_a_process():
    assert db.profile_for("voice").peak < db.profile_for("jobs").peak < db.profile_for("api").peak


def test_unknown_profile_is_an_error_not_a_default():
    with pytest.raises(ValueError):
        db.profile_for("typo")


def test_postgres_engine_gets_the_profile_pool():
    url = dburl.build_url(host="h", port=1, database="d", user="u", password="p").render_as_string(hide_password=False)
    engine = db.make_engine(url, db.profile_for("voice"))
    pool = engine.sync_engine.pool
    assert (pool.size(), pool._max_overflow) == (2, 2)
    assert pool._recycle == db.POOL_RECYCLE_SEC and pool._timeout == db.POOL_TIMEOUT_SEC


def test_sqlite_engine_is_built_without_pool_arguments():
    # SQLite 的池类型不接受 pool_size：套用会直接抛 TypeError
    assert db.make_engine("sqlite+aiosqlite:///:memory:", db.profile_for("api")) is not None


def test_connections_are_tagged_with_the_process_role_and_timeouts():
    opts = db.server_options("companion-voice")
    assert opts["application_name"] == "companion-voice"
    assert "statement_timeout=30000" in opts["options"]
    assert "idle_in_transaction_session_timeout=60000" in opts["options"]
    assert len(db.server_options("x" * 100)["application_name"]) == 63


def test_checkpoint_pool_is_closed_until_the_loop_opens_it():
    url = dburl.build_url(host="h", port=1, database="d", user="u", password="p").render_as_string(hide_password=False)
    pool = db.make_checkpoint_pool(url, db.profile_for("api"))
    assert pool.closed and pool.max_size == db.profile_for("api").checkpoint_max


def test_budget_adds_up_per_process_type():
    expected = (db.profile_for("api").peak * 2 + db.profile_for("jobs").peak + db.profile_for("voice").peak * 8)
    assert db.connection_budget({"api": 2, "jobs": 1, "voice": 8}) == expected


def test_an_over_budget_plan_is_warned_about(caplog):
    with caplog.at_level(logging.WARNING, logger="companion.database"):
        db.check_budget({"api": 2, "voice": 20}, max_connections=100)
    assert "exceeds" in caplog.text


def test_a_plan_within_budget_is_quiet(caplog):
    with caplog.at_level(logging.WARNING, logger="companion.database"):
        db.check_budget({"api": 1, "jobs": 1, "voice": 2}, max_connections=100)
    assert caplog.text == ""
