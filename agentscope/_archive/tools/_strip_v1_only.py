#!/usr/bin/env python3
"""Remove *pure* v0.x / v1 API 叙述；保留 v2 仍适用的设计与概念模型正文。

在完整长文恢复后运行：
  python3 _strip_v1_only.py AgentScopev2.md

默认原地写回；加 --dry-run 只打印将删除的行数。
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

# 整段删除：明确只描述已移除 API、且对 v2 读者无设计价值的短节（可按需扩展）
SECTION_DROP_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^##\s+18\.\s+与 v0\.x 的差异"),
]

# 行级删除：仅当整行匹配（避免误伤表格中的对照词）
LINE_DROP_EXACT = {
    "JSONSession",
}

# 行内若仅为「v0.x 已移除」类脚注则保留；下列正则删除整行说明性列表项（可选，保守默认关闭）
LINE_DROP_REGEX: list[re.Pattern[str]] = []


def should_drop_section_start(line: str) -> bool:
    return any(p.search(line) for p in SECTION_DROP_PATTERNS)


def process(lines: list[str]) -> list[str]:
    out: list[str] = []
    skip_section = False
    section_level = 0

    for line in lines:
        m = re.match(r"^(#+)\s", line)
        if skip_section and m:
            lvl = len(m.group(1))
            if lvl <= section_level:
                skip_section = False
            else:
                continue
        if not skip_section and m and should_drop_section_start(line):
            skip_section = True
            section_level = len(m.group(1))
            continue
        if skip_section:
            continue
        if line.strip() in LINE_DROP_EXACT:
            continue
        if any(p.search(line) for p in LINE_DROP_REGEX):
            continue
        out.append(line)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    text = args.path.read_text(encoding="utf-8")
    lines = text.splitlines()
    new_lines = process(lines)
    print(f"lines: {len(lines)} -> {len(new_lines)} (removed {len(lines) - len(new_lines)})")
    if not args.dry_run:
        args.path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
