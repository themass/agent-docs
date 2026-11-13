"""memory_hub：多应用共享的记忆库（D §10）。

与 companion 解耦：只依赖一个「记忆端口」（add / search / delete_one / delete_user / list_for_user），
不认识 LangGraph、FastAPI 或业务类型之外的任何东西。浅聊与 job-come 各自通过 ``for_app`` 获得
作用域绑定的客户端；隔离靠复合 ``app:uid``（存储原生过滤字段），而不是 metadata。
"""

from memory_hub.config import AppConfig, ConfigError, validate_configs
from memory_hub.hub import MemoryHub, ScopedMemory, UnknownApp
from memory_hub.scope import compose_user_id, split_user_id

__all__ = [
    "AppConfig",
    "ConfigError",
    "MemoryHub",
    "ScopedMemory",
    "UnknownApp",
    "compose_user_id",
    "split_user_id",
    "validate_configs",
]
