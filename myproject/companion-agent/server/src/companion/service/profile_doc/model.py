"""用户档案（形态 A）的数据形状。

和画像条目（persona_entry）是同一件事的两种形态：
- 画像是**条目**——逐条增、可回滚、可按来源事实联动删除；
- 档案是**一篇 Markdown**——长篇叙事版，LLM 后台任务按批整体维护，管理员可直接改写。
两者都按「用户 + 角色」隔离、都始终注入提示词（不靠检索命中）。

三条规则决定它的形状：
- **一行一人一角**：``ca_profile_doc`` 的主键就是 (owner_id, role_id)；
- **管理员永远赢**：LLM 的每次维护都带版本号（乐观并发）——管理员在这期间改过，
  这一批就放弃，下一批以管理员的版本为底稿重写；
- **档案是数据不是指令**：注入时包在参考信息块里（templates.PROFILE_DOC_HEADER）。
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_DOC_CHARS = 1600      # 档案总长的上限：LLM 输出超长视为不合格，保留旧版


@dataclass(frozen=True)
class ProfileDoc:
    owner_id: int
    role_id: str
    markdown: str         # 空串 = 游标行先于档案出现，还没生成过
    version: int          # 每写一次 +1（llm 或 admin）
    source: str           # "" | llm | admin
    last_message_id: int  # LLM 维护处理到的用户消息 id
