"""Build a daily GitHub Trending ranking chart image from the daily report Markdown."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DailyOverviewRow:
    """One row from the daily report overview table."""

    rank: int
    name: str
    url: str
    stars_today: str
    summary: str
    stars_total: int | None = None
    language: str = ""
    category: str = ""


_OVERVIEW_HEADER = re.compile(r"##\s*一、今日总览")
_TABLE_ROW = re.compile(
    r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*(https://github\.com/[^|]+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|\s*$"
)
_SCRIPT_REPO_LINE = re.compile(
    r"^\d+\.\s+#\d+\s+\[([^\]]+)\]\([^)]+\)(?:\s*[—–-]\s*([^\n]+))?\s*$",
    re.MULTILINE,
)


def _parse_script_repos(script_path: Path) -> list[str]:
    """Return repo slugs from the 入选项目 section in order."""
    if not script_path.is_file():
        return []
    text = script_path.read_text(encoding="utf-8", errors="replace")
    marker = "## 入选项目"
    if marker not in text:
        return []
    section = text.split(marker, 1)[1].split("---", 1)[0]
    repos: list[str] = []
    for match in _SCRIPT_REPO_LINE.finditer(section):
        repos.append(match.group(1).strip())
    return repos


def extract_narration_summaries(script_path: Path) -> dict[str, str]:
    """Extract Chinese one-line summaries from the narration body."""
    if not script_path.is_file():
        return {}

    text = script_path.read_text(encoding="utf-8", errors="replace")
    marker = "## 完整口播文本"
    if marker not in text:
        return {}

    body = text.split(marker, 1)[1].split("---", 1)[0]
    repos = _parse_script_repos(script_path)
    if not repos:
        return {}

    blocks = re.split(r"第[一二三四五12345]个，", body)
    summaries: dict[str, str] = {}
    for repo, block in zip(repos, blocks[1:]):
        sentences = [part.strip() for part in block.split("。") if part.strip()]
        for sentence in sentences[1:]:
            if len(sentence) >= 8:
                summaries[repo.lower()] = sentence
                break
    return summaries


def report_date_from_path(report_path: Path) -> str:
    """Extract YYYY-MM-DD from a daily report filename or content."""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", report_path.stem)
    if match:
        return match.group(1)
    text = report_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"📅\s*(\d{4}-\d{2}-\d{2})", text)
    if match:
        return match.group(1)
    return "today"


def format_chart_title_date(date_str: str) -> str:
    """Format 2026-06-04 as 2026.06.04 for the chart banner."""
    parts = date_str.split("-")
    if len(parts) == 3:
        return ".".join(parts)
    return date_str


def parse_daily_overview_table(report_path: Path, *, limit: int = 10) -> list[DailyOverviewRow]:
    """Parse rows from the daily report overview markdown table."""
    if not report_path.is_file():
        return []

    text = report_path.read_text(encoding="utf-8", errors="replace")
    header = _OVERVIEW_HEADER.search(text)
    if not header:
        return []

    section = text[header.end() :]
    rows: list[DailyOverviewRow] = []
    for line in section.splitlines():
        if line.startswith("## "):
            break
        match = _TABLE_ROW.match(line.strip())
        if not match:
            continue
        rank = int(match.group(1))
        rows.append(
            DailyOverviewRow(
                rank=rank,
                name=match.group(2).strip(),
                url=match.group(3).strip(),
                stars_today=match.group(4).strip(),
                summary=match.group(7).strip(),
                language=match.group(5).strip(),
                category=match.group(6).strip(),
            )
        )
        if len(rows) >= limit:
            break
    return rows


def merge_script_summaries(rows: list[DailyOverviewRow], script_path: Path) -> list[DailyOverviewRow]:
    """Prefer Chinese one-line summaries from the video script when available."""
    if not script_path.is_file():
        return rows

    text = script_path.read_text(encoding="utf-8", errors="replace")
    summaries: dict[str, str] = dict(extract_narration_summaries(script_path))
    for match in _SCRIPT_REPO_LINE.finditer(text):
        repo = match.group(1).strip()
        inline = (match.group(2) or "").strip()
        if inline and inline not in {"--", "-"}:
            summaries[repo.lower()] = inline

    merged: list[DailyOverviewRow] = []
    for row in rows:
        key = row.name.lower()
        summary = summaries.get(key, row.summary)
        merged.append(
            DailyOverviewRow(
                rank=row.rank,
                name=row.name,
                url=row.url,
                stars_today=row.stars_today,
                summary=summary,
                stars_total=row.stars_total,
                language=row.language,
                category=row.category,
            )
        )
    return merged


def enrich_overview_stars(rows: list[DailyOverviewRow]) -> None:
    """Fill total star counts via gh CLI when available."""
    for row in rows:
        try:
            result = subprocess.run(
                ["gh", "api", f"repos/{row.name}", "--jq", ".stargazers_count"],
                capture_output=True,
                text=True,
                timeout=12,
                check=False,
            )
            if result.returncode != 0:
                continue
            row.stars_total = int(result.stdout.strip())
        except (OSError, ValueError, subprocess.TimeoutExpired):
            continue


def _format_stars(count: int | None) -> str:
    if count is None:
        return "-"
    if count >= 1_000_000:
        value = count / 1_000_000
        return f"{value:.1f}M".replace(".0M", "M")
    if count >= 10_000:
        value = count / 1_000
        return f"{value:.1f}k".replace(".0k", "k")
    if count >= 1_000:
        value = count / 1_000
        return f"{value:.1f}k".replace(".0k", "k")
    return str(count)


def _truncate(text: str, max_len: int = 26) -> str:
    """Legacy helper kept for short labels like subtitles."""
    compact = re.sub(r"\s+", " ", text.strip())
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 1] + "…"


def _fit_font_size(
    draw,
    text: str,
    *,
    max_width: int,
    start_size: int,
    min_size: int = 16,
    bold: bool = False,
):
    """Shrink font size until the full text fits without ellipsis."""
    for size in range(start_size, min_size - 1, -1):
        font = _load_font(size, bold=bold)
        width, _ = _text_size(draw, text, font)
        if width <= max_width:
            return font
    return _load_font(min_size, bold=bold)


def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Wrap mixed Chinese/English text by approximate character count."""
    compact = re.sub(r"\s+", " ", text.strip())
    if not compact:
        return []
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


