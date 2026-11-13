"""技能目录端口：组装提示词时只需要「按 id 合成正文」这一能力。"""

from __future__ import annotations

from typing import Protocol


class SkillCatalog(Protocol):
    def compose(self, skill_ids, *args, **kwargs) -> str: ...

    def selected_ids(self, skill_ids, *args, **kwargs) -> list[str]: ...
