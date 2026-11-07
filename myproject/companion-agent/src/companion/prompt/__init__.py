"""提示词组装：skill 包 + 角色卡。

宿主（LiveKit Agent 的 instructions）在这里拿两段文本：角色人设与 skill 块。
两者都不依赖模型主动读文件——skill 正文与参考片段在组装时就已内联。
"""

from companion.prompt.character import (
    CharacterCard,
    CharacterFormatError,
    from_v2_json,
    render_persona,
    slugify,
    to_v2_json,
)
from companion.prompt.skills import (
    SkillError,
    SkillFormatError,
    SkillLibrary,
    SkillNotFound,
    SkillPackage,
    SkillPathError,
    compose,
    split_frontmatter,
)

__all__ = [
    "CharacterCard",
    "CharacterFormatError",
    "SkillError",
    "SkillFormatError",
    "SkillLibrary",
    "SkillNotFound",
    "SkillPackage",
    "SkillPathError",
    "compose",
    "from_v2_json",
    "render_persona",
    "slugify",
    "split_frontmatter",
    "to_v2_json",
]
