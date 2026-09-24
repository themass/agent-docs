#!/usr/bin/env python3
"""Generate an experimental Content Studio Web Story page.

This renderer is intentionally separate from the stable video pipeline. It
reuses parsing and GitHub screenshot helpers, but writes to its own output
directory and never modifies existing MP4 artifacts.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
CONTENT_STUDIO_DIR = SKILL_DIR.parent
PROFILE_DIR = CONTENT_STUDIO_DIR.parent.parent
VIDEO_PIPELINE_SCRIPTS = CONTENT_STUDIO_DIR / "video-pipeline" / "scripts"
if str(VIDEO_PIPELINE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(VIDEO_PIPELINE_SCRIPTS))

from daily_ranking_chart import parse_daily_overview_table  # noqa: E402
from video_generator import (  # noqa: E402
    VideoRenderError,
    amplify_narration_audio,
    build_media_timeline,
    capture_github_repo_page,
    extract_narration,
    generate_tts,
    get_audio_duration,
    normalize_text_for_tts,
    select_visual_repos,
)


@dataclass
class StoryProject:
    """One project shown on the Web Story page."""

    rank: int | None
    repo: str
    shortName: str
    role: str
    summary: str
    language: str
    starsToday: str
    screenshot: str


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_line(pattern: str, text: str, fallback: str = "") -> str:
    match = re.search(pattern, text)
    if not match:
        return fallback
    return match.group(1).strip()


def _extract_theme(script_text: str) -> dict[str, Any]:
    thesis = _extract_line(r"\*\*一句话 thesis\*\*[:：]\s*(.+)", script_text, "GitHub 热榜正在出现新的开发趋势。")
    tags_line = _extract_line(r"\*\*趋势标签\*\*[:：]\s*(.+)", script_text, "GitHub、AI Agent、开源工具")
    chain_line = _extract_line(r"\*\*叙事链\*\*[:：]\s*(.+)", script_text, "")
    tags = [tag.strip() for tag in re.split(r"[、,，]", tags_line) if tag.strip()][:4]
    chain = [
        re.sub(r"\s*\([^)]*\)", "", part).strip()
        for part in re.split(r"\s*->\s*", chain_line)
        if part.strip()
    ][:3]
    title = "GitHub 热榜"
    if "Agent" in thesis or "agent" in thesis:
        title = "Agent 工程化"
    elif "AI" in thesis:
        title = "AI 工具链"
    return {"title": title, "thesis": thesis.rstrip("。"), "tags": tags, "chain": chain}


def _extract_script_projects(script_text: str) -> dict[str, dict[str, Any]]:
    projects: dict[str, dict[str, Any]] = {}
    pattern = re.compile(
        r"^\d+\.\s+#(?P<rank>\d+)\s+\[(?P<repo>[^\]]+)\]\([^)]+\)\s+—\s+\*\*链上角色\*\*[:：](?P<role>[^。]+)。(?P<summary>.+)$",
        re.MULTILINE,
    )
    for match in pattern.finditer(script_text):
        repo = match.group("repo").strip()
        projects[repo] = {
            "rank": int(match.group("rank")),
            "role": match.group("role").strip(),
            "summary": match.group("summary").strip(),
        }
    return projects


def _overview_by_repo(report_path: Path) -> dict[str, dict[str, str]]:
    rows = parse_daily_overview_table(report_path, limit=25)
    return {
        row.name: {
            "language": "",
            "starsToday": row.stars_today,
            "summary": row.summary,
            "rank": str(row.rank),
        }
        for row in rows
    }


def _timeline_json(script_path: Path) -> list[dict[str, Any]]:
    narration = extract_narration(script_path)
    estimated_seconds = max(72.0, min(150.0, len(narration) / 5.9))
    return [asdict(segment) for segment in build_media_timeline(narration, estimated_seconds)]


def _summary_from_narration(script_path: Path) -> dict[str, Any]:
    narration = extract_narration(script_path)
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", narration) if part.strip()]
    outro = paragraphs[-1] if paragraphs else narration
    sentences = [part.strip() for part in re.split(r"[。！？!?]", outro) if part.strip()]
    bullets = sentences[-3:] if len(sentences) >= 3 else sentences
    if not bullets:
        bullets = ["把热榜项目看成生产链路", "关注工具之间的组合能力", "沉淀可复用的 Agent 工作流"]
    return {
        "oneLine": "基座 + 网关 + 工程增强",
        "bullets": [item[:44] for item in bullets[:3]],
    }


def _render_preview(index_path: Path, preview_path: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        msg = "未安装 playwright，无法生成 Web Story 预览截图"
        raise RuntimeError(msg) from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
            page.goto(index_path.as_uri(), wait_until="networkidle", timeout=60_000)
            page.screenshot(path=str(preview_path), full_page=False, timeout=60_000)
        finally:
            browser.close()


def _scroll_to_section_script() -> str:
    return """
    ({ index, duration }) =>
      new Promise((resolve) => {
        const sections = Array.from(document.querySelectorAll(".story-section"));
        const target = sections[index];
        if (!target) {
          resolve(false);
          return;
        }
        const start = window.scrollY;
        const end = target.offsetTop;
        const diff = end - start;
        const startedAt = performance.now();
        const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
        const step = (now) => {
          const progress = duration <= 0 ? 1 : Math.min((now - startedAt) / duration, 1);
          window.scrollTo(0, start + diff * ease(progress));
          if (progress < 1) {
            requestAnimationFrame(step);
          } else {
            resolve(true);
          }
        };
        requestAnimationFrame(step);
      })
    """


def _record_story_video(
    index_path: Path,
    output_path: Path,
    story_data: dict[str, Any],
    *,
    max_seconds: float,
) -> None:
    """Record the Web Story page as a silent vertical MP4."""
    if shutil.which("ffmpeg") is None:
        msg = "未找到 ffmpeg，无法将 Web Story 录屏转换为 mp4"
        raise RuntimeError(msg)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        msg = "未安装 playwright，无法录制 Web Story 视频"
        raise RuntimeError(msg) from exc

    timeline = story_data.get("timeline")
    if not isinstance(timeline, list) or not timeline:
        section_durations = [6.0] * (len(story_data.get("projects", [])) + 2)
    else:
        section_durations = [
            max(float(segment.get("end", 0)) - float(segment.get("start", 0)), 2.0)
            for segment in timeline
            if isinstance(segment, dict)
        ]
    total = sum(section_durations) or 1.0
    scale = min(1.0, max_seconds / total)
    section_durations = [max(3.2, duration * scale) for duration in section_durations]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1080, "height": 1920},
                device_scale_factor=1,
                record_video_dir=str(tmp),
                record_video_size={"width": 1080, "height": 1920},
            )
            try:
                page = context.new_page()
                page.goto(index_path.as_uri(), wait_until="networkidle", timeout=60_000)
                page.evaluate("() => { document.documentElement.style.scrollBehavior = 'auto'; }")
                page.wait_for_timeout(800)
                section_count = page.locator(".story-section").count()
                for index in range(min(section_count, len(section_durations))):
                    scroll_ms = 0 if index == 0 else 1200
                    page.evaluate(
                        _scroll_to_section_script(),
                        {"index": index, "duration": scroll_ms},
                    )
                    hold_ms = max(int(section_durations[index] * 1000) - scroll_ms, 900)
                    page.wait_for_timeout(hold_ms)
            finally:
                context.close()
                browser.close()

        recorded = next(tmp.glob("*.webm"), None)
        if recorded is None or recorded.stat().st_size == 0:
            msg = "Playwright 未生成 Web Story 录屏文件"
            raise RuntimeError(msg)

        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(recorded),
                "-vf",
                "scale=1080:1920",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            msg = f"ffmpeg 转换 Web Story 录屏失败: {stderr or 'unknown error'}"
            raise RuntimeError(msg)


def _generate_narration_audio(script_path: Path, output_dir: Path) -> Path:
    """Generate narration audio for the experimental Web Story video."""
    audio_dir = output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    narration = extract_narration(script_path)
    tts_text = normalize_text_for_tts(narration)
    raw_audio = audio_dir / "narration.mp3"
    if not generate_tts(tts_text, raw_audio, prefer="auto"):
        msg = "Web Story TTS 生成失败"
        raise RuntimeError(msg)
    boosted = amplify_narration_audio(raw_audio, audio_dir)
    return boosted


def _mux_audio(video_path: Path, audio_path: Path, output_path: Path) -> None:
    """Mux narration audio into the recorded Web Story video."""
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        msg = f"ffmpeg 合成 Web Story 有声视频失败: {stderr or 'unknown error'}"
        raise RuntimeError(msg)


def build_story(
    *,
    date: str,
    report_path: Path,
    script_path: Path,
    output_dir: Path,
    source_limit: int,
    visual_limit: int,
    skip_preview: bool,
    record_video: bool,
    with_audio: bool,
    record_max_seconds: float,
) -> Path:
    """Build a Web Story directory and return the generated `index.html` path."""
    if not report_path.is_file():
        msg = f"日报不存在: {report_path}"
        raise FileNotFoundError(msg)
    if not script_path.is_file():
        msg = f"视频脚本不存在: {script_path}"
        raise FileNotFoundError(msg)

    output_dir.mkdir(parents=True, exist_ok=True)
    github_dir = output_dir / "github"
    github_dir.mkdir(parents=True, exist_ok=True)

    script_text = _read(script_path)
    theme = _extract_theme(script_text)
    script_projects = _extract_script_projects(script_text)
    overview = _overview_by_repo(report_path)
    repos = select_visual_repos(
        script_path,
        report_path,
        source_limit=source_limit,
        visual_limit=visual_limit,
    )
    if not repos:
        msg = "无法从日报和视频脚本中选择 Web Story 项目"
        raise VideoRenderError(msg)

    projects: list[StoryProject] = []
    for index, repo in enumerate(repos):
        screenshot = github_dir / f"{repo.replace('/', '__')}-fullpage.png"
        capture_github_repo_page(repo, screenshot)
        meta = script_projects.get(repo, {})
        report_meta = overview.get(repo, {})
        rank = meta.get("rank")
        if rank is None and report_meta.get("rank"):
            rank = int(report_meta["rank"])
        role = str(meta.get("role") or "趋势项目")
        summary = str(meta.get("summary") or report_meta.get("summary") or "值得跟踪的 GitHub 热榜项目")
        projects.append(
            StoryProject(
                rank=rank if isinstance(rank, int) else index + 1,
                repo=repo,
                shortName=repo.split("/", 1)[-1],
                role=role,
                summary=summary,
                language=report_meta.get("language", "GitHub"),
                starsToday=report_meta.get("starsToday", "-"),
                screenshot=f"./github/{screenshot.name}",
            )
        )

    story_data = {
        "date": date,
        "theme": theme,
        "projects": [asdict(project) for project in projects],
        "timeline": _timeline_json(script_path),
        "summary": _summary_from_narration(script_path),
        "source": {
            "report": str(report_path),
            "script": str(script_path),
            "mode": "web-story-experimental",
        },
    }
    (output_dir / "story-data.json").write_text(
        json.dumps(story_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    template = (SKILL_DIR / "templates" / "index.html").read_text(encoding="utf-8")
    index_html = template.replace("{{TITLE}}", html.escape(f"Content Studio Web Story {date}"))
    story_json = json.dumps(story_data, ensure_ascii=False).replace("</", "<\\/")
    index_html = index_html.replace(
        "{{STORY_DATA}}",
        story_json,
    )
    (output_dir / "index.html").write_text(index_html, encoding="utf-8")
    shutil.copyfile(SKILL_DIR / "templates" / "styles.css", output_dir / "styles.css")

    if not skip_preview:
        _render_preview(output_dir / "index.html", output_dir / "web-story-preview.png")

    narration_audio: Path | None = None
    if with_audio:
        print("🎙️  Web Story TTS 生成旁白…")
        narration_audio = _generate_narration_audio(script_path, output_dir)
        record_max_seconds = max(record_max_seconds, get_audio_duration(narration_audio))

    if record_video:
        silent_video = output_dir / "web-story-video.mp4"
        _record_story_video(
            output_dir / "index.html",
            silent_video,
            story_data,
            max_seconds=record_max_seconds,
        )
        if narration_audio is not None:
            _mux_audio(
                silent_video,
                narration_audio,
                output_dir / "web-story-video-audio.mp4",
            )

    return output_dir / "index.html"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a Content Studio Web Story page.")
    parser.add_argument("date", help="Target date in YYYY-MM-DD format.")
    parser.add_argument("--report-dir", type=Path, default=PROFILE_DIR / "reports")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--source-project-limit", type=int, default=10)
    parser.add_argument("--visual-project-limit", type=int, default=3)
    parser.add_argument("--skip-preview", action="store_true")
    parser.add_argument("--record-video", action="store_true")
    parser.add_argument("--with-audio", action="store_true")
    parser.add_argument("--record-max-seconds", type=float, default=48.0)
    args = parser.parse_args()

    year, month, *_ = args.date.split("-")
    report_path = args.report_dir / year / month / f"{args.date}.md"
    script_path = args.report_dir / year / month / f"{args.date}-video-script.md"
    output_dir = args.output_dir or args.report_dir / year / month / "assets" / f"{args.date}-web-story"

    try:
        index_path = build_story(
            date=args.date,
            report_path=report_path,
            script_path=script_path,
            output_dir=output_dir,
            source_limit=args.source_project_limit,
            visual_limit=args.visual_project_limit,
            skip_preview=args.skip_preview,
            record_video=args.record_video,
            with_audio=args.with_audio,
            record_max_seconds=args.record_max_seconds,
        )
    except Exception as exc:
        print(f"❌ Web Story 生成失败: {exc}", file=sys.stderr)
        return 1

    print(f"✅ Web Story 页面: {index_path}")
    print(f"📦 输出目录: {output_dir}")
    preview = output_dir / "web-story-preview.png"
    if preview.exists():
        print(f"🖼️  预览截图: {preview}")
    video = output_dir / "web-story-video.mp4"
    if video.exists():
        print(f"🎞️  实验视频: {video}")
    audio_video = output_dir / "web-story-video-audio.mp4"
    if audio_video.exists():
        print(f"🔊 有声实验视频: {audio_video}")
    print(f"🌐 打开预览: open {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
