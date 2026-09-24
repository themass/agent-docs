#!/usr/bin/env python3
"""
视频生成器：MoneyPrinterTurbo + 火山引擎 TTS/edge-tts/ffmpeg 降级方案。

用法：
  python3 video_generator.py \\
    --script reports/2026/05/2026-05-30-video-script.md \\
    --output reports/2026/05/2026-05-30-video.mp4 \\
    --engine auto \\         # auto / moneyprinter / fallback
    --tts volcengine         # volcengine / edge-tts（不传则自动探测）

环境变量（火山引擎 TTS）：
  VOLCENGINE_APP_ID     火山引擎语音合成 AppID
  VOLCENGINE_TOKEN      访问 Token
  VOLCENGINE_CLUSTER    合成集群，默认 volcano_tts
  VOLCENGINE_VOICE_TYPE 发音人，默认 zh_female_wanwanxiaohe_moon_bigtts

依赖：
  推荐：MoneyPrinterTurbo 服务运行在 http://localhost:8080
  降级：pip install edge-tts && brew install ffmpeg
  火山 TTS：pip install requests（已内置）
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("PW_TEST_SCREENSHOT_NO_FONTS_READY", "1")

from daily_ranking_chart import (
    enrich_overview_stars,
    generate_daily_ranking_chart,
    merge_script_summaries,
    parse_daily_overview_table,
    report_date_from_path,
)
from project_intro_card import build_project_intro_contexts, generate_project_intro_card


# ---------------------------------------------------------------------------
# 文本提取
# ---------------------------------------------------------------------------

def extract_narration(script_path: Path) -> str:
    """从视频脚本 Markdown 中提取纯口播文本（TTS 直接使用）。"""
    text = script_path.read_text(encoding="utf-8")

    # 先尝试找「完整口播文本」段落
    match = re.search(
        r"## 完整口播文本[^\n]*\n(.*?)(?=\n---|\n##|$)",
        text,
        re.DOTALL,
    )
    if match:
        narration = match.group(1).strip()
        # 去掉 Markdown 格式符号
        narration = re.sub(r"\*+", "", narration)
        narration = re.sub(r"`+", "", narration)
        return sanitize_narration_text(narration)

    # 降级：把整个文件的段落文本拼在一起，去掉 Markdown 符号
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("|") and not stripped.startswith("```") and not stripped.startswith("-"):
            clean = re.sub(r"\*+|`+|#+", "", stripped).strip()
            if clean:
                lines.append(clean)
    return sanitize_narration_text("\n".join(lines[:30]))  # 最多取前 30 行，避免 TTS 超长


def sanitize_narration_text(text: str) -> str:
    """Remove stage-direction lines like ``（开场）`` before TTS and subtitles."""
    cleaned = _STAGE_DIRECTION_LINE.sub("", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


# ---------------------------------------------------------------------------
# 口播文本处理（TTS 读法 / 分段 / 字幕）
# ---------------------------------------------------------------------------

_CN_DIGITS = "零一二三四五六七八九"
_PROJECT_MARKERS = ("第一个", "第二个", "第三个", "第四个", "第五个")
_PROJECT_SPEECH_MARKERS = (
    "第一个是",
    "第二个是",
    "第三个是",
    "第四个是",
    "第五个是",
)
_STAGE_DIRECTION_LINE = re.compile(
    r"^\s*(?:[（(\[]\s*)?"
    r"(?:开场|第一个|第二个|第三个|第四个|第五个|结尾)(?:项目)?"
    r"(?:\s*[）)\]])?\s*$",
    re.MULTILINE,
)
_SECTION_BOUNDARY = re.compile(
    r"(?m)^(第一个是|第二个是|第三个是|第四个是|第五个是)"
)
_PROJECT_INTRO_CARD_MIN_S = 4.0
_PROJECT_INTRO_CARD_MAX_S = 6.5
_PROJECT_INTRO_CARD_RATIO = 0.38
_MOTION_EFFECTS = ("zoom_in", "zoom_out", "pan_up")
_ASS_FONT = "Heiti SC"
# 1080x1920 竖屏：约 4% 屏高，适合手机端快速扫读。
_ASS_FONT_SIZE = 42
_ASS_MARGIN_V = 150
_FRAMES_PER_PROJECT = 3
_GITHUB_SCROLL_WIDTH = 1080
_GITHUB_SCROLL_HEIGHT = 1920
_GITHUB_SCROLL_STEP_RATIO = 0.86
_TTS_CHUNK_MAX_CHARS = 220
_BGM_VOLUME = 0.08
_DEMO_MEDIA_EXTENSIONS = (".gif", ".mp4", ".webm", ".mov")
_DEMO_MEDIA_HINTS = ("demo", "preview", "screenshot", "screen", "showcase", "example", "media")


@dataclass
class TimelineSegment:
    """One narration block with exact start/end times shared by slides and subtitles."""

    kind: str
    text: str
    start: float
    end: float
    project_index: int | None = None


@dataclass
class VisualClip:
    """One rendered visual beat inside a narration block."""

    image: Path
    start: float
    end: float
    effect: str = "pan_up"
    scroll_strip: bool = False


class VideoRenderError(RuntimeError):
    """Raised when github-scroll rendering fails; never fall back to card screenshots."""


def int_to_zh(n: int) -> str:
    """Convert a non-negative integer to spoken Chinese (for TTS)."""
    if n < 0:
        return "负" + int_to_zh(-n)
    if n == 0:
        return "零"
    if n < 10:
        return _CN_DIGITS[n]
    if n < 20:
        tail = int_to_zh(n % 10) if n % 10 else ""
        return "十" + tail
    if n < 100:
        tens, ones = divmod(n, 10)
        tens_part = int_to_zh(tens) + "十"
        return tens_part + (int_to_zh(ones) if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        head = int_to_zh(hundreds) + "百"
        if rest == 0:
            return head
        if rest < 10:
            return head + "零" + int_to_zh(rest)
        return head + int_to_zh(rest)
    if n < 10000:
        thousands, rest = divmod(n, 1000)
        head = int_to_zh(thousands) + "千"
        if rest == 0:
            return head
        if rest < 100:
            return head + "零" + int_to_zh(rest)
        return head + int_to_zh(rest)
    if n < 100000000:
        wan, rest = divmod(n, 10000)
        head = int_to_zh(wan) + "万"
        if rest == 0:
            return head
        if rest < 1000:
            return head + "零" + int_to_zh(rest)
        return head + int_to_zh(rest)
    yi, rest = divmod(n, 100000000)
    head = int_to_zh(yi) + "亿"
    if rest == 0:
        return head
    if rest < 10000000:
        return head + "零" + int_to_zh(rest)
    return head + int_to_zh(rest)


def normalize_text_for_tts(text: str) -> str:
    """Rewrite numbers/percentages so Chinese TTS reads them naturally."""
    normalized = text

    def percent_repl(match: re.Match[str]) -> str:
        raw = match.group(1)
        if "." in raw:
            left, right = raw.split(".", 1)
            spoken = int_to_zh(int(left)) + "点" + "".join(_CN_DIGITS[int(d)] for d in right if d.isdigit())
        else:
            spoken = int_to_zh(int(raw))
        return f"百分之{spoken}"

    normalized = re.sub(r"(\d+(?:\.\d+)?)\s*%", percent_repl, normalized)

    def number_repl(match: re.Match[str]) -> str:
        token = match.group(0)
        if len(token) >= 4 or int(token) >= 100:
            return int_to_zh(int(token))
        return token

    normalized = re.sub(r"\d+", number_repl, normalized)
    return normalized


def split_narration_sections(
    narration: str,
    *,
    split_outro: bool = False,
) -> list[dict[str, object]]:
    """Split narration into intro / per-project / optional outro sections."""
    narration = sanitize_narration_text(narration)
    parts = _SECTION_BOUNDARY.split(narration)
    sections: list[dict[str, object]] = []
    marker_index = {marker: idx for idx, marker in enumerate(_PROJECT_SPEECH_MARKERS)}

    intro = parts[0].strip() if parts else narration.strip()
    if intro:
        sections.append({"kind": "intro", "text": intro, "project_index": None})

    idx = 1
    while idx + 1 < len(parts):
        marker = parts[idx]
        body = parts[idx + 1].strip()
        if marker in marker_index and body:
            project_text = f"{marker}{body}"
            if split_outro and marker == "第五个是":
                project_text, outro = _split_project_outro(project_text)
            else:
                outro = ""
            sections.append(
                {
                    "kind": "project",
                    "text": project_text,
                    "project_index": marker_index[marker],
                }
            )
            if split_outro and outro:
                sections.append({"kind": "outro", "text": outro, "project_index": None})
        idx += 2

    if not any(section["kind"] == "project" for section in sections):
        legacy = re.compile(r"(?m)^(第一个|第二个|第三个)")
        legacy_parts = legacy.split(narration)
        legacy_index = {marker: idx for idx, marker in enumerate(_PROJECT_MARKERS)}
        sections = []
        intro = legacy_parts[0].strip() if legacy_parts else narration.strip()
        if intro:
            sections.append({"kind": "intro", "text": intro, "project_index": None})
        legacy_idx = 1
        while legacy_idx + 1 < len(legacy_parts):
            marker = legacy_parts[legacy_idx]
            body = legacy_parts[legacy_idx + 1].strip()
            if marker in legacy_index and body:
                if not body.startswith(marker):
                    body = f"{marker}，{body}"
                sections.append(
                    {
                        "kind": "project",
                        "text": body,
                        "project_index": legacy_index[marker],
                    }
                )
            legacy_idx += 2
        if not any(section["kind"] == "project" for section in sections):
            sections = _split_analyst_paragraph_sections(narration)
        if not any(section["kind"] == "project" for section in sections):
            sections = [{"kind": "body", "text": narration.strip(), "project_index": None}]
    return sections


def _split_analyst_paragraph_sections(narration: str) -> list[dict[str, object]]:
    """Split analyst-style scripts without explicit "第一个是" markers.

    New GitHub Trend Analyst scripts are written as:
    thesis paragraph -> project 1 -> project 2 -> project 3 -> outro.
    The renderer still needs explicit project segments so each repo gets a
    github-scroll clip.
    """
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", narration)
        if paragraph.strip()
    ]
    if len(paragraphs) < 3:
        return []

    body_paragraphs = paragraphs[1:]
    outro_text = ""
    if len(body_paragraphs) > 5:
        outro_text = body_paragraphs[-1]
        body_paragraphs = body_paragraphs[:-1]
    project_paragraphs = body_paragraphs[:5]

    sections: list[dict[str, object]] = [
        {"kind": "intro", "text": paragraphs[0], "project_index": None}
    ]
    for index, paragraph in enumerate(project_paragraphs):
        sections.append(
            {
                "kind": "project",
                "text": paragraph,
                "project_index": index,
            }
        )
    if outro_text:
        sections.append(
            {
                "kind": "outro",
                "text": outro_text,
                "project_index": None,
            }
        )
    return sections


def _split_project_outro(body: str) -> tuple[str, str]:
    """Split trailing CTA/outro from the last project paragraph when present."""
    match = re.search(r"(这\s*[二三3]\s*个|以上(?:这)?|总结|你最想|评论区)", body)
    if match and match.start() > 24:
        return body[: match.start()].strip(), body[match.start() :].strip()
    return body, ""


def compute_section_durations(
    sections: list[dict[str, object]],
    total_seconds: float,
    *,
    min_section: float = 1.0,
) -> list[tuple[dict[str, object], float]]:
    """Allocate slide time proportionally by spoken text length."""
    if not sections:
        return []
    weights = [max(len(str(section["text"])), 1) for section in sections]
    weight_sum = float(sum(weights))
    raw = [total_seconds * weight / weight_sum for weight in weights]
    return [(section, duration) for section, duration in zip(sections, raw)]


def build_media_timeline(
    narration: str,
    total_seconds: float,
    *,
    timing_text: str | None = None,
) -> list[TimelineSegment]:
    """Build one shared timeline; weights follow TTS text, subtitles use display text."""
    display_sections = split_narration_sections(narration, split_outro=False)
    timing_source = timing_text or narration
    timing_sections = split_narration_sections(timing_source, split_outro=False)
    if len(timing_sections) != len(display_sections):
        timing_sections = display_sections

    weights = [max(len(str(section["text"])), 1) for section in timing_sections]
    weight_sum = float(sum(weights))
    timeline: list[TimelineSegment] = []
    cursor = 0.0
    for display_section, timing_section in zip(display_sections, timing_sections):
        weight = max(len(str(timing_section["text"])), 1)
        duration = total_seconds * weight / weight_sum
        project_index = display_section.get("project_index")
        timeline.append(
            TimelineSegment(
                kind=str(display_section["kind"]),
                text=str(display_section["text"]).strip(),
                start=cursor,
                end=cursor + duration,
                project_index=project_index if isinstance(project_index, int) else None,
            )
        )
        cursor += duration
    if timeline:
        timeline[-1].end = total_seconds
    return timeline


def expand_timeline_to_visual_clips(
    timeline: list[TimelineSegment],
    repos: list[str],
    assets: dict[str, list[Path]],
    *,
    intro_image: Path | None = None,
) -> list[VisualClip]:
    """Expand each narration block into multiple images or one scroll strip."""
    clips: list[VisualClip] = []
    for segment in timeline:
        duration = max(segment.end - segment.start, 0.5)
        repo_images: list[Path] = []
        scroll_strip: Path | None = None
        if segment.kind == "project" and segment.project_index is not None:
            if 0 <= segment.project_index < len(repos):
                repo_images = assets.get(repos[segment.project_index], [])
                scroll_strip = next(
                    (path for path in repo_images if path.name.endswith("-scroll.png")),
                    None,
                )
        elif repos:
            repo_images = assets.get(repos[0], [])

        if segment.kind == "intro" and intro_image is not None and intro_image.exists():
            clips.append(
                VisualClip(
                    image=intro_image,
                    start=segment.start,
                    end=segment.end,
                    effect="zoom_in",
                )
            )
            continue

        stills = [path for path in repo_images if not path.name.endswith("-scroll.png")]
        if not stills and repo_images:
            stills = repo_images[:1]
        if not stills:
            continue

        if segment.kind == "project" and len(stills) >= 2:
            frames = stills[: max(_FRAMES_PER_PROJECT, 2)]
            per_clip = duration / len(frames)
            cursor = segment.start
            for index, image in enumerate(frames):
                clip_end = segment.end if index == len(frames) - 1 else cursor + per_clip
                clips.append(
                    VisualClip(
                        image=image,
                        start=cursor,
                        end=clip_end,
                        effect=_MOTION_EFFECTS[index % len(_MOTION_EFFECTS)],
                    )
                )
                cursor = clip_end
            continue

        if segment.kind == "project" and scroll_strip and scroll_strip.exists():
            clips.append(
                VisualClip(
                    image=scroll_strip,
                    start=segment.start,
                    end=segment.end,
                    effect="scroll_down",
                    scroll_strip=True,
                )
            )
            continue

        if segment.kind in {"intro", "outro"} or len(stills) == 1:
            clips.append(
                VisualClip(
                    image=stills[0],
                    start=segment.start,
                    end=segment.end,
                    effect=_MOTION_EFFECTS[len(clips) % len(_MOTION_EFFECTS)],
                )
            )
            continue

        per_clip = duration / len(stills)
        cursor = segment.start
        for index, image in enumerate(stills):
            clip_end = segment.end if index == len(stills) - 1 else cursor + per_clip
            clips.append(
                VisualClip(
                    image=image,
                    start=cursor,
                    end=clip_end,
                    effect=_MOTION_EFFECTS[index % len(_MOTION_EFFECTS)],
                )
            )
            cursor = clip_end
    return clips


def _subtitle_chunks(text: str, max_len: int = 14) -> list[str]:
    """Break long narration into short bottom-subtitle lines."""
    sentences = re.split(r"(?<=[。！？!?])", text)
    chunks: list[str] = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) <= max_len:
            chunks.append(sentence)
            continue
        parts = re.split(r"(?<=[，,、；;])", sentence)
        buffer = ""
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if len(buffer) + len(part) <= max_len:
                buffer += part
            else:
                if buffer:
                    chunks.append(buffer)
                buffer = part
        if buffer:
            chunks.append(buffer)
    return chunks


def _escape_ffmpeg_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _seconds_to_ass(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def generate_ass_subtitles(timeline: list[TimelineSegment], dest: Path) -> Path:
    """Generate ASS subtitles using the same timeline as slide changes."""
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{_ASS_FONT},{_ASS_FONT_SIZE},&H00000000,&H000000FF,&H00000000,"
        f"&H00000000,1,0,0,0,100,100,0,0,1,0,0,2,48,48,{_ASS_MARGIN_V},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for segment in timeline:
        if not segment.text:
            continue
        segment_duration = max(segment.end - segment.start, 0.1)
        chunks = _subtitle_chunks(segment.text)
        if not chunks:
            continue
        weights = [max(len(chunk), 1) for chunk in chunks]
        weight_sum = float(sum(weights))
        cursor = segment.start
        for index, chunk in enumerate(chunks):
            chunk_duration = segment_duration * weights[index] / weight_sum
            chunk_end = segment.end if index == len(chunks) - 1 else cursor + chunk_duration
            lines.append(
                f"Dialogue: 0,{_seconds_to_ass(cursor)},{_seconds_to_ass(chunk_end)},"
                f"Default,,0,0,0,,{chunk.replace(',', '，')}"
            )
            cursor = chunk_end

    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# TTS — provider fallback chain
# ---------------------------------------------------------------------------

_VOLCENGINE_API_URL = "https://openspeech.bytedance.com/api/v1/tts"
_LIB_DIR = Path(__file__).resolve().parents[2] / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))
from profile_paths import find_profile_dir  # noqa: E402

_PROFILE_DIR = find_profile_dir(start=Path(__file__))
_PROFILE_HOME = _PROFILE_DIR / "home"
_PLACEHOLDER_AUDIO = _PROFILE_DIR / "audio_cache" / "github-video-placeholder.mp3"


def _ensure_playwright_home() -> None:
    """Point Playwright browser cache at the Hermes profile home directory."""
    if _PROFILE_HOME.is_dir():
        os.environ["HOME"] = str(_PROFILE_HOME)
_DEFAULT_TTS_CONFIG = _PROFILE_DIR / "config" / "tts-providers.yaml"
_TTS_PLACEHOLDER_PREFIXES = ("YOUR_", "your-", "填入", "替换")


def _read_str(config: dict[str, object], key: str, default: str = "") -> str:
    value = config.get(key)
    if value is None:
        return default
    return str(value).strip()


def _read_float(config: dict[str, object], key: str, default: float) -> float:
    value = config.get(key)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_int(config: dict[str, object], key: str, default: int) -> int:
    value = config.get(key)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _looks_like_placeholder(value: str) -> bool:
    text = value.strip()
    return not text or any(text.startswith(prefix) for prefix in _TTS_PLACEHOLDER_PREFIXES)


def _tts_config_path() -> Path:
    configured = os.environ.get("CONTENT_STUDIO_TTS_CONFIG", "").strip()
    return Path(configured).expanduser() if configured else _DEFAULT_TTS_CONFIG


def load_tts_config() -> tuple[list[str], dict[str, dict[str, object]]]:
    """Load private TTS provider config.

    The expected shape matches `config/tts-providers.example.yaml`:
    `enabled` controls fallback order; `ttsEngConfig` stores provider details.
    Missing config is normal and simply disables configured providers.
    """
    path = _tts_config_path()
    if not path.exists() or path.stat().st_size == 0:
        return [], {}
    try:
        import yaml  # type: ignore[import-not-found]  # noqa: PLC0415
    except ImportError:
        print(
            f"⚠️  找到 TTS 配置但缺少 PyYAML，跳过: {path}",
            file=sys.stderr,
        )
        return [], {}

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError) as exc:
        print(f"⚠️  TTS 配置读取失败: {path}: {exc}", file=sys.stderr)
        return [], {}

    if not isinstance(data, dict):
        return [], {}
    raw_providers = data.get("ttsEngConfig")
    providers: dict[str, dict[str, object]] = {}
    if isinstance(raw_providers, dict):
        for name, value in raw_providers.items():
            if isinstance(value, dict):
                providers[str(name)] = value

    raw_enabled = data.get("enabled")
    if isinstance(raw_enabled, list):
        enabled = [str(item) for item in raw_enabled if str(item).strip()]
    else:
        enabled = list(providers)
    return enabled, providers


def has_configured_tts_provider() -> bool:
    """Return whether private config appears to contain at least one real key."""
    enabled, providers = load_tts_config()
    for name in enabled:
        if name == "edge-tts":
            return True
        config = providers.get(name)
        if not config:
            continue
        supplier = _read_str(config, "supplier").lower()
        if supplier == "bytedancettsservice" or supplier == "bytettservice":
            token = _read_str(config, "token")
            appid = _read_str(config, "appid")
            if not _looks_like_placeholder(token) and not _looks_like_placeholder(appid):
                return True
        elif supplier == "minimaxttsservice":
            appid = _read_str(config, "appid")
            if not _looks_like_placeholder(appid):
                return True
        elif supplier == "alittsservice":
            token = _read_str(config, "token") or _read_str(config, "nls_token")
            access_key = _read_str(config, "access_key")
            access_key_secret = _read_str(config, "access_key_secret")
            if not _looks_like_placeholder(token):
                return True
            if not _looks_like_placeholder(access_key) and not _looks_like_placeholder(access_key_secret):
                return True
    return False


def _write_audio_bytes(data: bytes, output_path: Path, label: str) -> bool:
    if not data:
        print(f"❌ {label} 返回空音频", file=sys.stderr)
        return False
    output_path.write_bytes(data)
    print(f"✅ {label} 生成: {output_path} ({output_path.stat().st_size // 1024} KB)")
    return output_path.exists() and output_path.stat().st_size > 0

def tts_volcengine(text: str, output_mp3: Path) -> bool:
    """调用火山引擎语音合成 API 生成 mp3。

    需要环境变量：VOLCENGINE_APP_ID、VOLCENGINE_TOKEN。
    可选：VOLCENGINE_CLUSTER（默认 volcano_tts）、VOLCENGINE_VOICE_TYPE。
    """
    import urllib.request  # noqa: PLC0415

    app_id = os.environ.get("VOLCENGINE_APP_ID", "")
    token = os.environ.get("VOLCENGINE_TOKEN", "")
    if not app_id or not token:
        print("⚠️  未设置 VOLCENGINE_APP_ID / VOLCENGINE_TOKEN，跳过火山引擎 TTS", file=sys.stderr)
        return False

    cluster = os.environ.get("VOLCENGINE_CLUSTER", "volcano_tts")
    voice_type = os.environ.get("VOLCENGINE_VOICE_TYPE", "zh_female_wanwanxiaohe_moon_bigtts")

    payload = {
        "app": {
            "appid": app_id,
            "token": token,
            "cluster": cluster,
        },
        "user": {"uid": "content-studio"},
        "audio": {
            "voice_type": voice_type,
            "encoding": "mp3",
            "speed_ratio": 1.1,       # 语速略快，适合短视频
            "volume_ratio": 1.0,
            "pitch_ratio": 1.0,
        },
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": text,
            "text_type": "plain",
            "operation": "query",
            "with_frontend": 1,
            "frontend_type": "unitTson",
        },
    }

    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            _VOLCENGINE_API_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer;{token}",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())

        if body.get("code") != 3000:
            print(f"❌ 火山引擎 TTS 错误: code={body.get('code')}, msg={body.get('message')}", file=sys.stderr)
            return False

        audio_b64 = body.get("data", "")
        if not audio_b64:
            print("❌ 火山引擎 TTS 返回空 data", file=sys.stderr)
            return False

        output_mp3.write_bytes(base64.b64decode(audio_b64))
        print(f"✅ 火山引擎 TTS 生成: {output_mp3} ({output_mp3.stat().st_size // 1024} KB)")
        return True

    except OSError as exc:
        print(f"⚠️  火山引擎 TTS 网络错误: {exc}", file=sys.stderr)
        return False


def tts_bytedance_config(text: str, output_audio: Path, config: dict[str, object], name: str) -> bool:
    """Call ByteDance/Volcengine TTS using one provider entry from config."""
    app_id = _read_str(config, "appid")
    token = _read_str(config, "token")
    if _looks_like_placeholder(app_id) or _looks_like_placeholder(token):
        print(f"⚠️  {name} 缺少 appid/token，跳过", file=sys.stderr)
        return False

    base_url = _read_str(config, "url", "https://openspeech.bytedance.com").rstrip("/")
    api_url = base_url if base_url.endswith("/api/v1/tts") else f"{base_url}/api/v1/tts"
    encoding = _read_str(config, "encoding", "wav") or "wav"
    payload = {
        "app": {
            "appid": app_id,
            "token": token,
            "cluster": _read_str(config, "cluster", "volcano_tts"),
        },
        "user": {"uid": _read_str(config, "uid", "content-studio")},
        "audio": {
            "voice_type": _read_str(config, "voice_type", "zh_female_wanwanxiaohe_moon_bigtts"),
            "encoding": encoding,
            "speed_ratio": _read_float(config, "speed_ratio", 1.0),
            "volume_ratio": _read_float(config, "volume_ratio", 1.0),
            "pitch_ratio": _read_float(config, "pitch_ratio", 1.0),
            "sample_rate": _read_int(config, "sample_rate", 24000),
        },
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": text,
            "text_type": _read_str(config, "text_type", "plain"),
            "operation": "query",
            "with_frontend": 1,
            "frontend_type": "unitTson",
        },
    }
    emotion = _read_str(config, "emotion")
    if emotion:
        payload["audio"]["emotion"] = emotion

    try:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer;{token}",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
    except (OSError, ValueError) as exc:
        print(f"⚠️  {name} 网络/解析错误: {exc}", file=sys.stderr)
        return False

    if body.get("code") != 3000:
        print(
            f"❌ {name} 错误: code={body.get('code')}, msg={body.get('message')}",
            file=sys.stderr,
        )
        return False

    audio = body.get("data")
    if isinstance(audio, dict):
        audio = audio.get("audio") or audio.get("data")
    if not isinstance(audio, str) or not audio:
        print(f"❌ {name} 返回空 data", file=sys.stderr)
        return False
    try:
        return _write_audio_bytes(base64.b64decode(audio), output_audio, name)
    except ValueError as exc:
        print(f"❌ {name} 音频 base64 解码失败: {exc}", file=sys.stderr)
        return False


def _percent_encode(value: str) -> str:
    return urllib.parse.quote(value, safe="-_.~")


def _ali_create_token(config: dict[str, object]) -> str:
    access_key = _read_str(config, "access_key")
    access_key_secret = _read_str(config, "access_key_secret")
    if _looks_like_placeholder(access_key) or _looks_like_placeholder(access_key_secret):
        return ""

    params = {
        "AccessKeyId": access_key,
        "Action": "CreateToken",
        "Format": "JSON",
        "RegionId": "cn-shanghai",
        "SignatureMethod": "HMAC-SHA1",
        "SignatureNonce": str(uuid.uuid4()),
        "SignatureVersion": "1.0",
        "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "Version": "2019-02-28",
    }
    canonical = "&".join(
        f"{_percent_encode(key)}={_percent_encode(params[key])}"
        for key in sorted(params)
    )
    string_to_sign = f"GET&%2F&{_percent_encode(canonical)}"
    digest = hmac.new(
        (access_key_secret + "&").encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    params["Signature"] = base64.b64encode(digest).decode("ascii")
    query = urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(
            f"https://nls-meta.cn-shanghai.aliyuncs.com/?{query}",
            timeout=30,
        ) as resp:
            body = json.loads(resp.read())
    except (OSError, ValueError) as exc:
        print(f"⚠️  阿里 TTS token 获取失败: {exc}", file=sys.stderr)
        return ""
    token = body.get("Token", {}).get("Id") if isinstance(body.get("Token"), dict) else ""
    return token if isinstance(token, str) else ""


def tts_ali_config(text: str, output_audio: Path, config: dict[str, object], name: str) -> bool:
    """Call Aliyun NLS stream TTS using an Ali provider config."""
    appkey = _read_str(config, "appid")
    if _looks_like_placeholder(appkey):
        print(f"⚠️  {name} 缺少 appid/appkey，跳过", file=sys.stderr)
        return False
    token = _read_str(config, "token") or _read_str(config, "nls_token") or _ali_create_token(config)
    if _looks_like_placeholder(token):
        print(f"⚠️  {name} 缺少可用 NLS token，跳过", file=sys.stderr)
        return False

    text_type = _read_str(config, "text_type", "plain")
    request_text = text
    if text_type == "ssml" and "<speak" not in request_text:
        request_text = f"<speak>{html.escape(text)}</speak>"

    speed_ratio = _read_float(config, "speed_ratio", 1.0)
    speech_rate = max(-500, min(500, int((speed_ratio - 1.0) * 500)))
    params = {
        "appkey": appkey,
        "token": token,
        "text": request_text,
        "format": _read_str(config, "encoding", "wav") or "wav",
        "sample_rate": str(_read_int(config, "sample_rate", 16000)),
        "voice": _read_str(config, "voice_type") or _read_str(config, "uid", "betty"),
        "volume": str(_read_int(config, "volume_ratio", 50)),
        "speech_rate": str(speech_rate),
    }
    url = _read_str(config, "url", "https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/tts")
    try:
        with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(params)}", timeout=60) as resp:
            content = resp.read()
            content_type = resp.headers.get("Content-Type", "")
    except OSError as exc:
        print(f"⚠️  {name} 网络错误: {exc}", file=sys.stderr)
        return False
    if "application/json" in content_type:
        print(f"❌ {name} 返回错误: {content.decode('utf-8', errors='replace')[:300]}", file=sys.stderr)
        return False
    return _write_audio_bytes(content, output_audio, name)


def _decode_minimax_audio(value: str) -> bytes:
    stripped = value.strip()
    if re.fullmatch(r"[0-9a-fA-F]+", stripped) and len(stripped) % 2 == 0:
        return bytes.fromhex(stripped)
    return base64.b64decode(stripped)


def tts_minimax_config(text: str, output_audio: Path, config: dict[str, object], name: str) -> bool:
    """Call Minimax t2a_v2 using one provider config."""
    auth = _read_str(config, "appid")
    if _looks_like_placeholder(auth):
        print(f"⚠️  {name} 缺少 appid/Bearer token，跳过", file=sys.stderr)
        return False
    if not auth.lower().startswith("bearer "):
        auth = f"Bearer {auth}"

    encoding = _read_str(config, "encoding", "wav") or "wav"
    payload = {
        "model": _read_str(config, "voice_type", "speech-02-hd"),
        "text": text,
        "stream": False,
        "voice_setting": {
            "voice_id": _read_str(config, "uid", "male-qn-qingse"),
            "speed": _read_float(config, "speed_ratio", 1.0),
            "vol": _read_float(config, "volume_ratio", 1.0),
            "pitch": _read_int(config, "pitch", 0),
        },
        "audio_setting": {
            "sample_rate": _read_int(config, "sample_rate", 16000),
            "bitrate": _read_int(config, "bitrate", 128000),
            "format": encoding,
            "channel": _read_int(config, "channel", 1),
        },
    }
    try:
        req = urllib.request.Request(
            _read_str(config, "url"),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": auth,
            },
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read())
    except (OSError, ValueError) as exc:
        print(f"⚠️  {name} 网络/解析错误: {exc}", file=sys.stderr)
        return False

    base_resp = body.get("base_resp")
    if isinstance(base_resp, dict) and base_resp.get("status_code") not in (0, "0", None):
        print(f"❌ {name} 错误: {base_resp}", file=sys.stderr)
        return False
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    audio_value = data.get("audio") or data.get("audio_file") or body.get("audio")
    if not isinstance(audio_value, str) or not audio_value:
        print(f"❌ {name} 未返回 audio", file=sys.stderr)
        return False
    try:
        return _write_audio_bytes(_decode_minimax_audio(audio_value), output_audio, name)
    except ValueError as exc:
        print(f"❌ {name} 音频解码失败: {exc}", file=sys.stderr)
        return False


def tts_edge(text: str, output_mp3: Path) -> bool:
    """edge-tts 降级方案（免费，质量稍低）。"""
    result = subprocess.run(
        [
            sys.executable, "-m", "edge_tts",
            "--voice", "zh-CN-XiaoxiaoNeural",
            "--text", text,
            "--write-media", str(output_mp3),
        ],
        capture_output=True,
    )
    if result.returncode == 0:
        print(f"✅ edge-tts 生成: {output_mp3}")
        return True
    print(f"❌ edge-tts 失败: {result.stderr.decode()[:200]}", file=sys.stderr)
    return False


def _run_configured_provider(
    name: str,
    text: str,
    output_audio: Path,
    providers: dict[str, dict[str, object]],
) -> bool:
    if name == "edge-tts":
        return tts_edge(text, output_audio)
    config = providers.get(name)
    if not config:
        print(f"⚠️  TTS provider 未找到: {name}", file=sys.stderr)
        return False
    supplier = _read_str(config, "supplier").lower()
    if supplier == "bytedancettsservice" or supplier == "bytettservice":
        return tts_bytedance_config(text, output_audio, config, name)
    if supplier == "alittsservice":
        return tts_ali_config(text, output_audio, config, name)
    if supplier == "minimaxttsservice":
        return tts_minimax_config(text, output_audio, config, name)
    print(f"⚠️  不支持的 TTS supplier: {name} ({supplier})", file=sys.stderr)
    return False


def split_tts_text(text: str, max_chars: int = _TTS_CHUNK_MAX_CHARS) -> list[str]:
    """Split long TTS text into provider-safe chunks without losing punctuation."""
    normalized = text.strip()
    if not normalized:
        return []
    if len(normalized) <= max_chars:
        return [normalized]

    pieces = [
        piece
        for piece in re.split(r"(?<=[。！？!?])|(?<=\n)", normalized)
        if piece.strip()
    ]
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        if len(piece) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_tts_piece(piece, max_chars))
            continue
        if current and len(current) + len(piece) + 1 > max_chars:
            chunks.append(current)
            current = piece
        else:
            current = f"{current}\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks


def _split_long_tts_piece(piece: str, max_chars: int) -> list[str]:
    """Split one overlong sentence at softer punctuation before hard slicing."""
    parts = [part for part in re.split(r"(?<=[，,、；;])", piece) if part.strip()]
    chunks: list[str] = []
    current = ""
    for part in parts:
        part = part.strip()
        if len(part) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(part[index : index + max_chars] for index in range(0, len(part), max_chars))
            continue
        if current and len(current) + len(part) > max_chars:
            chunks.append(current)
            current = part
        else:
            current += part
    if current:
        chunks.append(current)
    return chunks


def _concat_audio_files(chunks: list[Path], output_audio: Path) -> bool:
    """Concatenate TTS chunks into one audio file using ffmpeg."""
    if not chunks:
        return False
    if len(chunks) == 1:
        shutil.copyfile(chunks[0], output_audio)
        return output_audio.exists() and output_audio.stat().st_size > 0
    with tempfile.TemporaryDirectory() as tmpdir:
        concat_file = Path(tmpdir) / "audio-concat.txt"
        concat_file.write_text(
            "\n".join(f"file '{chunk}'" for chunk in chunks),
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c:a",
                "libmp3lame",
                "-b:a",
                "192k",
                str(output_audio),
            ],
            capture_output=True,
        )
    return result.returncode == 0 and output_audio.exists() and output_audio.stat().st_size > 0


def _background_music_path() -> Path | None:
    """Return an optional user-provided background music file."""
    if os.environ.get("CONTENT_STUDIO_DISABLE_BGM") == "1":
        return None
    configured = os.environ.get("CONTENT_STUDIO_BGM_FILE", "").strip()
    if not configured:
        return None
    path = Path(configured).expanduser()
    if path.exists() and path.stat().st_size > 0:
        return path
    print(f"⚠️  背景音乐文件不存在，跳过: {path}", file=sys.stderr)
    return None


def mix_optional_background_music(narration_audio: Path, duration: float, dest: Path) -> Path:
    """Mix low-volume background music under narration when configured."""
    bgm = _background_music_path()
    if bgm is None:
        return narration_audio
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(narration_audio),
            "-stream_loop",
            "-1",
            "-i",
            str(bgm),
            "-filter_complex",
            (
                f"[1:a]volume={_BGM_VOLUME:.3f},"
                f"atrim=0:{duration:.3f},asetpts=N/SR/TB[bgm];"
                "[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[a]"
            ),
            "-map",
            "[a]",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(dest),
        ],
        capture_output=True,
    )
    if result.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
        print(f"🎵 已混入背景音乐: {bgm} (volume={_BGM_VOLUME:.2f})")
        return dest
    print(f"⚠️  背景音乐混音失败，继续使用纯口播: {bgm}", file=sys.stderr)
    return narration_audio


def _generate_tts_chunks(
    chunks: list[str],
    output_audio: Path,
    label: str,
    runner,
) -> bool:
    """Generate all chunks with one provider, then concatenate them."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        audio_chunks: list[Path] = []
        for index, chunk in enumerate(chunks, 1):
            chunk_path = tmp / f"tts-{index:02d}.mp3"
            print(f"🎙️  {label} 分段 {index}/{len(chunks)} ({len(chunk)} 字)")
            if not runner(chunk, chunk_path):
                return False
            audio_chunks.append(chunk_path)
        if not _concat_audio_files(audio_chunks, output_audio):
            print(f"❌ {label} 分段音频拼接失败", file=sys.stderr)
            return False
    print(
        f"✅ {label} 分段合成完成: {output_audio} "
        f"({output_audio.stat().st_size // 1024} KB, {get_audio_duration(output_audio):.1f}s)"
    )
    return True


