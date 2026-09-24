#!/usr/bin/env python3
"""Shared helpers for Content Studio ↔ Open Notebook integration."""

from __future__ import annotations

from pathlib import Path

NOTEBOOK_DESCRIPTIONS = {
    "Content Studio Daily": "每日 GitHub/内容策划总报。",
    "Community Pulse": "last30days 社区热点、趋势信号和原始脉搏简报。",
    "GitHub Radar": "GitHub 榜单、项目雷达、年度和单日报告。",
    "Video Production": "视频脚本、发布文案、分镜和生产素材说明。",
    "Raw Research Archive": "原始抓取资料、仓库 raw 分析和可追溯证据。",
}


def read_heading(path: Path) -> str:
    """Read the first markdown H1, or fall back to the filename."""

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def source_date(path: Path) -> str | None:
    """Extract a leading YYYY-MM-DD date from a filename."""

    stem = path.stem
    if len(stem) >= 10 and stem[4] == "-" and stem[7] == "-":
        candidate = stem[:10]
        if all(part.isdigit() for part in candidate.split("-")):
            return candidate
    return None


def build_source_title(path: Path, root: Path) -> str:
    """Build a stable title for duplicate detection in Open Notebook."""

    heading = read_heading(path)
    date = source_date(path)
    if date:
        return f"{date} · {heading}"
    try:
        rel = path.relative_to(root)
        return f"{rel.as_posix()} · {heading}"
    except ValueError:
        return f"{path.name} · {heading}"


def classify_source(path: Path, root: Path) -> list[str]:
    """Map a markdown file to one or more Open Notebook notebooks."""

    rel = path.relative_to(root) if path.is_relative_to(root) else path
    rel_text = rel.as_posix()
    name = path.name
    if "raw" in rel_text or "raw" in name:
        return ["Raw Research Archive"]
    if "github-daily-rank" in str(path) or "github-daily-rank" in str(root) or name.startswith("GITHUB_"):
        return ["GitHub Radar"]
    if name.endswith("-community-pulse.md"):
        return ["Community Pulse"]
    if name.endswith(("-video-script.md", "-video-publish.md", "-storyboard.md")):
        return ["Video Production"]
    if name.endswith(("-production-radar.md", "-weekly.md")):
        return ["GitHub Radar"]
    return ["Content Studio Daily"]


def collect_markdown_files(*roots: Path) -> list[Path]:
    """Collect markdown source files from one or more roots."""

    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file() and root.suffix.lower() == ".md":
            files.append(root)
            continue
        for path in root.rglob("*.md"):
            if path.name == "index.md" or path.name.endswith(".invalid.md"):
                continue
            if ".git" in path.parts:
                continue
            files.append(path)
    return sorted(set(files))
