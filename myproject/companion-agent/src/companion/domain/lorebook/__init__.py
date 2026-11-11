"""世界书（World Info / Lorebook）：按关键词激活、按位置注入的设定条目。

语义参照 SillyTavern（洁净室实现，见 chat-agent-harness-greenfield.md 第 5 节），第一版范围：
主次关键词与逻辑、常驻、插入位置（角色前 / 角色后 / @深度）、深度与角色、顺序号、预算。
不做：递归、包含组、粘滞 / 冷却 / 延迟、概率。
"""

from companion.domain.lorebook.model import LoreEntry, Lorebook, from_character_book
from companion.domain.lorebook.scan import Activation, activate

__all__ = ["Activation", "LoreEntry", "Lorebook", "activate", "from_character_book"]