def generate_tts(text: str, output_mp3: Path, prefer: str = "auto") -> bool:
    """按优先级调用 TTS，返回是否成功。

    prefer: provider name / 'volcengine' / 'edge-tts' / 'auto'
    auto 逻辑：私有配置 provider 顺序 → 旧 VOLCENGINE_* env → edge-tts。
    """
    enabled, providers = load_tts_config()
    chunks = split_tts_text(text)
    if len(chunks) > 1:
        print(
            f"🎙️  TTS 文本 {len(text)} 字，按 {len(chunks)} 段合成，"
            "避免长文本被服务端截断"
        )
        if prefer != "auto" and prefer not in {"volcengine", "edge-tts"}:
            return _generate_tts_chunks(
                chunks,
                output_mp3,
                prefer,
                lambda chunk, path: _run_configured_provider(prefer, chunk, path, providers),
            )
        if prefer == "volcengine":
            return _generate_tts_chunks(chunks, output_mp3, "火山引擎 TTS", tts_volcengine)
        if prefer == "edge-tts":
            return _generate_tts_chunks(chunks, output_mp3, "edge-tts", tts_edge)
        for name in enabled:
            print(f"🎙️  尝试 TTS provider: {name}")
            if _generate_tts_chunks(
                chunks,
                output_mp3,
                name,
                lambda chunk, path, provider_name=name: _run_configured_provider(
                    provider_name,
                    chunk,
                    path,
                    providers,
                ),
            ):
                return True
            print(f"↩  TTS provider 分段失败，切换下一个: {name}")
        if os.environ.get("VOLCENGINE_APP_ID") and os.environ.get("VOLCENGINE_TOKEN"):
            if _generate_tts_chunks(chunks, output_mp3, "火山引擎 TTS", tts_volcengine):
                return True
            print("↩  火山引擎 TTS 分段失败，降级到 edge-tts")
        return _generate_tts_chunks(chunks, output_mp3, "edge-tts", tts_edge)

    if prefer != "auto" and prefer not in {"volcengine", "edge-tts"}:
        return _run_configured_provider(prefer, text, output_mp3, providers)
    if prefer == "volcengine":
        return tts_volcengine(text, output_mp3)
    if prefer == "edge-tts":
        return tts_edge(text, output_mp3)
    # auto
    for name in enabled:
        print(f"🎙️  尝试 TTS provider: {name}")
        if _run_configured_provider(name, text, output_mp3, providers):
            return True
        print(f"↩  TTS provider 失败，切换下一个: {name}")
    if os.environ.get("VOLCENGINE_APP_ID") and os.environ.get("VOLCENGINE_TOKEN"):
        if tts_volcengine(text, output_mp3):
            return True
        print("↩  火山引擎 TTS 失败，降级到 edge-tts")
    return tts_edge(text, output_mp3)