def _text_size(draw, text: str, font) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_centered(draw, xy: tuple[int, int], text: str, font, fill: str) -> None:
    x, y = xy
    width, _ = _text_size(draw, text, font)
    draw.text((x - width / 2, y), text, font=font, fill=fill)


def _draw_gradient_background(image) -> None:
    """Draw a dark blue tech gradient with subtle grid lines."""
    from PIL import ImageDraw

    width, height = image.size
    pixels = image.load()
    top = (4, 20, 43)
    bottom = (2, 8, 25)
    glow = (0, 190, 255)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        for x in range(width):
            radial = max(0.0, 1.0 - (((x - width * 0.55) / 580) ** 2 + ((y - height * 0.20) / 520) ** 2))
            color = tuple(
                int(top[i] * (1 - ratio) + bottom[i] * ratio + glow[i] * radial * 0.10)
                for i in range(3)
            )
            pixels[x, y] = color

    draw = ImageDraw.Draw(image, "RGBA")
    for x in range(80, width, 96):
        draw.line((x, 0, x, height), fill=(75, 166, 255, 18), width=1)
    for y in range(90, height, 96):
        draw.line((0, y, width, y), fill=(75, 166, 255, 16), width=1)
    for x in range(0, width, 24):
        draw.line((x, 0, x, height), fill=(75, 166, 255, 5), width=1)
    for y in range(0, height, 24):
        draw.line((0, y, width, y), fill=(75, 166, 255, 5), width=1)


