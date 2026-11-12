"""环境变量配置。所有变量以 COMPANION_ 或 LIVEKIT_ 开头，见 .env.example。"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    companion_env: str = "dev"
    companion_log_level: str = "INFO"

    companion_llm_routing_path: Path = Field(
        default=PROJECT_ROOT / "config" / "llm" / "routing.yaml"
    )
    companion_llm_api_base: str = ""
    companion_llm_api_key: str = ""

    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    companion_token_ttl_sec: int = 600

    # 身份验证：redis_token（生产，读 Java 登录态）或 allow_all（仅 dev）。D §4、A §5.5
    companion_auth_verifier: str = "allow_all"
    auth_redis_url: str = ""
    # 新聊天栈的存储。目标库是 Postgres（表前缀 ca_），例如 postgresql+psycopg://user:pass@host/db；
    # companion_mysql_url 是旧的 MySQL 测试库，只在没配 Postgres 时使用。Redis 共用，键前缀 ca:。
    companion_database_url: str = ""
    # 也可以不给整串，而是分开给各部分（密码里有 @ : / 等字符时更安全，由代码负责转义）。
    # 整串 companion_database_url 优先；分开给时 host 与 name 必填。
    companion_db_host: str = ""
    companion_db_port: int = 5432
    companion_db_name: str = ""
    companion_db_user: str = ""
    companion_db_password: str = ""
    companion_mysql_url: str = ""
    companion_redis_url: str = ""
    # 大脑对话线程的 checkpoint（LangGraph AsyncPostgresSaver，psycopg 连接串）。
    # 留空时从 companion_database_url 推导；两者都没有则大脑无状态（每轮只看本轮输入，仅用于测试）。
    companion_checkpoint_url: str = ""
    # 质检数据（模型调用、语音回合）保留多少天，到期由后台任务删除（含音频对象）。
    companion_qa_retention_days: int = 90
    # 会话内压缩：未摘要的历史超过这么多 token 时，把较早的消息压成摘要，保留最近这么多条原文。
    companion_summary_trigger_tokens: int = 9000
    companion_summary_keep_messages: int = 20

    @property
    def database_url(self) -> str:
        if self.companion_database_url:
            return self.companion_database_url
        if self.companion_db_host and self.companion_db_name:
            from companion.bootstrap.database import build_url

            return build_url(host=self.companion_db_host, port=self.companion_db_port,
                             database=self.companion_db_name, user=self.companion_db_user,
                             password=self.companion_db_password).render_as_string(hide_password=False)
        return self.companion_mysql_url

    @property
    def checkpoint_url(self) -> str:
        """psycopg 连接串：去掉 SQLAlchemy 的驱动后缀。只有 Postgres 才能用作 checkpoint。"""
        from companion.bootstrap.database import to_psycopg_conninfo

        url = self.companion_checkpoint_url or self.companion_database_url or (
            self.database_url if self.companion_db_host else "")
        if not url.startswith(("postgresql", "postgres")):
            return ""
        return to_psycopg_conninfo(url)

    # 对象存储：火山引擎 TOS（S3 兼容），与 job-come 同一个区域与接口（上传图片、解题附件）
    tos_endpoint: str = ""
    tos_region: str = "cn-beijing"
    tos_bucket: str = ""
    tos_access_key: str = ""
    tos_secret_key: str = ""
    # 桶内前缀：生产 companion/，测试 companion-test/（与 job-come 共用同一个桶）
    tos_key_prefix: str = "companion/"
    # 运营接口（形象上下线）的管理令牌。为空 = 这些接口关闭，不留默认口令。
    companion_admin_token: str = ""


settings = Settings()