def should_use_placeholder_audio() -> bool:
    """Return whether placeholder audio should replace TTS for MVP validation."""
    if os.environ.get("CONTENT_STUDIO_FORCE_PLACEHOLDER_AUDIO") == "1":
        return _PLACEHOLDER_AUDIO.exists()
    if os.environ.get("CONTENT_STUDIO_DISABLE_PLACEHOLDER_AUDIO") == "1":
        return False
    if has_configured_tts_provider():
        return False
    if os.environ.get("VOLCENGINE_APP_ID") and os.environ.get("VOLCENGINE_TOKEN"):
        return False
    return _PLACEHOLDER_AUDIO.exists()


def generate_srt(text: str, audio_path: Path) -> Path:
    """Backward-compatible wrapper that writes ASS subtitles on the shared timeline."""
    total_seconds = get_audio_duration(audio_path)
    timeline = build_media_timeline(
        text,
        total_seconds,
        timing_text=normalize_text_for_tts(text),
    )
    return generate_ass_subtitles(timeline, audio_path.with_suffix(".ass"))


def _seconds_to_srt(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    ms = int((s % 1) * 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def extract_cover_frame(video_path: Path, output_path: Path) -> bool:
    """从视频第 1 秒提取封面截图。"""
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", "1",
            "-i", str(video_path),
            "-frames:v", "1",
            "-q:v", "2",
            str(output_path),
        ],
        capture_output=True,
    )
    if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
        return True
    if output_path.exists() and output_path.stat().st_size == 0:
        output_path.unlink()
    return False


