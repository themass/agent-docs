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

    # 对象存储：火山引擎 TOS（S3 兼容），与 job-come 同一个区域与接口（上传图片、解题附件）
    tos_endpoint: str = ""
    tos_region: str = "cn-beijing"
    tos_bucket: str = ""
    tos_access_key: str = ""
    tos_secret_key: str = ""


settings = Settings()
