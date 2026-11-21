"""用户档案存储协议。所有方法按「用户 + 角色」隔离（和画像、关系一致）。"""

from __future__ import annotations

from typing import Protocol

from companion.service.profile_doc.model import ProfileDoc


class ProfileDocStore(Protocol):
    async def get(self, *, owner_id: int, role_id: str) -> ProfileDoc | None:
        """该（用户，角色）的档案行；没聊过返回 None。"""
        ...

    async def advance(self, *, owner_id: int, role_id: str, last_message_id: int, add_chars: int) -> int:
        """回合收尾调用：累计待维护的用户发言字数（档案不存在时先建游标行）。"""
        ...

    async def commit_llm(self, *, owner_id: int, role_id: str, markdown: str, up_to_message_id: int,
                         expected_version: int) -> bool:
        """LLM 维护的落库（乐观并发）。期间版本被管理员改过则放弃，返回 False。"""
        ...

    async def mark_processed(self, *, owner_id: int, role_id: str, last_message_id: int) -> None:
        """本批看完了但档案无变化：只推进水位，不动正文。"""
        ...

    async def save_admin(self, *, owner_id: int, role_id: str, markdown: str) -> bool:
        """管理员改写：无条件覆盖，版本 +1。"""
        ...

    async def delete_user(self, *, owner_id: int) -> int:
        """账号注销：该用户的全部档案行物理删除。返回删除行数。"""
        ...