# ---------------------------------------------------------------------------
# 方案 A：MoneyPrinterTurbo
# ---------------------------------------------------------------------------

def generate_with_moneyprinter(narration: str, output_path: Path, base_url: str = "http://localhost:8080") -> bool:
    """调用 MoneyPrinterTurbo HTTP API 生成视频。"""
    try:
        import urllib.request  # noqa: PLC0415 # stdlib only, no heavy imports at module level

        payload = json.dumps({
            "video_subject": narration[:200],  # 作为主题关键词
            "video_script": narration,          # 完整口播文本
            "video_language": "zh-CN",
            "voice_name": "zh-CN-XiaoxiaoNeural",
            "voice_rate": 1.0,
            "bgm_type": "random",
            "bgm_volume": 0.1,
            "subtitle_enabled": True,
            "subtitle_position": "bottom",
            "font_size": 40,
            "n_threads": 2,
        }).encode()

        req = urllib.request.Request(
            f"{base_url}/api/v1/video",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = json.loads(resp.read())

        task_id = body.get("task_id") or body.get("id")
        if not task_id:
            print(f"❌ MoneyPrinterTurbo 未返回 task_id: {body}", file=sys.stderr)
            return False

        # 轮询任务状态
        print(f"⏳ MoneyPrinterTurbo 任务 {task_id} 已提交，等待生成（最多 10 分钟）…")
        deadline = time.time() + 600
        while time.time() < deadline:
            time.sleep(10)
            status_req = urllib.request.Request(f"{base_url}/api/v1/video/{task_id}")
            with urllib.request.urlopen(status_req, timeout=30) as sresp:
                status = json.loads(sresp.read())
            state = status.get("state") or status.get("status", "")
            print(f"  状态: {state}")
            if state in ("completed", "success", "done"):
                video_url = status.get("video_url") or status.get("output_url")
                if video_url:
                    _download_file(f"{base_url}{video_url}", output_path)
                    return output_path.exists() and output_path.stat().st_size > 0
                # 有些版本直接把文件放在本地目录
                local = status.get("video_path")
                if local and Path(local).exists():
                    Path(local).rename(output_path)
                    return output_path.exists() and output_path.stat().st_size > 0
            if state in ("failed", "error"):
                print(f"❌ MoneyPrinterTurbo 任务失败: {status}", file=sys.stderr)
                return False

        print("❌ MoneyPrinterTurbo 超时（10 分钟）", file=sys.stderr)
        return False

    except OSError as exc:
        print(f"⚠️  MoneyPrinterTurbo 不可用 ({exc})，改用 TTS + GitHub 页面滚动", file=sys.stderr)
        return False


def _download_file(
    url: str,
    dest: Path,
    *,
    retries: int = 4,
    min_bytes: int = 1024,
    timeout: int = 120,
) -> None:
    """Download a URL to disk with retries (handles IncompleteRead from OG CDN)."""
    import time
    import urllib.error
    import urllib.request
    from http.client import IncompleteRead

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; content-studio-video/1.0)",
        "Accept": "image/png,image/*,*/*",
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                chunks: list[bytes] = []
                while True:
                    try:
                        block = resp.read(64 * 1024)
                    except IncompleteRead as partial_exc:
                        partial = getattr(partial_exc, "partial", None) or partial_exc.args[0]
                        if partial:
                            chunks.append(partial)
                        if len(b"".join(chunks)) >= min_bytes:
                            break
                        raise
                    if not block:
                        break
                    chunks.append(block)
            data = b"".join(chunks)
            if len(data) < min_bytes:
                msg = f"response too small ({len(data)} bytes)"
                raise OSError(msg)
            dest.write_bytes(data)
            return
        except (OSError, urllib.error.URLError, IncompleteRead, TimeoutError, ValueError) as exc:
            last_error = exc
            if dest.exists():
                dest.unlink(missing_ok=True)
            if attempt < retries:
                wait = min(2**attempt, 8)
                print(
                    f"⚠️  下载重试 {attempt}/{retries} ({wait}s): {url} — {exc}",
                    file=sys.stderr,
                )
                time.sleep(wait)
    msg = f"download failed after {retries} attempts: {url}"
    raise OSError(msg) from last_error


def amplify_narration_audio(audio_path: Path, work_dir: Path) -> Path:
    """Boost narration loudness before mux (default near-max with limiter)."""
    if os.environ.get("CONTENT_STUDIO_DISABLE_AUDIO_BOOST", "0") == "1":
        return audio_path

    try:
        volume = float(os.environ.get("CONTENT_STUDIO_NARRATION_VOLUME", "8.0"))
    except ValueError:
        volume = 8.0
    volume = max(1.0, min(volume, 20.0))

    boosted = work_dir / "narration-boosted.m4a"
    af = f"volume={volume:.2f},alimiter=limit=0.99:level_out=0.99"
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(audio_path),
            "-af",
            af,
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(boosted),
        ],
        capture_output=True,
    )
    if result.returncode == 0 and boosted.exists() and boosted.stat().st_size > 0:
        print(f"🔊 旁白音量已提升 (volume={volume:.1f})")
        return boosted
    print("⚠️  旁白音量提升失败，使用原音频", file=sys.stderr)
    return audio_path


# ---------------------------------------------------------------------------
# GitHub 项目素材
# ---------------------------------------------------------------------------

def extract_github_repos(text: str, limit: int = 3) -> list[str]:
    """Extract GitHub repositories from Markdown links or plain URLs."""
    repos: list[str] = []
    pattern = re.compile(r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)")
    for match in pattern.finditer(text):
        repo = match.group(1).rstrip(").,")
        if repo not in repos:
            repos.append(repo)
        if len(repos) >= limit:
            break
    return repos


def select_visual_repos(
    script_path: Path,
    report_path: Path | None,
    *,
    source_limit: int,
    visual_limit: int,
) -> list[str]:
    """Select visual repositories from the daily report Top N only.

    The script may mention the selected repositories explicitly. When it does,
    honor that order, but only if the repository also appears in the daily
    report's Top N list. This prevents the video pipeline from introducing
    projects outside the GitHub Trending daily report.
    """
    if not report_path or not report_path.exists():
        return []

    report_text = report_path.read_text(encoding="utf-8", errors="replace")
    top_repos = extract_github_repos(report_text, limit=source_limit)
    if not top_repos:
        return []

    script_text = script_path.read_text(encoding="utf-8", errors="replace")
    scripted_repos = extract_github_repos(script_text, limit=source_limit)
    selected: list[str] = []
    for repo in scripted_repos:
        if repo in top_repos and repo not in selected:
            selected.append(repo)
        if len(selected) >= visual_limit:
            return selected

    for repo in top_repos:
        if repo not in selected:
            selected.append(repo)
        if len(selected) >= visual_limit:
            break
    return selected


def _url_ext(url: str) -> str:
    """Return a lowercase file extension from a URL path, ignoring query args."""
    parsed = urllib.parse.urlparse(url)
    return Path(urllib.parse.unquote(parsed.path)).suffix.lower()


def _is_badge_media(url: str) -> bool:
    """Skip tiny status badges that often appear before real demo assets."""
    lowered = url.lower()
    badge_hosts = ("shields.io", "badgen.net", "badge.fury.io", "img.shields.io")
    badge_words = ("badge", "workflow", "coverage", "license", "version", "status")
    return any(host in lowered for host in badge_hosts) or any(word in lowered for word in badge_words)


def _fetch_repo_default_branch(repo: str) -> str:
    """Fetch the default branch so relative README media links resolve correctly."""
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}", "--jq", ".default_branch"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass

    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}",
            headers={"User-Agent": "content-studio-video/1.0"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read())
        branch = str(payload.get("default_branch") or "").strip()
        if branch:
            return branch
    except (OSError, ValueError):
        pass
    return "main"


def _resolve_readme_media_url(repo: str, raw_url: str, default_branch: str) -> str | None:
    """Resolve README media links to directly downloadable URLs."""
    value = html.unescape(raw_url.strip().strip("'\""))
    if not value or value.startswith("#") or value.startswith("data:"):
        return None
    if value.startswith("//"):
        value = f"https:{value}"

    parsed = urllib.parse.urlparse(value)
    if parsed.scheme in {"http", "https"}:
        if parsed.netloc == "github.com":
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 5 and parts[0] == repo.split("/", 1)[0] and parts[1] == repo.split("/", 1)[1]:
                if parts[2] in {"blob", "raw"}:
                    branch = parts[3]
                    path = "/".join(parts[4:])
                    quoted = urllib.parse.quote(path, safe="/")
                    return f"https://raw.githubusercontent.com/{repo}/{branch}/{quoted}"
            if parsed.path.startswith(f"/{repo}/raw/"):
                path = parsed.path.split("/raw/", 1)[1]
                return f"https://raw.githubusercontent.com/{repo}/{path}"
        return value

    path = value.split("#", 1)[0].split("?", 1)[0].strip()
    if not path:
        return None
    path = path.removeprefix("./").lstrip("/")
    quoted = urllib.parse.quote(path, safe="/")
    return f"https://raw.githubusercontent.com/{repo}/{default_branch}/{quoted}"


def _extract_readme_media_candidates(repo: str, readme: str) -> list[str]:
    """Find likely animated/demo media from README Markdown or HTML."""
    default_branch = _fetch_repo_default_branch(repo)
    raw_values: list[str] = []
    patterns = [
        r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)",
        r"\[[^\]]*(?:demo|preview|screenshot|gif|video)[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)",
        r"""<img[^>]+src=["']([^"']+)["']""",
        r"""<(?:source|video)[^>]+src=["']([^"']+)["']""",
    ]
    for pattern in patterns:
        raw_values.extend(match.group(1) for match in re.finditer(pattern, readme, re.IGNORECASE))

    candidates: list[str] = []
    for raw in raw_values:
        url = _resolve_readme_media_url(repo, raw, default_branch)
        if not url:
            continue
        ext = _url_ext(url)
        if ext not in _DEMO_MEDIA_EXTENSIONS or _is_badge_media(url):
            continue
        if url not in candidates:
            candidates.append(url)

    def score(url: str) -> tuple[int, int]:
        lowered = url.lower()
        hint_score = sum(1 for hint in _DEMO_MEDIA_HINTS if hint in lowered)
        ext_score = {".gif": 4, ".mp4": 3, ".webm": 2, ".mov": 1}.get(_url_ext(url), 0)
        return (hint_score, ext_score)

    return sorted(candidates, key=score, reverse=True)


def download_repo_demo_media(repo: str, output_dir: Path, index: int) -> Path | None:
    """Download the first useful README demo GIF/video for a repository."""
    safe_name = repo.replace("/", "__")
    cached = _find_cached_demo_media(output_dir, safe_name)
    if cached is not None:
        dest = output_dir / f"{index:02d}-{safe_name}-demo{cached.suffix.lower()}"
        if cached != dest:
            shutil.copyfile(cached, dest)
        print(f"🎞️  复用 README 演示素材缓存: {repo}")
        return dest

    try:
        readme = _fetch_repo_readme_raw(repo)
    except OSError:
        print(f"⚠️  README 读取失败，跳过演示素材: {repo}", file=sys.stderr)
        return None
    if not readme:
        print(f"ℹ️  README 不可用，跳过演示素材: {repo}")
        return None

    candidates = _extract_readme_media_candidates(repo, readme)
    if not candidates:
        print(f"ℹ️  未发现 README GIF/视频演示素材: {repo}")
        return None

    for candidate in candidates[:5]:
        ext = _url_ext(candidate)
        dest = output_dir / f"{index:02d}-{safe_name}-demo{ext}"
        try:
            print(f"🎞️  下载 README 演示素材: {repo} ({ext.lstrip('.')})")
            _download_demo_media(candidate, dest)
        except OSError as exc:
            print(f"⚠️  README 演示素材下载失败 {repo}: {exc}", file=sys.stderr)
            continue
        if dest.exists() and dest.stat().st_size > 4096:
            return dest
    print(f"ℹ️  README 演示素材不可用，改用截图/卡片: {repo}")
    return None


def _find_cached_demo_media(output_dir: Path, safe_name: str) -> Path | None:
    """Find a previously downloaded demo asset for the same repo."""
    roots = [output_dir, output_dir.parent]
    seen: set[Path] = set()
    for root in roots:
        if not root.exists() or root in seen:
            continue
        seen.add(root)
        patterns = [
            f"[0-9][0-9]-{safe_name}-demo.*",
            f"*/[0-9][0-9]-{safe_name}-demo.*",
        ]
        for pattern in patterns:
            for candidate in root.glob(pattern):
                if candidate.suffix.lower() in _DEMO_MEDIA_EXTENSIONS and candidate.stat().st_size > 4096:
                    return candidate
    return None


