"""从 Hermes 内置记忆文件加载 Core 上下文（USER.md + MEMORY.md）。"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_AGENT_DIR = Path.home() / ".hermes"


def _read_bounded(path: Path, max_chars: int = 4000) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8").strip()
    if len(text) > max_chars:
        return text[: max_chars - 3] + "..."
    return text


def load_hermes_core_memory(agent_dir: Path | None = None) -> str:
    """读取 Hermes Persistent Memory，拼成可注入 system 的段落。

    Args:
        agent_dir: Hermes 配置目录，默认 ``~/.hermes``。

    Returns:
        空字符串表示无记忆文件；否则为格式化后的记忆块。
    """
    base = agent_dir or Path(os.environ.get("HERMES_AGENT_DIR", DEFAULT_AGENT_DIR))
    mem_dir = base / "memories"
    user = _read_bounded(mem_dir / "USER.md", 1500)
    memory = _read_bounded(mem_dir / "MEMORY.md", 2200)
    if not user and not memory:
        return ""
    parts: list[str] = ["【关于用户的长期记忆（来自 Hermes，自然提起，不要念档案）】"]
    if user:
        parts.append(f"[用户画像]\n{user}")
    if memory:
        parts.append(f"[Agent 笔记]\n{memory}")
    return "\n\n".join(parts)


def build_instructions(base: str, memory_block: str) -> str:
    """合并人格 prompt 与记忆块。"""
    if not memory_block:
        return base
    return f"{base}\n\n{memory_block}"


if __name__ == "__main__":
    block = load_hermes_core_memory()
    assert isinstance(block, str)
    print(f"memory block chars: {len(block)}")
    if block:
        print(block[:200], "...")
