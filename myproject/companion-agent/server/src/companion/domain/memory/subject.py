"""记忆主体：按角色隔离记忆空间。

同一个用户和不同角色聊天，各自记住的东西互不相通：和林澈说过的事，苏黛不知道。
隔离做在「记忆主体 id」上（``{owner}.{role}``），而不是在每个后端里加过滤条件，
因此任何满足记忆接口的后端都自动隔离，接口本身不用改。

主体 id 不含冒号（memory_hub 用冒号拼 ``app:uid``）；角色 id 里出现不安全的字符时取哈希。
"""

from __future__ import annotations

import hashlib
import re

_SAFE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SEP = "."


def role_key(role_id: str) -> str:
    if _SAFE.match(role_id):
        return role_id
    return "h" + hashlib.sha256(role_id.encode("utf-8")).hexdigest()[:24]


def role_subject(owner_id: int | str, role_id: str | None) -> str:
    """角色维度的记忆主体。``role_id`` 为空时退回用户级（不属于任何角色的记忆，例如手动添加的）。"""
    owner = str(owner_id)
    if not role_id:
        return owner
    return f"{owner}{SEP}{role_key(role_id)}"