def _download_demo_media(url: str, dest: Path) -> None:
    """Download README demo media with a hard timeout so rendering never stalls."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 4096:
        return

    curl = shutil.which("curl")
    if curl:
        result = subprocess.run(
            [
                curl,
                "--fail",
                "--location",
                "--silent",
                "--show-error",
                "--max-time",
                "35",
                "--connect-timeout",
                "10",
                "--output",
                str(dest),
                url,
            ],
            capture_output=True,
            text=True,
            timeout=40,
        )
        if result.returncode == 0 and dest.exists() and dest.stat().st_size > 4096:
            return
        if dest.exists():
            dest.unlink(missing_ok=True)
        msg = (result.stderr or result.stdout or f"curl exit {result.returncode}").strip()
        raise OSError(msg)

    _download_file(url, dest, retries=1, min_bytes=4096, timeout=25)


def download_github_og_images(repos: list[str], output_dir: Path) -> list[Path]:
    """Download GitHub OpenGraph cards for selected repositories."""
    assets = download_repo_visual_assets(repos, output_dir)
    images: list[Path] = []
    for repo in repos:
        images.extend(assets.get(repo, []))
    return images


def download_repo_visual_assets(repos: list[str], output_dir: Path) -> dict[str, list[Path]]:
    """Download per-repo visuals: OG, title card, readme/stats cards, scroll strip."""
    output_dir.mkdir(parents=True, exist_ok=True)
    assets: dict[str, list[Path]] = {}
    for index, repo in enumerate(repos, 1):
        safe_name = repo.replace("/", "__")
        og_path = output_dir / f"{index:02d}-{safe_name}-og.png"
        title_path = output_dir / f"{index:02d}-{safe_name}-title.png"
        readme_path = output_dir / f"{index:02d}-{safe_name}-readme.png"
        stats_path = output_dir / f"{index:02d}-{safe_name}-stats.png"
        scroll_path = output_dir / f"{index:02d}-{safe_name}-scroll.png"
        repo_assets: list[Path] = []
        url = f"https://opengraph.githubassets.com/content-studio/{repo}"
        try:
            print(f"🖼️  下载 GitHub 项目卡片: {repo}")
            _download_file(url, og_path)
            if og_path.exists() and og_path.stat().st_size > 1024:
                repo_assets.append(og_path)
                if create_repo_branded_card(og_path, repo, title_path):
                    repo_assets.append(title_path)
                if create_repo_readme_card(repo, readme_path):
                    repo_assets.append(readme_path)
                if create_repo_stats_card(repo, stats_path):
                    repo_assets.append(stats_path)
                still_assets = [
                    path
                    for path in repo_assets
                    if path.suffix.lower() not in _DEMO_MEDIA_EXTENSIONS
                ]
                if create_repo_scroll_strip(still_assets[: _FRAMES_PER_PROJECT], scroll_path):
                    repo_assets.append(scroll_path)
        except Exception as exc:  # noqa: BLE001 - network/CDN errors must not abort pipeline
            print(f"⚠️  下载项目卡片失败 {repo}: {exc}", file=sys.stderr)
        assets[repo] = repo_assets
    return assets


def _fetch_repo_metadata(repo: str) -> dict[str, str]:
    """Fetch repo description/stars/language via gh CLI when available."""
    try:
        result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{repo}",
                "--jq",
                "{description: .description, stars: (.stargazers_count|tostring), language: .language}",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            return {}
        payload = json.loads(result.stdout or "{}")
        if isinstance(payload, dict):
            return {key: str(value) for key, value in payload.items() if value}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {}
    return {}


def _fetch_repo_readme_excerpt(repo: str, limit: int = 420) -> str:
    """Fetch README excerpt for a visual card."""
    text = _fetch_repo_readme_raw(repo)
    text = re.sub(r"\s+", " ", text.strip())
    return text[:limit]


def _fetch_repo_readme_raw(repo: str) -> str:
    """Fetch README Markdown via GitHub CLI when available."""
    try:
        result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{repo}/readme",
                "-H",
                "Accept: application/vnd.github.raw",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            return ""
        return result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _render_text_card(title: str, body: str, dest: Path) -> bool:
    """Render a simple text card for README/stats preview."""
    font_candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ]
    font = next((candidate for candidate in font_candidates if Path(candidate).exists()), "")
    font_clause = f":fontfile='{font}'" if font else ""
    safe_title = title.replace(":", "\\:").replace("'", "\\'")
    safe_body = body.replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "drawbox=x=0:y=0:w=iw:h=ih:color=0x111827:t=fill,"
        f"drawtext=text='{safe_title}'{font_clause}:fontcolor=white:fontsize=52:"
        "x=(w-text_w)/2:y=180,"
        f"drawtext=text='{safe_body}'{font_clause}:fontcolor=0xE5E7EB:fontsize=34:"
        "x=80:y=320:line_spacing=12"
    )
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=0x111827:s=1080x1920:r=1",
            "-frames:v",
            "1",
            "-vf",
            vf,
            str(dest),
        ],
        capture_output=True,
    )
    return result.returncode == 0 and dest.exists() and dest.stat().st_size > 0


def create_repo_readme_card(repo: str, dest: Path) -> bool:
    """Create a README excerpt card."""
    excerpt = _fetch_repo_readme_excerpt(repo)
    if not excerpt:
        return False
    short_name = repo.split("/", 1)[-1]
    return _render_text_card(f"{short_name} / README", excerpt, dest)


def create_repo_stats_card(repo: str, dest: Path) -> bool:
    """Create a stats card with stars/language/description."""
    meta = _fetch_repo_metadata(repo)
    if not meta:
        return False
    short_name = repo.split("/", 1)[-1]
    stars = meta.get("stars", "?")
    language = meta.get("language", "Unknown")
    description = meta.get("description", "")
    body = f"Stars: {stars}\\nLanguage: {language}\\n\\n{description[:260]}"
    return _render_text_card(f"{short_name} / Overview", body, dest)


def create_repo_scroll_strip(images: list[Path], dest: Path) -> bool:
    """Stack multiple cards vertically for a homepage-like scroll effect."""
    usable = [path for path in images if path.exists() and path.stat().st_size > 0]
    if len(usable) < 2:
        return False
    scaled_inputs: list[str] = []
    for index, image in enumerate(usable):
        scaled_inputs.append(f"[{index}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[s{index}]")
    stack_inputs = "".join(f"[s{index}]" for index in range(len(usable)))
    filter_complex = (
        ";".join(scaled_inputs)
        + f";{stack_inputs}vstack=inputs={len(usable)}[vout]"
    )
    cmd = ["ffmpeg", "-y"]
    for image in usable:
        cmd.extend(["-i", str(image)])
    cmd.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-frames:v",
            "1",
            str(dest),
        ]
    )
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0 and dest.exists() and dest.stat().st_size > 0


def create_repo_branded_card(source: Path, repo: str, dest: Path) -> bool:
    """Create a second slide variant with repo name overlay for visual variety."""
    short_name = repo.split("/", 1)[-1]
    font_candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ]
    font = next((candidate for candidate in font_candidates if Path(candidate).exists()), "")
    font_clause = f":fontfile='{font}'" if font else ""
    vf = (
        "scale=1080:-1,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x111827,"
        "drawbox=x=0:y=h-220:w=iw:h=220:color=black@0.55:t=fill,"
        f"drawtext=text='{short_name}'{font_clause}:fontcolor=white:fontsize=42:"
        "x=(w-text_w)/2:y=h-150"
    )
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-vf",
            vf,
            "-frames:v",
            "1",
            str(dest),
        ],
        capture_output=True,
    )
    return result.returncode == 0 and dest.exists() and dest.stat().st_size > 0


def render_image_motion_segment(
    image_path: Path,
    dest: Path,
    duration: float,
    *,
    effect: str = "zoom_in",
) -> bool:
    """Render one still image with light motion for intro/cover clips."""
    duration = max(duration, 0.5)
    vf = _motion_slide_filter(effect, duration)
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(image_path),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            str(dest),
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-t",
                f"{duration:.3f}",
                "-i",
                str(image_path),
                "-vf",
                _static_slide_filter(),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                str(dest),
            ],
            capture_output=True,
        )
    return result.returncode == 0 and dest.exists() and dest.stat().st_size > 0


def render_demo_media_segment(media_path: Path, dest: Path, duration: float) -> bool:
    """Render an animated README demo GIF/video as a vertical project clip."""
    duration = max(duration, 0.5)
    vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x111827,fps=24"
    cmd = [
        "ffmpeg",
        "-y",
        "-stream_loop",
        "-1",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(media_path),
        "-vf",
        vf,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        str(dest),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
        return True

    fallback = [
        "ffmpeg",
        "-y",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(media_path),
        "-vf",
        vf,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        str(dest),
    ]
    result = subprocess.run(fallback, capture_output=True)
    return result.returncode == 0 and dest.exists() and dest.stat().st_size > 0


def _prepare_daily_ranking_chart(
    source_report: Path | None,
    script_path: Path,
    asset_dir: Path,
    featured_repos: list[str],
) -> Path | None:
    """Build the daily ranking chart PNG used for intro and cover."""
    if source_report is None or not source_report.is_file():
        return None
    if os.environ.get("CONTENT_STUDIO_DISABLE_RANKING_CHART", "0") == "1":
        return None

    rows = parse_daily_overview_table(source_report, limit=10)
    if not rows:
        return None

    rows = merge_script_summaries(rows, script_path)
    if os.environ.get("CONTENT_STUDIO_SKIP_STAR_FETCH", "0") != "1":
        enrich_overview_stars(rows)

    chart_png = asset_dir / "daily-ranking-chart.png"
    cover_jpg = asset_dir / "daily-ranking-cover.jpg"
    title_date = report_date_from_path(source_report)
    theme = _extract_chart_theme(script_path)
    if not generate_daily_ranking_chart(
        rows,
        title_date=title_date,
        featured_repos=set(featured_repos),
        dest=chart_png,
        cover_dest=cover_jpg,
        theme_title=theme["title"],
        theme_subtitle=theme["subtitle"],
        theme_tags=theme["tags"],
        narrative_chain=theme["chain"],
    ):
        return None

    print(f"📊 日榜排行图已生成: {chart_png}")
    return chart_png


def _extract_chart_theme(script_path: Path) -> dict[str, object]:
    """Extract compact theme metadata for the opening ranking card."""
    fallback = {
        "title": "GitHub 热榜",
        "subtitle": "趋势项目集中爆发",
        "tags": ["GitHub", "AI Agent", "Workflow", "Open Source"],
        "chain": [],
    }
    if not script_path.is_file():
        return fallback

    text = script_path.read_text(encoding="utf-8", errors="replace")
    thesis_match = re.search(r"\*\*一句话 thesis\*\*[:：]\s*(.+)", text)
    tags_match = re.search(r"\*\*趋势标签\*\*[:：]\s*(.+)", text)
    chain_match = re.search(r"\*\*叙事链\*\*[:：]\s*(.+)", text)

    title = "GitHub 热榜"
    subtitle = "趋势项目集中爆发"
    if thesis_match:
        thesis = re.sub(r"[。.!！]+$", "", thesis_match.group(1).strip())
        if "Agent" in thesis or "agent" in thesis:
            title = "Agent 工程化"
        elif "AI" in thesis:
            title = "AI 工具链"
        else:
            title = thesis[:12]
        subtitle = thesis[:20]

    tags = fallback["tags"]
    if tags_match:
        parsed_tags = [tag.strip() for tag in re.split(r"[、,，]", tags_match.group(1)) if tag.strip()]
        if parsed_tags:
            tags = parsed_tags[:4]

    chain: list[str] = []
    if chain_match:
        raw_chain = chain_match.group(1)
        chain = [
            re.sub(r"\s*\([^)]*\)", "", part).strip()
            for part in re.split(r"\s*->\s*", raw_chain)
            if part.strip()
        ][:3]

    return {"title": title, "subtitle": subtitle, "tags": tags, "chain": chain}


def _repo_scroll_strip(
    repo: str,
    asset_dir: Path,
    repo_assets: dict[str, list[Path]] | None,
) -> Path | None:
    """Return a tall scroll-strip image for one repo, downloading cards if needed."""
    images = list((repo_assets or {}).get(repo, []))
    scroll_strip = next((path for path in images if path.name.endswith("-scroll.png")), None)
    if scroll_strip is not None and scroll_strip.exists():
        return scroll_strip

    extra = download_repo_visual_assets([repo], asset_dir).get(repo, [])
    scroll_strip = next((path for path in extra if path.name.endswith("-scroll.png")), None)
    if scroll_strip is not None and scroll_strip.exists():
        return scroll_strip
    return None


def _repo_demo_media(repo: str, asset_dir: Path, repo_assets: dict[str, list[Path]] | None) -> Path | None:
    """Return a downloaded animated README demo asset for one repo."""
    if os.environ.get("CONTENT_STUDIO_ENABLE_README_DEMO", "0") != "1":
        return None
    assets = list((repo_assets or {}).get(repo, []))
    for asset in assets:
        if asset.exists() and asset.suffix.lower() in _DEMO_MEDIA_EXTENSIONS:
            return asset
    if repo_assets is not None and repo in repo_assets:
        return None
    extra = download_repo_visual_assets([repo], asset_dir).get(repo, [])
    for asset in extra:
        if asset.exists() and asset.suffix.lower() in _DEMO_MEDIA_EXTENSIONS:
            return asset
    return None


def _render_card_scroll_segment(
    repo: str,
    dest: Path,
    duration: float,
    asset_dir: Path,
    repo_assets: dict[str, list[Path]] | None,
) -> bool:
    """Fallback: pan down a stacked card strip when live GitHub capture fails."""
    scroll_strip = _repo_scroll_strip(repo, asset_dir, repo_assets)
    if scroll_strip is None:
        images = [
            path
            for path in list((repo_assets or {}).get(repo, []))
            if path.suffix.lower() not in _DEMO_MEDIA_EXTENSIONS
        ]
        if not images:
            images = [
                path
                for path in download_repo_visual_assets([repo], asset_dir).get(repo, [])
                if path.suffix.lower() not in _DEMO_MEDIA_EXTENSIONS
            ]
        og_image = next((path for path in images if path.name.endswith("-og.png")), None)
        if og_image is not None and og_image.exists():
            return render_image_motion_segment(og_image, dest, duration, effect="pan_up")
        return False

    duration = max(duration, 0.5)
    vf = _scroll_strip_filter(duration)
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(scroll_strip),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            str(dest),
        ],
        capture_output=True,
    )
    return result.returncode == 0 and dest.exists() and dest.stat().st_size > 0


def render_outro_summary_card(text: str, dest: Path) -> bool:
    """Render a polished closing insight card from the outro narration."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False

    width, height = _GITHUB_SCROLL_WIDTH, _GITHUB_SCROLL_HEIGHT
    image = Image.new("RGB", (width, height), "#04142B")
    pixels = image.load()
    top = (3, 18, 40)
    bottom = (1, 7, 22)
    glow = (0, 192, 255)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        for x in range(width):
            radial = max(
                0.0,
                1.0
                - (((x - width * 0.55) / 600) ** 2 + ((y - height * 0.18) / 540) ** 2),
            )
            pixels[x, y] = tuple(
                int(top[i] * (1 - ratio) + bottom[i] * ratio + glow[i] * radial * 0.10)
                for i in range(3)
            )

    draw = ImageDraw.Draw(image, "RGBA")
    for x in range(80, width, 96):
        draw.line((x, 0, x, height), fill=(75, 166, 255, 16), width=1)
    for y in range(90, height, 96):
        draw.line((0, y, width, y), fill=(75, 166, 255, 14), width=1)

    eyebrow_font = _load_callout_font(30)
    title_font = _load_callout_font(68)
    subtitle_font = _load_callout_font(42)
    body_font = _load_callout_font(32)
    small_font = _load_callout_font(24)

    def text_size(value: str, font) -> tuple[int, int]:
        bbox = draw.textbbox((0, 0), value, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    def centered(y: int, value: str, font, fill: str) -> None:
        text_w, _ = text_size(value, font)
        draw.text(((width - text_w) / 2, y), value, font=font, fill=fill)

    centered(160, "Content Studio · 长期判断", eyebrow_font, "#8FB7D8")
    centered(260, "接下来的核心竞争力", title_font, "#CFF4FF")
    centered(345, "不是模型接口，而是工程化链路", subtitle_font, "#22D3EE")

    sentences = [part.strip() for part in re.split(r"[。！？!?]", text) if part.strip()]
    bullets = sentences[-3:] if len(sentences) >= 3 else sentences
    if not bullets:
        bullets = ["把 AI 深度嵌入工作流", "掌握 Agent 编排", "沉淀可复用生产规范"]

    card_x, card_y, card_w = 122, 540, 836
    bullet_labels = ["趋势", "机会", "行动"]
    for index, bullet in enumerate(bullets[:3]):
        y0 = card_y + index * 178
        y1 = y0 + 128
        draw.rounded_rectangle(
            (card_x, y0, card_x + card_w, y1),
            radius=22,
            fill=(5, 21, 48, 220),
            outline=(56, 189, 248, 120),
            width=2,
        )
        label = bullet_labels[index]
        draw.rounded_rectangle((card_x + 24, y0 + 32, card_x + 112, y0 + 88), radius=16, fill=(14, 165, 233, 230))
        centered_x = card_x + 68
        label_w, _ = text_size(label, small_font)
        draw.text((centered_x - label_w / 2, y0 + 43), label, font=small_font, fill="#001223")

        wrapped = _wrap_card_text(bullet, 24)[:2]
        for line_idx, line in enumerate(wrapped):
            draw.text((card_x + 140, y0 + 28 + line_idx * 42), line, font=body_font, fill="#EAF6FF")

    centered(1160, "Agent 工程化", subtitle_font, "#22D3EE")
    centered(1222, "基座 + 网关 + 工程增强", subtitle_font, "#FACC15")

    footer = "把热榜项目看成生产链路，而不是孤立工具"
    centered(height - 170, footer, small_font, "#8FB7D8")

    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, format="PNG")
    return dest.exists() and dest.stat().st_size > 0


