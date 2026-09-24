#!/usr/bin/env python3
"""Generate hybrid storyboard/spec from a Content Studio video script."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - JSON is valid YAML fallback.
    yaml = None  # type: ignore[assignment]


DEFAULT_REPORT_DIR = Path("/Users/gqli/.hermes/profiles/content-studio/reports")
NEGATIVE_PROMPT = (
    "watermark, logo, fake text, unreadable text, blurry, distorted hands, "
    "generic programmer typing, low quality"
)


@dataclass
class Project:
    rank: str
    repo: str
    role: str
    description: str


def _section(text: str, title: str) -> str:
    pattern = rf"^##\s+{re.escape(title)}[^\n]*\n(.*?)(?=^##\s+|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.MULTILINE)
    return match.group(1).strip() if match else ""


def _first_bullet_value(section: str, label: str) -> str:
    pattern = rf"-\s+\*\*{re.escape(label)}\*\*\s*:\s*(.+)"
    match = re.search(pattern, section)
    return _clean(match.group(1)) if match else ""


def _clean(value: str) -> str:
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"\1", value)
    value = re.sub(r"[*_`#]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" 。；;")


def parse_projects(section: str) -> list[Project]:
    projects: list[Project] = []
    pattern = re.compile(
        r"^\d+\.\s+#(?P<rank>\d+)\s+\[(?P<repo>[^\]]+)\]\([^)]+\)\s*[—–-]\s*(?P<body>.+)$",
        re.MULTILINE,
    )
    for match in pattern.finditer(section):
        body = _clean(match.group("body"))
        role = ""
        role_match = re.search(r"链上角色[：:]\s*([^。；;]+)", body)
        if role_match:
            role = _clean(role_match.group(1))
        if not role:
            role = "趋势链路角色"
        projects.append(
            Project(
                rank=match.group("rank"),
                repo=match.group("repo"),
                role=role,
                description=body,
            )
        )

    if projects:
        return projects[:5]

    fallback_pattern = re.compile(r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)")
    seen: set[str] = set()
    for index, match in enumerate(fallback_pattern.finditer(section), start=1):
        repo = match.group(1)
        if repo in seen:
            continue
        seen.add(repo)
        projects.append(
            Project(
                rank=str(index),
                repo=repo,
                role="趋势链路角色",
                description="来自脚本的 GitHub 项目",
            )
        )
    return projects[:5]


def build_visual_prompt(thesis: str, trend_label: str, *, kind: str) -> str:
    topic = trend_label or thesis or "AI developer tooling"
    if kind == "outro":
        return (
            f"A vertical cinematic 9:16 closing scene representing the long-term shift of {topic}, "
            "modular AI engineering systems becoming reliable infrastructure, clean dark navy "
            "developer-tool atmosphere, subtle depth, professional, no readable text, no logos."
        )
    return (
        f"A vertical cinematic 9:16 visual metaphor for {topic}, AI agent workflows becoming "
        "structured reusable engineering assets, modular glowing cards connected by clean data rails, "
        "professional developer-tool atmosphere, subtle depth, no readable text, no logos."
    )


def build_spec(date: str, report_dir: Path, script_path: Path, text: str) -> dict[str, Any]:
    year, month, _ = date.split("-")
    base = report_dir / year / month
    theme_section = _section(text, "本期主题")
    projects_section = _section(text, "入选项目")
    thesis = _first_bullet_value(theme_section, "一句话 thesis") or _first_bullet_value(
        theme_section, "一句 thesis"
    )
    trend_label = _first_bullet_value(theme_section, "趋势标签") or "GitHub 热榜趋势"
    evidence = _first_bullet_value(theme_section, "核心证据")
    projects = parse_projects(projects_section)

    if not thesis:
        title_match = re.search(r"^#\s+(.+)", text, re.MULTILINE)
        thesis = _clean(title_match.group(1)) if title_match else "今天 GitHub 热榜显示一个新的技术趋势"

    segments: list[dict[str, Any]] = [
        {
            "id": "intro-thesis",
            "asset_type": "card",
            "visual_type": "concept_card",
            "duration_seconds": 10,
            "narration_ref": "intro",
            "card": {
                "title": trend_label,
                "subtitle": thesis,
                "bullets": [b for b in [evidence, "来自 GitHub Trending 的真实项目证据"] if b],
            },
        },
        {
            "id": "intro-ai-broll",
            "asset_type": "ai_broll",
            "visual_type": "ai_generated",
            "duration_seconds": 6,
            "narration_ref": "intro_metaphor",
            "visual_prompt": build_visual_prompt(thesis, trend_label, kind="intro"),
            "negative_prompt": NEGATIVE_PROMPT,
            "ai_broll": {
                "provider": "volcengine_seedance",
                "mode": "text_to_video",
                "fallback": "concept_card",
            },
        },
    ]

    for index, project in enumerate(projects[:3], start=1):
        segments.append(
            {
                "id": f"project-{index}-github",
                "asset_type": "github",
                "visual_type": "github_scroll_callout",
                "duration_seconds": 18,
                "narration_ref": f"project_{index}_evidence",
                "repo": project.repo,
                "callouts": ["repo_name", "stars", "readme"],
            }
        )
        segments.append(
            {
                "id": f"project-{index}-card",
                "asset_type": "card",
                "visual_type": "concept_card",
                "duration_seconds": 7,
                "narration_ref": f"project_{index}_capabilities",
                "card": {
                    "title": project.role,
                    "subtitle": project.repo,
                    "bullets": [
                        f"排名 #{project.rank}",
                        _clean(project.description)[:90] or "项目能力拆解",
                        "用真实 GitHub 证据承接口播",
                    ],
                },
            }
        )

    segments.extend(
        [
            {
                "id": "outro-ai-broll",
                "asset_type": "ai_broll",
                "visual_type": "ai_generated",
                "duration_seconds": 6,
                "narration_ref": "outro_metaphor",
                "visual_prompt": build_visual_prompt(thesis, trend_label, kind="outro"),
                "negative_prompt": NEGATIVE_PROMPT,
                "ai_broll": {
                    "provider": "volcengine_seedance",
                    "mode": "text_to_video",
                    "fallback": "concept_card",
                },
            },
            {
                "id": "outro-summary",
                "asset_type": "card",
                "visual_type": "summary_card",
                "duration_seconds": 10,
                "narration_ref": "outro",
                "card": {
                    "title": "长期判断",
                    "subtitle": trend_label,
                    "bullets": ["不是单个项目爆火，而是一条能力链正在成型", "先看证据，再看可落地机会"],
                },
            },
        ]
    )

    return {
        "version": 1,
        "profile": "content-studio",
        "pipeline": "hybrid-video",
        "metadata": {
            "date": date,
            "source_report": str(base / f"{date}.md"),
            "script_file": str(script_path),
            "storyboard_file": str(base / f"{date}-hybrid-storyboard.md"),
            "output_video": str(base / f"{date}-hybrid-video.mp4"),
            "asset_dir": str(base / "assets" / f"{date}-hybrid"),
        },
        "render_policy": {
            "preserve_existing_pipelines": True,
            "fail_fast_on_github": True,
            "ai_broll_failure_policy": "card_fallback",
            "max_ai_broll_segments": 3,
        },
        "theme": {
            "thesis": thesis,
            "trend_label": trend_label,
        },
        "segments": segments,
    }


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if yaml is not None:
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_storyboard(path: Path, spec: dict[str, Any]) -> None:
    theme = spec["theme"]
    rows = []
    for segment in spec["segments"]:
        rows.append(
            "| {id} | {duration}s | {asset_type} | {visual_type} | {material} |".format(
                id=segment["id"],
                duration=segment["duration_seconds"],
                asset_type=segment["asset_type"],
                visual_type=segment["visual_type"],
                material=segment.get("repo") or segment.get("visual_prompt", "")[:48] or segment.get("card", {}).get("title", ""),
            )
        )
    content = f"""# Hybrid 视频分镜：{theme['trend_label']} | {spec['metadata']['date']}

