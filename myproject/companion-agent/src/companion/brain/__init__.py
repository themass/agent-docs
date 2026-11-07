"""对话主脑（brain）抽象。

DeerFlow 是 v1 的主脑，但这个包只依赖一个很小的接口，这样：

- 单测能用 fake 主脑跑，不需要 DeerFlow 的 wheel、模型和网络；
- 以后换主脑（或给简单回合加直连模型分支）不改 LiveKit 那一层。

主脑的产出是**未断句的文本片段流**。断句、情绪标签剥离、送 TTS 都在上层做。
"""

from companion.brain.port import BrainPort, BrainTurn
from companion.brain.fake import FakeBrain

__all__ = ["BrainPort", "BrainTurn", "FakeBrain"]