def _wrap_card_text(text: str, max_chars: int) -> list[str]:
    compact = re.sub(r"\s+", " ", text.strip())
    lines: list[str] = []
    current = ""
    for char in compact:
        if len(current) >= max_chars:
            lines.append(current)
            current = char
        else:
            current += char
    if current:
        lines.append(current)
    return lines


def _split_project_segment_duration(total: float) -> tuple[float, float]:
    """Split one project narration block into intro-card and github-scroll durations."""
    intro = min(
        _PROJECT_INTRO_CARD_MAX_S,
        max(_PROJECT_INTRO_CARD_MIN_S, total * _PROJECT_INTRO_CARD_RATIO),
    )
    if intro >= total - 1.0:
        intro = max(2.0, total * 0.4)
    return intro, max(total - intro, 1.0)


def create_github_page_scroll_video(
    repos: list[str],
    dest: Path,
    timeline: list[TimelineSegment],
    asset_dir: Path,
    *,
    ranking_chart: Path | None = None,
    repo_assets: dict[str, list[Path]] | None = None,
    source_report: Path | None = None,
    script_path: Path | None = None,
) -> bool:
    """Create GitHub page scroll clips with red callout arrows.

    Raises:
        VideoRenderError: If any segment cannot be rendered via github-scroll.
    """
    del repo_assets  # card screenshots are intentionally unsupported.
    if os.environ.get("GITHUB_PAGE_SCROLL", "1") == "0":
        msg = "GITHUB_PAGE_SCROLL=0 已禁用页面滚动渲染"
        raise VideoRenderError(msg)
    if not repos:
        msg = "未从日报/脚本中解析到任何 GitHub 仓库，无法生成画面"
        raise VideoRenderError(msg)
    if not timeline:
        msg = "口播时间轴为空，无法生成画面"
        raise VideoRenderError(msg)

    scroll_dir = asset_dir / "github-scroll"
    scroll_dir.mkdir(parents=True, exist_ok=True)
    intro_contexts = {}
    if source_report and script_path:
        intro_contexts = build_project_intro_contexts(
            repos,
            report_path=source_report,
            script_path=script_path,
        )
    captures: dict[str, tuple[Path, list[dict[str, float | str]]]] = {}
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        segments: list[Path] = []
        for index, segment in enumerate(timeline):
            segment_duration = max(segment.end - segment.start, 0.5)
            segment_path = tmp / f"github-scroll-{index:02d}.mp4"
            if segment.kind == "intro":
                if ranking_chart is None or not ranking_chart.exists():
                    msg = "开场日榜排行图缺失，无法渲染 intro 段"
                    raise VideoRenderError(msg)
                if not render_image_motion_segment(
                    ranking_chart,
                    segment_path,
                    segment_duration,
                    effect="zoom_in",
                ):
                    msg = "开场日榜视频段 ffmpeg 渲染失败"
                    raise VideoRenderError(msg)
                segments.append(segment_path)
                print(
                    f"🎞️  {segment.start:.1f}-{segment.end:.1f}s "
                    "daily-ranking-chart → 开场日榜"
                )
                continue

            if segment.kind == "outro":
                summary_card = asset_dir / "outro-summary-card.png"
                if not render_outro_summary_card(segment.text, summary_card):
                    msg = "结尾总结卡生成失败，无法渲染 outro 段"
                    raise VideoRenderError(msg)
                if not render_image_motion_segment(
                    summary_card,
                    segment_path,
                    segment_duration,
                    effect="zoom_in",
                ):
                    msg = "结尾总结卡视频段 ffmpeg 渲染失败"
                    raise VideoRenderError(msg)
                segments.append(segment_path)
                print(
                    f"🎞️  {segment.start:.1f}-{segment.end:.1f}s "
                    "summary-card → 长期判断"
                )
                continue

            if segment.kind != "project":
                continue

            repo = _repo_for_timeline_segment(segment, repos)
            if repo is None:
                msg = f"时间轴 project 段无法匹配仓库: index={segment.project_index}"
                raise VideoRenderError(msg)

            if repo not in captures:
                screenshot = scroll_dir / f"{repo.replace('/', '__')}-fullpage.png"
                markers = capture_github_repo_page(repo, screenshot)
                captures[repo] = (screenshot, markers)

            card_duration, scroll_duration = _split_project_segment_duration(segment_duration)
            intro_card_path = asset_dir / f"{repo.replace('/', '__')}-intro.png"
            context = intro_contexts.get(repo)
            if context and generate_project_intro_card(context, intro_card_path):
                card_segment = tmp / f"github-scroll-{index:02d}-intro.mp4"
                if render_image_motion_segment(
                    intro_card_path,
                    card_segment,
                    card_duration,
                    effect="zoom_in",
                ):
                    segments.append(card_segment)
                    print(
                        f"🎞️  {segment.start:.1f}-{segment.start + card_duration:.1f}s "
                        f"project-showcase → {repo}"
                    )
                else:
                    scroll_duration = segment_duration
            else:
                scroll_duration = segment_duration

            scroll_segment = tmp / f"github-scroll-{index:02d}-scroll.mp4"
            screenshot, markers = captures[repo]
            if not render_github_scroll_segment(
                screenshot,
                markers,
                scroll_segment,
                scroll_duration,
                show_callouts=True,
            ):
                msg = f"github-scroll 渲染失败: {repo}（截图={screenshot}）"
                raise VideoRenderError(msg)

            segments.append(scroll_segment)
            print(
                f"🎞️  {segment.start + card_duration:.1f}-{segment.end:.1f}s "
                f"github-scroll → {repo}"
            )

        expected_segments = sum(
            2 if segment.kind == "project" else 1
            for segment in timeline
            if segment.kind in {"intro", "project", "outro"}
        )
        if expected_segments == 0:
            msg = (
                "时间轴没有 intro/project 片段，无法生成 GitHub 滚动视频；"
                "请检查脚本是否包含可切分的趋势开场和项目段落"
            )
            raise VideoRenderError(msg)
        if not segments:
            msg = (
                "没有成功渲染任何视频片段，已中止；"
                "请检查 GitHub 页面截图、分镜表和项目段落切分"
            )
            raise VideoRenderError(msg)
        if len(segments) != expected_segments:
            msg = (
                f"视频片段不完整: 期望 {expected_segments} 段"
                f"（intro + project + outro），实际 {len(segments)} 段"
            )
            raise VideoRenderError(msg)

        concat_file = tmp / "concat.txt"
        concat_file.write_text(
            "\n".join(f"file '{segment}'" for segment in segments),
            encoding="utf-8",
        )
        concat_out = tmp / "github-scroll.mp4"
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(concat_out),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            msg = f"ffmpeg 拼接视频片段失败: {stderr or 'unknown error'}"
            raise VideoRenderError(msg)
        if not _fit_video_to_duration(concat_out, dest, timeline[-1].end):
            msg = "ffmpeg 调整视频时长失败"
            raise VideoRenderError(msg)
        return True


def _repo_for_timeline_segment(segment: TimelineSegment, repos: list[str]) -> str | None:
    """Select the repo shown for one timeline block."""
    if not repos:
        return None
    if segment.kind == "project" and segment.project_index is not None:
        if 0 <= segment.project_index < len(repos):
            return repos[segment.project_index]
    return repos[0]