## 视频目标

- **链路**: hybrid-video（第三条独立链路，不替代 sop/mpt）
- **核心 thesis**: {theme['thesis']}
- **AI 素材策略**: 仅 2-3 段 `ai_broll`，其余用 GitHub 证据和概念卡。

## 分镜表

| 段ID | 时长 | asset_type | visual_type | 素材/Prompt |
|------|------|------------|-------------|-------------|
{chr(10).join(rows)}

## 降级策略

- Seedance 不可用：`ai_broll` 降级为 fallback concept card。
- GitHub 段：v1 先生成占位卡，后续接入真实滚动片段。
- 当前 `*-video.mp4` 与 `*-mpt-video.mp4` 不受影响。
"""
    path.write_text(content, encoding="utf-8")


def generate(date: str, report_dir: Path) -> tuple[Path, Path]:
    year, month, _ = date.split("-")
    base = report_dir / year / month
    script_path = base / f"{date}-video-script.md"
    if not script_path.exists():
        msg = f"视频脚本不存在: {script_path}"
        raise FileNotFoundError(msg)
    text = script_path.read_text(encoding="utf-8")
    spec = build_spec(date, report_dir, script_path, text)
    storyboard_path = base / f"{date}-hybrid-storyboard.md"
    spec_path = base / f"{date}-hybrid-production-spec.yaml"
    write_storyboard(storyboard_path, spec)
    write_yaml(spec_path, spec)
    return storyboard_path, spec_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()

    storyboard_path, spec_path = generate(args.date, args.report_dir)
    print(f"✅ hybrid storyboard: {storyboard_path}")
    print(f"✅ hybrid spec: {spec_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
