"""流式文本处理：断句 + 头像事件映射。

上层拿到的永远是整句和规范情绪名，不关心模型怎么切块、怎么写标签。
"""

from companion.text.events import (
    AVATAR_PROTOCOL_VERSION,
    strip_emotion_tags,
    to_avatar_events,
)
from companion.text.splitter import SentenceSplitter, split_sentences

__all__ = [
    "AVATAR_PROTOCOL_VERSION",
    "SentenceSplitter",
    "split_sentences",
    "strip_emotion_tags",
    "to_avatar_events",
]