def capture_github_repo_page(repo: str, dest: Path) -> list[dict[str, float | str]]:
    """Capture a full GitHub repo page and return top-of-page callout targets.

    Raises:
        VideoRenderError: If Playwright is missing, navigation fails, or screenshot is empty.
    """
    if dest.exists() and dest.stat().st_size > 1024:
        markers = _default_github_callout_markers()
        if markers:
            return markers

    _ensure_playwright_home()
    profile_home = os.environ.get("HOME", "")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        msg = (
            "未安装 playwright。请在 profile home 下执行: "
            f"HOME={profile_home or _PROFILE_HOME} playwright install chromium"
        )
        raise VideoRenderError(msg) from exc

    url = f"https://github.com/{repo}"
    max_attempts = max(1, int(os.environ.get("GITHUB_CAPTURE_RETRIES", "3")))
    last_error: VideoRenderError | None = None

    for attempt in range(1, max_attempts + 1):
        load_errors: list[str] = []
        markers: list[dict[str, float | str]] = []
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page(
                        viewport={
                            "width": _GITHUB_SCROLL_WIDTH,
                            "height": _GITHUB_SCROLL_HEIGHT,
                        },
                        device_scale_factor=1,
                        user_agent=(
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0 Safari/537.36"
                        ),
                    )
                    page.route(
                        "**/*",
                        lambda route: route.abort()
                        if route.request.resource_type == "media"
                        else route.continue_(),
                    )
                    loaded = False
                    for wait_until in ("domcontentloaded", "commit", "load"):
                        try:
                            page.goto(url, wait_until=wait_until, timeout=90_000)
                            loaded = True
                            break
                        except Exception as exc:  # noqa: BLE001 - retry with looser wait strategy.
                            load_errors.append(f"{wait_until}: {exc}")
                    if not loaded:
                        detail = "; ".join(load_errors) or "unknown navigation error"
                        msg = f"GitHub 页面加载失败 {repo} ({url}): {detail}"
                        raise VideoRenderError(msg)
                    try:
                        page.wait_for_load_state("networkidle", timeout=15_000)
                    except Exception:
                        pass
                    page.wait_for_timeout(2_000)
                    if "github.com" not in page.url:
                        msg = f"GitHub 页面跳转异常 {repo}: 当前 URL={page.url}"
                        raise VideoRenderError(msg)
                    page.evaluate(
                        """
                        () => {
                          if (!document.body || !document.documentElement) {
                            return;
                          }
                          document.documentElement.style.scrollBehavior = 'auto';
                          document.body.style.scrollBehavior = 'auto';
                          window.scrollTo(0, 0);
                        }
                        """
                    )
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(dest), full_page=True, timeout=60_000)
                    try:
                        markers = page.evaluate(
                            """
                        () => {
                          const rectFor = (label, el) => {
                            if (!el) return null;
                            const rect = el.getBoundingClientRect();
                            if (rect.width <= 0 || rect.height <= 0) return null;
                            return {
                              label,
                              x: rect.x + rect.width / 2,
                              y: rect.y + rect.height / 2,
                              width: rect.width,
                              height: rect.height,
                            };
                          };
                          const name =
                            document.querySelector('strong[itemprop="name"] a') ||
                            document.querySelector('#repository-container-header strong a') ||
                            document.querySelector('[data-testid="repository-name"]');
                          const stars =
                            document.querySelector('#repo-stars-counter-star') ||
                            document.querySelector('a[href$="/stargazers"] strong') ||
                            document.querySelector('a[href$="/stargazers"]');
                          const forks =
                            document.querySelector('#repo-network-counter') ||
                            document.querySelector('a[href$="/forks"] strong') ||
                            document.querySelector('a[href$="/forks"]');
                          const about =
                            document.querySelector('h2.mb-3.h4') ||
                            Array.from(document.querySelectorAll('h2, h3'))
                              .find((el) => el.textContent && el.textContent.trim() === 'About');
                          const readme =
                            document.querySelector('#readme h2') ||
                            document.querySelector('#readme h1') ||
                            document.querySelector('[data-target="readme-toc.content"] h2');
                          return [
                            rectFor('项目名称', name),
                            rectFor('Star 数', stars),
                            rectFor('Fork 数', forks),
                            rectFor('项目简介', about),
                            rectFor('README', readme),
                          ]
                            .filter(Boolean);
                        }
                        """
                        )
                    except Exception as exc:  # noqa: BLE001 - marker DOM can drift; keep screenshot.
                        print(f"⚠️  标注解析失败 {repo}，使用默认位置: {exc}", file=sys.stderr)
                        markers = []
                finally:
                    browser.close()
        except VideoRenderError as exc:
            last_error = exc
            if attempt < max_attempts:
                print(
                    f"⚠️  GitHub 截图重试 {attempt}/{max_attempts}: {repo} — {exc}",
                    file=sys.stderr,
                )
                time.sleep(min(5 * attempt, 20))
                dest.unlink(missing_ok=True)
                continue
            raise
        except Exception as exc:
            last_error = VideoRenderError(f"GitHub 页面截图失败 {repo}: {exc}")
            if attempt < max_attempts:
                print(
                    f"⚠️  GitHub 截图重试 {attempt}/{max_attempts}: {repo} — {exc}",
                    file=sys.stderr,
                )
                time.sleep(min(5 * attempt, 20))
                dest.unlink(missing_ok=True)
                continue
            raise last_error from exc

        if not dest.exists() or dest.stat().st_size <= 1024:
            last_error = VideoRenderError(f"GitHub 全页截图无效 {repo}: {dest}")
            if attempt < max_attempts:
                print(
                    f"⚠️  GitHub 截图重试 {attempt}/{max_attempts}: {repo} — 无效截图",
                    file=sys.stderr,
                )
                time.sleep(min(5 * attempt, 20))
                continue
            raise last_error
        if not isinstance(markers, list) or not markers:
            return _default_github_callout_markers()
        try:
            return _sanitize_callout_markers(markers)
        except (TypeError, ValueError):
            return _default_github_callout_markers()

    if last_error:
        raise last_error
    msg = f"GitHub 页面截图失败 {repo}"
    raise VideoRenderError(msg)


def _default_github_callout_markers() -> list[dict[str, float | str]]:
    """Fallback callout positions for GitHub's desktop repo header."""
    return [
        {"label": "项目名称", "x": 260.0, "y": 100.0, "width": 220.0, "height": 38.0},
        {"label": "Star 数", "x": 870.0, "y": 100.0, "width": 120.0, "height": 36.0},
        {"label": "项目简介", "x": 820.0, "y": 390.0, "width": 260.0, "height": 90.0},
        {"label": "README", "x": 230.0, "y": 1160.0, "width": 280.0, "height": 60.0},
    ]


def _sanitize_callout_markers(markers: list[object]) -> list[dict[str, float | str]]:
    """Keep only finite marker coordinates inside the 1080x1920 viewport."""
    clean: list[dict[str, float | str]] = []
    for marker in markers:
        if not isinstance(marker, dict):
            continue
        label = str(marker.get("label") or "重点")
        try:
            x = float(marker["x"])
            y = float(marker["y"])
            width = float(marker.get("width", 80.0))
            height = float(marker.get("height", 32.0))
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(x) or not math.isfinite(y):
            continue
        if 0 <= x <= _GITHUB_SCROLL_WIDTH and 0 <= y <= _GITHUB_SCROLL_HEIGHT:
            clean.append({"label": label, "x": x, "y": y, "width": width, "height": height})
    return clean or _default_github_callout_markers()


def render_github_scroll_segment(
    screenshot: Path,
    markers: list[dict[str, float | str]],
    dest: Path,
    duration: float,
    *,
    show_callouts: bool,
) -> bool:
    """Render a vertical scroll animation from one full-page screenshot."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        normalized = tmp / "page.png"
        overlay = tmp / "callouts.png"
        if not normalize_scroll_screenshot(screenshot, normalized):
            return False
        if show_callouts and not draw_callout_overlay(markers, overlay):
            show_callouts = False

        vf = _github_scroll_filter(duration)
        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(normalized),
        ]
        if show_callouts:
            filter_complex = (
                f"[0:v]{vf}[base];"
                "[1:v]format=rgba,fade=t=out:st=3.2:d=0.5:alpha=1[mark];"
                "[base][mark]overlay=0:0:enable='lt(t,3.7)',fps=24[v]"
            )
            cmd.extend(
                [
                    "-loop",
                    "1",
                    "-t",
                    f"{duration:.3f}",
                    "-i",
                    str(overlay),
                    "-filter_complex",
                    filter_complex,
                    "-map",
                    "[v]",
                ]
            )
        else:
            cmd.extend(["-vf", vf])
        cmd.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                str(dest),
            ]
        )
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0 and dest.exists() and dest.stat().st_size > 0


def normalize_scroll_screenshot(source: Path, dest: Path) -> bool:
    """Resize a browser screenshot to video width and pad short pages."""
    try:
        from PIL import Image
    except ImportError:
        return False

    try:
        with Image.open(source) as image:
            image = image.convert("RGB")
            if image.width != _GITHUB_SCROLL_WIDTH:
                height = max(int(image.height * _GITHUB_SCROLL_WIDTH / image.width), 1)
                image = image.resize((_GITHUB_SCROLL_WIDTH, height), Image.Resampling.LANCZOS)
            if image.height < _GITHUB_SCROLL_HEIGHT:
                padded = Image.new("RGB", (_GITHUB_SCROLL_WIDTH, _GITHUB_SCROLL_HEIGHT), "#ffffff")
                padded.paste(image, (0, 0))
                image = padded
            image.save(dest)
    except OSError:
        return False
    return dest.exists() and dest.stat().st_size > 0


def draw_callout_overlay(markers: list[dict[str, float | str]], dest: Path) -> bool:
    """Draw red arrows and labels over the opening GitHub page hold."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False

    image = Image.new("RGBA", (_GITHUB_SCROLL_WIDTH, _GITHUB_SCROLL_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _load_callout_font(42)
    label_positions = [
        (64, 240),
        (64, 370),
        (64, 500),
        (64, 630),
        (64, 760),
    ]
    for index, marker in enumerate(markers[:5]):
        label = str(marker["label"])
        target = (float(marker["x"]), float(marker["y"]))
        box_w = min(max(float(marker.get("width", 90.0)) + 34, 120.0), 320.0)
        box_h = min(max(float(marker.get("height", 34.0)) + 24, 72.0), 130.0)
        draw.rounded_rectangle(
            [
                target[0] - box_w / 2,
                target[1] - box_h / 2,
                target[0] + box_w / 2,
                target[1] + box_h / 2,
            ],
            radius=18,
            outline=(239, 68, 68, 245),
            width=8,
        )
        label_x, label_y = label_positions[index % len(label_positions)]
        label_width = max(230, min(340, 110 + len(label) * 42))
        label_box = (label_x, label_y, label_x + label_width, label_y + 68)
        draw.rounded_rectangle(label_box, radius=18, fill=(220, 38, 38, 235))
        draw.text((label_x + 24, label_y + 10), label, font=font, fill=(255, 255, 255, 255))
        start = (label_x + label_width, label_y + 34)
        draw_arrow(draw, start, target)
    image.save(dest)
    return dest.exists() and dest.stat().st_size > 0


def _load_callout_font(size: int):
    """Load a CJK-capable font for callout labels."""
    try:
        from PIL import ImageFont
    except ImportError:
        return None

    for candidate in (
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ):
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    return ImageFont.load_default()


def draw_arrow(draw, start: tuple[float, float], end: tuple[float, float]) -> None:
    """Draw a thick red arrow between two points."""
    color = (220, 38, 38, 255)
    draw.line([start, end], fill=color, width=10)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    size = 30
    left = (
        end[0] - size * math.cos(angle - math.pi / 6),
        end[1] - size * math.sin(angle - math.pi / 6),
    )
    right = (
        end[0] - size * math.cos(angle + math.pi / 6),
        end[1] - size * math.sin(angle + math.pi / 6),
    )
    draw.polygon([end, left, right], fill=color)


def _github_scroll_filter(duration: float) -> str:
    """Crop a full-page screenshot with one-screen step scrolls.

    Short-video readability works best when each viewport stays readable for
    about 2.5-4s, with 0.8-1.0s motion between screens.
    """
    duration = max(duration, 1.0)
    screen_count = 4 if duration >= 18 else 3 if duration >= 10 else 2
    transition = min(1.0, max(0.75, duration * 0.07))
    hold = max((duration - transition * (screen_count - 1)) / screen_count, 1.8)
    step = _GITHUB_SCROLL_HEIGHT * _GITHUB_SCROLL_STEP_RATIO
    stops = [
        f"min(ih-1920\\,{index * step:.1f})"
        for index in range(screen_count)
    ]
    expr = stops[-1]
    cursor = 0.0
    phases: list[tuple[float, float, str, str]] = []
    for index in range(screen_count - 1):
        hold_end = cursor + hold
        transition_end = hold_end + transition
        phases.append((hold_end, transition_end, stops[index], stops[index + 1]))
        cursor = transition_end

    for hold_end, transition_end, start, end in reversed(phases):
        linear = f"{start}+({end}-{start})*(t-{hold_end:.3f})/{transition:.3f}"
        expr = (
            f"if(lt(t\\,{hold_end:.3f})\\,{start}\\,"
            f"if(lt(t\\,{transition_end:.3f})\\,{linear}\\,{expr}))"
        )
    y_expr = expr
    return f"crop=1080:1920:0:'max(0\\,{y_expr})',fps=24"


def _scroll_strip_filter(duration: float, fps: int = 24) -> str:
    """Pan down a tall stacked strip to simulate GitHub page scrolling."""
    duration = max(duration, 1.0)
    return (
        "scale=1080:-1,"
        f"crop=1080:1920:0:'max(0,(ih-1920)*t/{duration})',"
        f"fps={fps}"
    )


def _motion_slide_filter(effect: str, duration: float, fps: int = 24) -> str:
    """Fast slide motion using crop/pan/zoom (much faster than zoompan)."""
    duration = max(duration, 1.0)
    base = "scale=1080:-1,pad=1080:2200:(ow-iw)/2:(oh-ih)/2:color=0x111827"
    if effect == "zoom_out":
        return (
            f"scale=1240:-1,pad=1240:2200:(ow-iw)/2:(oh-ih)/2:color=0x111827,"
            f"crop=1080:1920:'(iw-1080)/2*(1-t/{duration})':'(ih-1920)/2*(1-t/{duration})',fps={fps}"
        )
    if effect == "pan_up":
        return f"{base},crop=1080:1920:0:'(ih-1920)*t/{duration}',fps={fps}"
    return (
        f"scale=1240:-1,pad=1240:2200:(ow-iw)/2:(oh-ih)/2:color=0x111827,"
        f"crop=1080:1920:'(iw-1080)/2*(t/{duration})':'(ih-1920)/2*(t/{duration})',fps={fps}"
    )


def _static_slide_filter() -> str:
    """Fallback slide filter when motion generation fails."""
    return "scale=1080:-1,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x111827,fps=24"


def create_slideshow_video(
    repos: list[str],
    assets: dict[str, list[Path]],
    dest: Path,
    timeline: list[TimelineSegment],
    *,
    ranking_chart: Path | None = None,
) -> bool:
    """Create visual clips from the shared timeline; one block can scroll or multi-cut."""
    if not repos or not timeline or not any(assets.get(repo) for repo in repos):
        return False

    visual_clips = expand_timeline_to_visual_clips(
        timeline,
        repos,
        assets,
        intro_image=ranking_chart,
    )
    if not visual_clips:
        return False

    target_duration = timeline[-1].end if timeline else 0.0
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        segments: list[Path] = []

        for index, clip in enumerate(visual_clips):
            duration = max(clip.end - clip.start, 0.5)
            segment_path = tmp / f"segment-{index:02d}.mp4"
            if clip.scroll_strip:
                vf = _scroll_strip_filter(duration)
            else:
                vf = _motion_slide_filter(clip.effect, duration)
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loop",
                    "1",
                    "-t",
                    f"{duration:.3f}",
                    "-i",
                    str(clip.image),
                    "-vf",
                    vf,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-pix_fmt",
                    "yuv420p",
                    str(segment_path),
                ],
                capture_output=True,
            )
            if result.returncode != 0:
                result = subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-loop",
                        "1",
                        "-t",
                        f"{duration:.3f}",
                        "-i",
                        str(clip.image),
                        "-vf",
                        _static_slide_filter(),
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-crf",
                        "23",
                        "-pix_fmt",
                        "yuv420p",
                        str(segment_path),
                    ],
                    capture_output=True,
                )
            if result.returncode != 0:
                print(f"⚠️  幻灯片片段生成失败: {clip.image}", file=sys.stderr)
                continue
            segments.append(segment_path)
            print(
                f"🎞️  {clip.start:.1f}-{clip.end:.1f}s "
                f"{'scroll' if clip.scroll_strip else clip.effect} → {clip.image.name}"
            )

        if not segments:
            return False

        concat_file = tmp / "concat.txt"
        concat_file.write_text(
            "\n".join(f"file '{segment}'" for segment in segments),
            encoding="utf-8",
        )
        concat_out = tmp / "concat.mp4"
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(concat_out),
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            return False

        return _fit_video_to_duration(concat_out, dest, target_duration)


