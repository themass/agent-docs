"""会话摘要重建用的纯函数与模板。

摘要的日常维护由大脑的摘要中间件完成（超阈值时压缩较早的消息）。这里处理的是例外：
用户删除或编辑了已被压缩进摘要的消息时，从消息表里**未删除**的内容重新生成摘要，
保证删掉的内容模型也看不到（chat-agent-next-plan.md §7 决策 3）。

提示词要点参照 SillyTavern 的摘要扩展（洁净室实现）：最重要的事实与事件、只输出摘要、给长度上限；
长度按字符而不是「词」计——中文与阿拉伯语按空格数词会得到 0。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

RESUMMARIZE_JOB = "session.resummarize"
MAX_TRANSCRIPT_CHARS = 16000
SUMMARY_MAX_CHARS = 1200

SUMMARY_PROMPT = """你是对话摘要器。把下面这段角色扮演对话压缩成一段摘要，供角色在之后的对话里回忆前情。

要求：
- 保留：人名与称呼、彼此的约定与计划、日期、未完成的话题、剧情进展与设定。
- 不保留：寒暄、已解决问题的细节、工具结果原文。
- 不记录：证件号、银行卡号、密码、精确住址、医疗诊断与用药。
- 用对话所用的语言，第三人称客观叙述，不超过 {max_chars} 个字符。
- 只输出摘要本身，不要标题、不要解释。

对话：
{transcript}
"""


@dataclass(frozen=True)
class TranscriptLine:
    role: str      # user | assistant
    text: str


def render_transcript(lines: Sequence[TranscriptLine], *, user_label: str = "用户", char_label: str = "角色",
                      max_chars: int = MAX_TRANSCRIPT_CHARS) -> str:
    """从最新往前保留，直到字符上限（太早的部分本来就该由更早的摘要承担）。"""
    rendered: list[str] = []
    used = 0
    for line in reversed(lines):
        label = user_label if line.role == "user" else char_label
        text = f"{label}：{line.text.strip()}"
        if used + len(text) > max_chars:
            break
        rendered.append(text)
        used += len(text)
    return "\n".join(reversed(rendered))


def summary_prompt(transcript: str, *, max_chars: int = SUMMARY_MAX_CHARS) -> str:
    return SUMMARY_PROMPT.format(transcript=transcript, max_chars=max_chars)
