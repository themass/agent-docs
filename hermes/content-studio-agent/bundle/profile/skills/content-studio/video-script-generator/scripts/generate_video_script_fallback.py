#!/usr/bin/env python3
"""Generate a degraded video script from the daily report Top 5."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

_ITEM_PATTERN = re.compile(
    r"###\s+(\d+)\.\s+([^\n]+).*?\| GitHub \| (https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+) \|",
    re.S,
)
_SPEECH_MARKERS = ("第一个", "第二个", "第三个", "第四个", "第五个")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("daily_report", help="Path to daily report markdown.")
    parser.add_argument("script_file", help="Output video script path.")
    parser.add_argument("date", help="Report date YYYY-MM-DD.")
    args = parser.parse_args()

    daily = Path(args.daily_report)
    out = Path(args.script_file)
    text = daily.read_text(encoding="utf-8", errors="replace")
    items = _ITEM_PATTERN.findall(text)[:5]
    if len(items) < 5:
        return 1

    names = [name.strip() for _, name, _ in items]
    lines = [
        f"# 视频脚本：今日 GitHub 热榜 | {args.date}",
        "",
        "## 说明",
        "",
        "本脚本由日报 Top 5 降级生成。模型脚本生成超时或不可用时，先保证视频流水线可以继续产出素材。",
        "",
        "## 入选项目",
        "",
    ]
    for rank, name, url in items:
        lines.append(f"{rank}. #{rank} [{name.strip()}]({url})")

    narration_intro = (
        f"大家好，今天我们快速看五个 GitHub 热榜项目："
        f"{names[0]}、{names[1]}、{names[2]}、{names[3]} 和 {names[4]}。"
    )
    project_lines = [
        "",
        "---",
        "",
        "## 完整口播文本",
        "",
        narration_intro,
        "",
    ]
    templates = [
        "它今天排在 GitHub Trending 前列，核心卖点是帮开发者更快判断这个项目值不值得试用。建议先看 README、Demo 和 Issues，确认它能不能直接进你的工具箱。",
        "这个项目解决的是一个很具体的开发或内容生产痛点，不是泛泛的概念项目。如果你正在找能立刻上手、能马上看到效果的开源工具，这个值得收藏后做一次本地试用。",
        "它的亮点在于概念清晰、展示性强，适合做成短视频讲解。如果你关注 AI、开发效率或者开源工具生态，建议继续跟踪它的更新节奏和社区反馈。",
        "它代表了今天热榜里一个很典型的工程方向，适合作为你工具链里的一个备选组件。先 star，再挑一个最小场景做验证。",
        "最后一个项目更适合做长期跟踪，不一定马上上手，但很适合放进你的观察清单。关注它的 release 节奏和社区讨论，往往比一次性 demo 更有价值。",
    ]
    for marker, name, template in zip(_SPEECH_MARKERS, names, templates):
        project_lines.append(f"{marker}，{name}。{template}")
        project_lines.append("")

    project_lines.extend(
        [
            "这五个项目都来自今天的日报 Top 5。你最想先试哪一个？评论区告诉我，明天继续给你选好货。",
            "",
            "---",
            "",
            "## 小红书发布素材",
            "",
            "### 标题备选",
            "1. 今日 GitHub 热榜 Top 5，先收藏再试用",
            "2. 程序员今天都在看什么开源项目？",
            "3. GitHub 今日值得关注的 5 个项目",
            "",
            "### 标签",
            "#GitHub #开源项目 #AI工具 #程序员 #效率工具",
            "",
        ]
    )
    lines.extend(project_lines)
    out.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