def _load_font(size: int, *, bold: bool = False):
    from PIL import ImageFont

    candidates = (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    )
    for candidate in candidates:
        if Path(candidate).exists():
            try:
                index = 1 if bold and candidate.endswith(".ttc") else 0
                return ImageFont.truetype(candidate, size, index=index)
            except OSError:
                continue
    return ImageFont.load_default()


def generate_daily_ranking_chart(
    rows: list[DailyOverviewRow],
    *,
    title_date: str,
    featured_repos: set[str],
    dest: Path,
    cover_dest: Path | None = None,
    theme_title: str = "GitHub 热榜",
    theme_subtitle: str = "趋势项目集中爆发",
    theme_tags: list[str] | None = None,
    narrative_chain: list[str] | None = None,
) -> bool:
    """Render a vertical ranking chart PNG (and optional JPG cover)."""
    if not rows:
        return False

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("⚠️  未安装 Pillow，无法生成日榜排行图", file=__import__("sys").stderr)
        return False

    width, height = 1080, 1920
    image = Image.new("RGB", (width, height), "#04142B")
    _draw_gradient_background(image)
    draw = ImageDraw.Draw(image, "RGBA")

    eyebrow_font = _load_font(28)
    title_font = _load_font(72, bold=True)
    subtitle_font = _load_font(34, bold=True)
    row_font = _load_font(28, bold=True)
    small_font = _load_font(23)
    metric_font = _load_font(44, bold=True)
    metric_label_font = _load_font(20)

    featured_lower = {repo.lower() for repo in featured_repos}
    featured = [
        row
        for row in rows
        if row.name.lower() in featured_lower
        or any(repo.endswith(f"/{row.name.lower()}") for repo in featured_lower)
    ]
    display_rows = featured[:5] if len(featured) >= 3 else rows[:5]
    total_growth = 0
    for row in display_rows:
        digits = re.sub(r"[^0-9]", "", row.stars_today)
        if digits:
            total_growth += int(digits)

    draw.text((0, 82), "", font=eyebrow_font)
    title_lines = _wrap_text(theme_title, 12)[:2]
    if not title_lines:
        title_lines = ["GitHub", "热榜"]
    _draw_centered(draw, (width // 2, 90), f"Content Studio · 日榜 #{format_chart_title_date(title_date)}", eyebrow_font, "#8FB7D8")
    if len(title_lines) == 1:
        _draw_centered(draw, (width // 2, 205), title_lines[0], title_font, "#CFF4FF")
    else:
        _draw_centered(draw, (width // 2, 165), title_lines[0], title_font, "#CFF4FF")
        _draw_centered(draw, (width // 2, 248), title_lines[1], title_font, "#22D3EE")
    _draw_centered(draw, (width // 2, 345), _truncate(theme_subtitle, 18), subtitle_font, "#38BDF8")

    card_x, card_y, card_w = 118, 440, 844
    row_h = 78
    featured_lower = {repo.lower() for repo in featured_repos}
    rank_colors = ["#FACC15", "#E5E7EB", "#FB923C", "#38BDF8", "#22C55E"]
    for index, row in enumerate(display_rows):
        y0 = card_y + index * (row_h + 18)
        y1 = y0 + row_h
        highlight = row.name.lower() in featured_lower or any(
            repo.endswith(f"/{row.name.lower()}") for repo in featured_lower
        )
        fill = (5, 21, 48, 220) if highlight else (5, 18, 38, 175)
        outline = (56, 189, 248, 155) if highlight else (56, 189, 248, 62)
        draw.rounded_rectangle((card_x, y0, card_x + card_w, y1), radius=14, fill=fill, outline=outline, width=2)

        badge_color = rank_colors[index % len(rank_colors)]
        badge = f"#{row.rank}"
        draw.rounded_rectangle((card_x + 16, y0 + 18, card_x + 66, y0 + 58), radius=9, fill=badge_color)
        _draw_centered(draw, (card_x + 41, y0 + 25), badge, small_font, "#031226")

        name = row.name.split("/", 1)[-1]
        name_max_width = card_w - 190 - 86
        name_font = _fit_font_size(
            draw,
            name,
            max_width=name_max_width,
            start_size=28,
            min_size=18,
            bold=True,
        )
        draw.text((card_x + 86, y0 + 18), name, font=name_font, fill="#EAF6FF")
        stars = _format_stars(row.stars_total)
        growth = row.stars_today.replace(",", "")
        draw.text((card_x + card_w - 190, y0 + 18), stars, font=small_font, fill="#FACC15")
        draw.text((card_x + card_w - 108, y0 + 18), growth, font=small_font, fill="#34D399")

    theme_y = 910
    theme_lines = _wrap_text(theme_title, 12)[:2] or ["GitHub 热榜", "趋势观察"]
    for index, line in enumerate(theme_lines):
        _draw_centered(draw, (width // 2, theme_y + index * 58), line, subtitle_font, "#22D3EE")

    tag_y = 1055
    tags = (theme_tags or [])[:4] or ["GitHub", "AI Agent", "Workflow", "Open Source"]
    tag_x = 210
    for tag in tags:
        text_w, _ = _text_size(draw, tag, small_font)
        draw.rounded_rectangle((tag_x, tag_y, tag_x + text_w + 34, tag_y + 42), radius=21, fill=(13, 42, 82, 215), outline=(56, 189, 248, 90))
        draw.text((tag_x + 17, tag_y + 8), tag, font=small_font, fill="#BDEBFF")
        tag_x += text_w + 48

    metrics_y = 1185
    metric_items = [
        ("3", "项目上榜"),
        (f"{total_growth // 1000 if total_growth >= 1000 else total_growth}{'K+' if total_growth >= 1000 else '+'}", "日增长"),
        ("趋势", "核心判断"),
    ]
    for index, (value, label) in enumerate(metric_items):
        center_x = 240 + index * 300
        _draw_centered(draw, (center_x, metrics_y), value, metric_font, "#FACC15")
        _draw_centered(draw, (center_x, metrics_y + 58), label, metric_label_font, "#8FB7D8")

    bar_top = 1360
    bar_rows = display_rows[:5]
    max_growth = max(
        1,
        *[int(re.sub(r"[^0-9]", "", row.stars_today) or "0") for row in bar_rows],
    )
    for index, row in enumerate(bar_rows):
        y = bar_top + index * 58
        name = row.name.split("/", 1)[-1]
        bar_name_font = _fit_font_size(
            draw,
            name,
            max_width=175,
            start_size=23,
            min_size=14,
            bold=False,
        )
        growth = int(re.sub(r"[^0-9]", "", row.stars_today) or "0")
        bar_w = int(560 * growth / max_growth)
        draw.text((170, y + 3), name, font=bar_name_font, fill="#BDEBFF")
        draw.rounded_rectangle((360, y, 360 + 560, y + 28), radius=14, fill=(8, 28, 56, 230))
        color = "#FACC15" if index == 0 else "#38BDF8"
        draw.rounded_rectangle((360, y, 360 + bar_w, y + 28), radius=14, fill=color)
        draw.text((360 + min(bar_w + 10, 490), y - 2), row.stars_today.replace(",", ""), font=small_font, fill="#FFFFFF")

    chain = " · ".join((narrative_chain or [])[:3])
    footer = chain or "Content Studio · 趋势分析"
    _draw_centered(draw, (width // 2, height - 118), footer, small_font, "#466B8D")

    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, format="PNG")
    if cover_dest is not None:
        rgb = image.convert("RGB")
        rgb.save(cover_dest, format="JPEG", quality=92)
    return dest.exists() and dest.stat().st_size > 0
