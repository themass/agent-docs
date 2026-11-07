"""记忆层。

主键是用户，跨角色共享；每条记忆带来源角色与来源消息。端口定义在 ``port.py``，
v1 后端 mem0（``mem0.py``），Hindsight 作为备选接在同一个端口后面，测试用
``fake.py``。抽取在 ``extraction.py``，回合结束后异步跑。

``mem0`` 是可选依赖，本包 import 时不拉起任何后端。
"""

from companion.memory.extraction import (
    FORBIDDEN_CATEGORIES,
    MemoryExtractor,
    build_extraction_prompt,
    is_forbidden_content,
    parse_candidates,
)
from companion.memory.fake import InMemoryMemoryPort
from companion.memory.mem0 import Mem0MemoryPort, Mem0Unavailable
from companion.memory.port import MemoryItem, MemoryKind, MemoryPort

__all__ = [
    "FORBIDDEN_CATEGORIES",
    "InMemoryMemoryPort",
    "Mem0MemoryPort",
    "Mem0Unavailable",
    "MemoryExtractor",
    "MemoryItem",
    "MemoryKind",
    "MemoryPort",
    "build_extraction_prompt",
    "is_forbidden_content",
    "parse_candidates",
]