def get_audio_duration(audio_path: Path) -> float:
    """Return audio duration in seconds using ffprobe, with a conservative fallback."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        try:
            return max(float(result.stdout.strip()), 8.0)
        except ValueError:
            pass
    return 60.0


def _fit_video_to_duration(source: Path, dest: Path, duration: float) -> bool:
    """Trim or pad video so its length exactly matches narration audio."""
    current = get_audio_duration(source)
    if abs(current - duration) < 0.05:
        shutil.copyfile(source, dest)
        return dest.exists() and dest.stat().st_size > 0
    if current < duration:
        pad_seconds = duration - current
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-vf",
                f"tpad=stop_mode=clone:stop_duration={pad_seconds:.3f}",
                "-t",
                f"{duration:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(dest),
            ],
            capture_output=True,
        )
    else:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-t",
                f"{duration:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(dest),
            ],
            capture_output=True,
        )
    return result.returncode == 0 and dest.exists() and dest.stat().st_size > 0


# ---------------------------------------------------------------------------
# 方案 B：edge-tts + ffmpeg 降级
# ---------------------------------------------------------------------------

def generate_with_fallback(
    narration: str,
    output_path: Path,
    script_path: Path,
    tts_engine: str = "auto",
    source_report: Path | None = None,
    audio_file: Path | None = None,
    source_project_limit: int = 10,
    visual_project_limit: int = 5,
) -> bool:
    """降级方案：TTS 生成旁白 + ffmpeg 合成简单视频。

    tts_engine: 'volcengine' / 'edge-tts' / 'auto'
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = Path(tmpdir) / "narration.mp3"
        bg_image = Path(tmpdir) / "bg.jpg"
        bg_video = Path(tmpdir) / "background.mp4"
        silent_video = Path(tmpdir) / "silent.mp4"

        tts_text = narration
        if audio_file:
            if not audio_file.exists():
                print(f"❌ 固定音频不存在: {audio_file}", file=sys.stderr)
                return False
            suffix = audio_file.suffix or ".mp3"
            audio_path = Path(tmpdir) / f"narration{suffix}"
            shutil.copyfile(audio_file, audio_path)
            print(f"🎙️  使用固定音频: {audio_file}")
        elif should_use_placeholder_audio():
            audio_path = Path(tmpdir) / "narration.mp3"
            shutil.copyfile(_PLACEHOLDER_AUDIO, audio_path)
            print(f"🎙️  使用占位音频（MVP 验证）: {_PLACEHOLDER_AUDIO}")
        else:
            print(f"🎙️  TTS 生成旁白（引擎: {tts_engine}）…")
            tts_text = normalize_text_for_tts(narration)
            if not generate_tts(tts_text, audio_path, prefer=tts_engine):
                print("❌ TTS 全部失败", file=sys.stderr)
                return False

        audio_duration = get_audio_duration(audio_path)
        mixed_audio_path = Path(tmpdir) / "narration-mixed.m4a"
        audio_path = mix_optional_background_music(audio_path, audio_duration, mixed_audio_path)
        audio_duration = get_audio_duration(audio_path)
        audio_path = amplify_narration_audio(audio_path, Path(tmpdir))
        audio_duration = get_audio_duration(audio_path)
        timeline = build_media_timeline(
            narration,
            audio_duration,
            timing_text=tts_text,
        )
        ass_path = generate_ass_subtitles(timeline, audio_path.with_suffix(".ass"))
        print(
            "⏱️  时间轴: "
            + ", ".join(
                f"{seg.kind}[{seg.start:.1f}-{seg.end:.1f}s]"
                for seg in timeline
            )
        )

        # --- 2. 创建视频背景 ---
        asset_dir = output_path.parent / "assets" / output_path.stem
        repos = select_visual_repos(
            script_path,
            source_report,
            source_limit=source_project_limit,
            visual_limit=visual_project_limit,
        )
        if repos:
            print(
                "📌 视频素材项目（来自日报 Top "
                f"{source_project_limit}）: {', '.join(repos)}"
            )
        asset_dir.mkdir(parents=True, exist_ok=True)
        ranking_chart = _prepare_daily_ranking_chart(
            source_report,
            script_path,
            asset_dir,
            repos,
        )
        create_github_page_scroll_video(
            repos,
            bg_video,
            timeline,
            asset_dir,
            ranking_chart=ranking_chart,
            source_report=source_report,
            script_path=script_path,
        )

        # --- 3. ffmpeg 合成 ---
        print("🎬 ffmpeg 合成视频…")
        compose_cmd = [
            "ffmpeg", "-y",
            "-i", str(bg_video),
            "-i", str(audio_path),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-t", f"{audio_duration:.3f}",
            str(silent_video),
        ]
        compose = subprocess.run(compose_cmd, capture_output=True)
        if compose.returncode != 0:
            print("❌ ffmpeg 合成失败：", compose.stderr.decode(), file=sys.stderr)
            return False

        # 叠加字幕（如果字幕文件存在且有内容）
        if ass_path.exists() and ass_path.stat().st_size > 0:
            escaped_ass = _escape_ffmpeg_path(ass_path)
            subtitle_result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(silent_video),
                    "-vf", f"ass={escaped_ass}",
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "23",
                    "-c:a", "copy",
                    str(output_path),
                ],
                capture_output=True,
            )
            if subtitle_result.returncode == 0:
                return output_path.exists() and output_path.stat().st_size > 0

        # 字幕叠加失败时直接用无字幕版
        shutil.copy(str(silent_video), str(output_path))
        return output_path.exists() and output_path.stat().st_size > 0


def _create_bg_image(dest: Path, narration: str) -> None:
    """用 ffmpeg 生成带文字的深色背景图。"""
    title_text = "今日 GitHub 热榜 TOP5"
    # 尝试 ffmpeg drawtext（需要中文字体）
    font_candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttf",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ]
    font = next((f for f in font_candidates if Path(f).exists()), "")

    drawtext_filter = (
        f"drawtext=text='{title_text}':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2"
        + (f":fontfile='{font}'" if font else "")
    )

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "color=c=0x1a1a2e:s=1280x720:r=1",
            "-frames:v", "1",
            "-vf", drawtext_filter,
            str(dest),
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        # 最终降级：纯色背景
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", "color=c=0x1a1a2e:s=1280x720:r=1",
                "-frames:v", "1",
                str(dest),
            ],
            capture_output=True,
            check=False,
        )


# ---------------------------------------------------------------------------
# 生成发布指引文档
# ---------------------------------------------------------------------------

def write_publish_guide(script_path: Path, video_path: Path, cover_path: Path) -> Path:
    """基于脚本内容生成小红书发布指引 Markdown。"""
    script_text = script_path.read_text(encoding="utf-8")

    # 提取标题备选
    title_match = re.search(r"### 标题备选.*?\n(.*?)(?=###|$)", script_text, re.DOTALL)
    titles = title_match.group(1).strip() if title_match else "「今日 GitHub TOP5」"

    # 提取标签
    tag_match = re.search(r"### 标签\n(.*?)(?=###|$)", script_text, re.DOTALL)
    tags = tag_match.group(1).strip() if tag_match else "#GitHub #开源 #程序员"

    today = script_path.stem.replace("-video-script", "")
    publish_path = script_path.parent / f"{today}-video-publish.md"

    guide = f"""# 小红书发布指引 — {today}

## 快速发布步骤

1. 打开创作者中心：<https://creator.xiaohongshu.com/publish/publish>
2. 选择「发布视频」
3. 上传视频：`{video_path}`
4. 封面：上传 `{cover_path}`（若不存在则截取视频第 1 帧）
5. 标题：见下方推荐
6. 正文：见下方模板
7. 标签：见下方标签
8. 定时发布推荐：工作日 12:00 或 20:00，周末 10:00 或 15:00

---

## 标题推荐（A/B 任选一）

{titles}

---

## 正文模板

每天给你挑 3 个 GitHub 热榜好项目，今天这三个绝对值得看 👇

（将脚本中三段项目介绍复制到这里）

感兴趣的评论区告诉我，明天继续 ~

{tags}

---

## 文件路径

- 视频：`{video_path}`
- 封面：`{cover_path}`
- 脚本：`{script_path}`
"""

    publish_path.write_text(guide, encoding="utf-8")
    return publish_path


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="GitHub 日报视频生成器")
    parser.add_argument("--script", required=True, help="视频脚本 Markdown 路径")
    parser.add_argument("--output", required=True, help="输出视频路径 (.mp4)")
    parser.add_argument(
        "--engine",
        default="auto",
        choices=["auto", "moneyprinter", "fallback"],
        help="视频引擎：auto/moneyprinter/fallback",
    )
    parser.add_argument(
        "--tts",
        default="auto",
        help=(
            "TTS 引擎（仅 fallback 模式生效）："
            " auto=配置顺序自动探测, volcengine=旧环境变量火山引擎, "
            "edge-tts=edge-tts, 或配置中的 provider 名（如 BYTE_LLM）"
        ),
    )
    parser.add_argument(
        "--moneyprinter-url",
        default="http://localhost:8080",
        help="MoneyPrinterTurbo 服务地址",
    )
    parser.add_argument(
        "--source-report",
        default="",
        help="源日报/周报路径，用于提取 GitHub 仓库并生成真实项目画面",
    )
    parser.add_argument(
        "--source-project-limit",
        type=int,
        default=10,
        help="从源日报中读取的 Trending 项目数量上限，默认 Top 10",
    )
    parser.add_argument(
        "--visual-project-limit",
        type=int,
        default=5,
        help="最终用于视频画面的项目数量，默认 5 个",
    )
    parser.add_argument(
        "--audio-file",
        default="",
        help="固定音频文件路径；传入后跳过 TTS，用该音频直接合成视频",
    )
    args = parser.parse_args()

    script_path = Path(args.script)
    output_path = Path(args.output)
    source_report = Path(args.source_report) if args.source_report else None
    audio_file = Path(args.audio_file) if args.audio_file else None

    if not script_path.exists():
        print(f"❌ 脚本文件不存在: {script_path}", file=sys.stderr)
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 提取口播文本
    narration = extract_narration(script_path)
    if not narration:
        print("❌ 无法从脚本提取口播文本", file=sys.stderr)
        sys.exit(1)

    print(f"📝 口播文本 ({len(narration)} 字)：\n{narration[:120]}…\n")

    # 选择引擎
    success = False
    if args.engine in ("auto", "moneyprinter"):
        print("🚀 尝试 MoneyPrinterTurbo…")
        success = generate_with_moneyprinter(narration, output_path, args.moneyprinter_url)

    if not success and args.engine in ("auto", "fallback"):
        print("⚙️  使用 TTS + ffmpeg + GitHub 页面滚动方案…")
        try:
            success = generate_with_fallback(
                narration,
                output_path,
                script_path=script_path,
                tts_engine=args.tts,
                source_report=source_report,
                audio_file=audio_file,
                source_project_limit=args.source_project_limit,
                visual_project_limit=args.visual_project_limit,
            )
        except VideoRenderError as exc:
            print(f"❌ {exc}", file=sys.stderr)
            success = False

    if not success:
        if output_path.exists() and output_path.stat().st_size == 0:
            output_path.unlink()
        print("❌ 视频生成失败，请检查以上错误信息", file=sys.stderr)
        sys.exit(1)

    if not output_path.exists() or output_path.stat().st_size == 0:
        if output_path.exists():
            output_path.unlink()
        print("❌ 视频生成失败：输出文件为空", file=sys.stderr)
        sys.exit(1)

    print(f"✅ 视频已生成: {output_path}")

    # 封面优先使用日榜排行图，其次截取视频首帧
    cover_path = output_path.with_suffix("").parent / (output_path.stem + "-cover.jpg")
    chart_cover = (
        output_path.parent / "assets" / output_path.stem / "daily-ranking-cover.jpg"
    )
    chart_png = output_path.parent / "assets" / output_path.stem / "daily-ranking-chart.png"
    if chart_cover.exists() and chart_cover.stat().st_size > 0:
        shutil.copyfile(chart_cover, cover_path)
        print(f"🖼️  封面已使用日榜排行图: {cover_path}")
    elif chart_png.exists() and chart_png.stat().st_size > 0:
        shutil.copyfile(chart_png, cover_path.with_suffix(".png"))
        cover_path = cover_path.with_suffix(".png")
        print(f"🖼️  封面已使用日榜排行图: {cover_path}")
    elif extract_cover_frame(output_path, cover_path):
        print(f"🖼️  封面已提取: {cover_path}")
    else:
        print("⚠️  封面提取失败（ffmpeg 未安装？），使用视频文件即可")
        cover_path = output_path  # 降级：用视频截图

    # 生成发布指引
    publish_path = write_publish_guide(script_path, output_path, cover_path)
    print(f"📋 发布指引: {publish_path}")

    # 总结
    print("\n" + "=" * 50)
    print("📦 视频素材包")
    print(f"  视频  : {output_path}")
    print(f"  封面  : {cover_path}")
    print(f"  脚本  : {script_path}")
    print(f"  发布  : {publish_path}")
    print("=" * 50)
    print("\n👉 下一步：打开发布指引，按步骤发布到小红书")


if __name__ == "__main__":
    main()
