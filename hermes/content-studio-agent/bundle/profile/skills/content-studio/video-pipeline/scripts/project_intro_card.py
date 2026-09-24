"""Render per-project showcase intro cards for the video pipeline."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from daily_ranking_chart import (
    DailyOverviewRow,
    _fit_font_size,
    _load_font,
    _text_size,
    _wrap_text,
    enrich_overview_stars,
    merge_script_summaries,
    parse_daily_overview_table,
    report_date_from_path,
)


@dataclass
class ProjectIntroContext:
    """Visual + copy inputs for one project showcase intro card."""

    repo: str
    rank: int
    language: str
    stars_total: int | None
    stars_today: str
    forks: int | None
    summary: str
    highlights: list[str]
    audience: list[str]
    tagline: str = ""
    one_liner: str = ""
    detail: str = ""
    episode_label: str = ""
    page_label: str = ""


_CATEGORY_AUDIENCE: dict[str, list[str]] = {
    "AI/Agent": ["LLM 应用开发者", "AI 助手开发者", "Agent 工程师"],
    "DevTools": ["全栈开发者", "DevOps 工程师", "技术负责人"],
    "Other": ["开源爱好者", "独立开发者", "技术探索者"],
}

_PROJECT_ENTRY_RE = re.compile(
    r"^\d+\.\s+#(\d+)\s+\[([^\]]+)\]\([^)]+\)\s*[—–-]\s*(.+)$",
    re.MULTILINE,
)


def sanitize_display_text(text: str) -> str:
    """Strip markdown/links so cards never show raw URL fragments."""
    value = (text or "").strip()
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"https?://\S+", "", value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"\1", value)
    value = re.sub(r"[*_`#]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _wrap_text_mixed(text: str, max_chars: int) -> list[str]:
    """Wrap mixed Chinese/English text without breaking ASCII words."""
    compact = sanitize_display_text(text)
    if not compact:
        return []

    lines: list[str] = []
    current = ""
    tokens = re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9][A-Za-z0-9._-]*|[^\s]", compact)
    if not tokens:
        tokens = list(compact)

    for token in tokens:
        candidate = current + token
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = token
    if current:
        lines.append(current)
    return lines


def _split_clauses(text: str) -> list[str]:
    parts = re.split(r"(?<=[。；;！!？?])", sanitize_display_text(text))
    return [part.strip() for part in parts if len(part.strip()) >= 6]


def _episode_label(report_path: Path | None) -> str:
    if report_path and report_path.is_file():
        date_str = report_date_from_path(report_path)
        match = re.search(r"-(\d{2})$", date_str)
        if match:
            return f"第 {int(match.group(1))} 期"
    return "第 1 期"


def _derive_tagline(summary: str, category: str, short_name: str, role: str = "") -> str:
    role_clean = sanitize_display_text(role)
    if role_clean:
        return role_clean[:14]
    compact = sanitize_display_text(summary)
    if category and category != "Other":
        return category.replace("/", " ")[:14]
    if "markdown" in compact.lower() or "md" in short_name.lower():
        return "轻量级文件转 Markdown"
    if "agent" in compact.lower():
        return "AI Agent 工具链"
    if "vector" in compact.lower():
        return "向量检索与索引"
    if "vision" in compact.lower() or "cv" in compact.lower():
        return "计算机视觉工具库"
    words = re.findall(r"[\u4e00-\u9fff]{2,8}", compact)
    if words:
        return words[0][:12]
    return short_name[:12]


def _fetch_repo_extras(repo: str) -> dict[str, str | int]:
    try:
        result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{repo}",
                "--jq",
                "{language: (.language // \"Unknown\"), forks: .forks_count, stars: .stargazers_count, description: (.description // \"\")}",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            return {}
        payload = json.loads(result.stdout or "{}")
        if not isinstance(payload, dict):
            return {}
        return payload
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {}


def _parse_project_script_block(script_path: Path, repo: str) -> dict[str, str]:
    """Parse 入选项目 + 口播段落，返回 role / entry_desc / narration."""
    result = {"role": "", "entry_desc": "", "narration": ""}
    if not script_path.is_file():
        return result

    text = script_path.read_text(encoding="utf-8", errors="replace")
    repo_key = repo.lower()
    short = repo.split("/", 1)[-1].lower()

    if "## 入选项目" in text:
        section = text.split("## 入选项目", 1)[1].split("---", 1)[0]
        for match in _PROJECT_ENTRY_RE.finditer(section):
            matched_repo = match.group(2).strip()
            if matched_repo.lower() != repo_key and short not in matched_repo.lower():
                continue
            body = sanitize_display_text(match.group(3))
            role_match = re.search(r"链上角色[:：]\s*([^。]+)", body)
            if role_match:
                result["role"] = role_match.group(1).strip()
            result["entry_desc"] = body
            break

    if "## 完整口播文本" in text:
        body = text.split("## 完整口播文本", 1)[1].split("---", 1)[0]
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        for paragraph in paragraphs:
            if short in paragraph.lower() or repo_key in paragraph.lower():
                result["narration"] = sanitize_display_text(paragraph)
                break

    return result


def _build_highlights(entry_desc: str, narration: str, summary: str) -> list[str]:
    highlights: list[str] = []
    if entry_desc:
        role_match = re.search(r"链上角色[:：]\s*([^。]+)", entry_desc)
        if role_match:
            highlights.append(role_match.group(1).strip())
        tail = re.sub(r"^.*?链上角色[:：][^。]+。", "", entry_desc).strip()
        if tail:
            highlights.extend(_split_clauses(tail))

    for clause in _split_clauses(narration):
        if clause not in highlights:
            highlights.append(clause)

    if len(highlights) < 3:
        for clause in _split_clauses(summary):
            if clause not in highlights:
                highlights.append(clause)

    cleaned = [sanitize_display_text(item) for item in highlights if sanitize_display_text(item)]
    if len(cleaned) < 3:
        cleaned.extend(
            [
                "GitHub Trending 今日上榜，社区关注度持续走高",
                "README 与示例完整，适合快速试用验证",
                "可作为工具链中的一个模块化组件接入",
            ]
        )
    return cleaned[:5]


def _derive_one_liner(role: str, entry_desc: str, narration: str, summary: str) -> str:
    if role:
        return role
    clauses = _split_clauses(entry_desc)
    for clause in clauses:
        if "链上角色" not in clause and len(clause) >= 8:
            return clause
    narration_clauses = _split_clauses(narration)
    if narration_clauses:
        return narration_clauses[0]
    summary_clauses = _split_clauses(summary)
    if summary_clauses:
        return summary_clauses[0]
    return "GitHub Trending 今日上榜，值得开发者关注"


def _derive_detail(narration: str, entry_desc: str, summary: str) -> str:
    if narration:
        return narration
    if entry_desc:
        return entry_desc
    return sanitize_display_text(summary)


def _audience_for_category(category: str) -> list[str]:
    for key, values in _CATEGORY_AUDIENCE.items():
        if key.lower() in category.lower():
            return values
    return list(_CATEGORY_AUDIENCE["Other"])


def build_project_intro_contexts(
    repos: list[str],
    *,
    report_path: Path | None,
    script_path: Path,
) -> dict[str, ProjectIntroContext]:
    rows: list[DailyOverviewRow] = []
    if report_path and report_path.is_file():
        rows = parse_daily_overview_table(report_path, limit=16)
        rows = merge_script_summaries(rows, script_path)
        enrich_overview_stars(rows)

    by_name = {row.name.lower(): row for row in rows}
    episode = _episode_label(report_path)
    total_pages = 1 + len(repos) * 2 + 1
    contexts: dict[str, ProjectIntroContext] = {}
    for index, repo in enumerate(repos):
        row = by_name.get(repo.lower()) or by_name.get(repo.split("/", 1)[-1].lower())
        extras = _fetch_repo_extras(repo)
        script_block = _parse_project_script_block(script_path, repo)
        raw_summary = row.summary if row else str(extras.get("description") or "")
        summary = sanitize_display_text(raw_summary)
        role = script_block["role"]
        highlights = _build_highlights(script_block["entry_desc"], script_block["narration"], summary)
        category = row.category if row else ""
        audience = _audience_for_category(category)
        short_name = repo.split("/", 1)[-1]
        page_no = 2 + index * 2
        contexts[repo] = ProjectIntroContext(
            repo=repo,
            rank=row.rank if row else index + 1,
            language=str(row.language if row and row.language else extras.get("language") or "Unknown"),
            stars_total=(
                row.stars_total
                if row and row.stars_total
                else int(extras["stars"])
                if isinstance(extras.get("stars"), int)
                else None
            ),
            stars_today=row.stars_today if row else "",
            forks=int(extras["forks"]) if extras.get("forks") is not None else None,
            summary=summary,
            highlights=highlights,
            audience=audience[:3],
            tagline=_derive_tagline(summary, category, short_name, role),
            one_liner=_derive_one_liner(role, script_block["entry_desc"], script_block["narration"], summary),
            detail=_derive_detail(script_block["narration"], script_block["entry_desc"], summary),
            episode_label=episode,
            page_label=f"{page_no:02d} / {total_pages:02d}",
        )
    return contexts


def _draw_showcase_background(image) -> None:
    """White canvas with soft teal corner glows."""
    from PIL import ImageDraw

    width, height = image.size
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            top_right = max(0.0, 1.0 - ((x - width * 0.82) ** 2 + (y - height * 0.12) ** 2) / (420**2))
            bottom_left = max(0.0, 1.0 - ((x - width * 0.18) ** 2 + (y - height * 0.88) ** 2) / (380**2))
            glow = min(1.0, top_right * 0.55 + bottom_left * 0.45)
            base = (255, 255, 255)
            tint = (220, 252, 231)
            color = tuple(int(base[i] * (1 - glow) + tint[i] * glow) for i in range(3))
            pixels[x, y] = color

    draw = ImageDraw.Draw(image, "RGBA")
    draw.rounded_rectangle((36, 36, width - 36, height - 36), radius=28, outline=(226, 232, 240, 180), width=2)


def _draw_stat_pill(
    draw,
    x: int,
    y: int,
    text: str,
    font,
    *,
    fill: tuple[int, int, int, int] = (241, 245, 249, 255),
    text_color: str = "#334155",
) -> int:
    """Draw one rounded stat pill; return width."""
    text_w, _ = _text_size(draw, text, font)
    pad_x, pad_y = 22, 12
    w = text_w + pad_x * 2
    h = _text_size(draw, text, font)[1] + pad_y * 2
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=fill)
    draw.text((x + pad_x, y + pad_y - 2), text, font=font, fill=text_color)
    return w


def _draw_wrapped_block(
    draw,
    x: int,
    y: int,
    max_width: int,
    lines: list[str],
    *,
    font_size: int = 28,
    min_size: int = 22,
    color: str = "#1E293B",
    line_gap: int = 40,
    bold: bool = False,
) -> int:
    """Draw wrapped lines; return next Y."""
    cursor_y = y
    for line in lines:
        font = _fit_font_size(draw, line, max_width=max_width, start_size=font_size, min_size=min_size, bold=bold)
        draw.text((x, cursor_y), line, font=font, fill=color)
        cursor_y += line_gap
    return cursor_y


def generate_project_intro_card(context: ProjectIntroContext, dest: Path) -> bool:
    """Render a premium showcase intro card (GitHub 爆火项目榜 style)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("⚠️  未安装 Pillow，无法生成项目介绍页", file=__import__("sys").stderr)
        return False

    _, short_name = context.repo.split("/", 1)
    width, height = 1080, 1920
    image = Image.new("RGB", (width, height), "#FFFFFF")
    _draw_showcase_background(image)
    draw = ImageDraw.Draw(image, "RGBA")

    margin = 64
    content_w = width - margin * 2

    eyebrow_font = _load_font(24)
    episode_font = _load_font(24, bold=True)
    pill_font = _load_font(24)
    insight_label_font = _load_font(24)
    bullet_font = _load_font(28)
    section_font = _load_font(28, bold=True)
    footer_font = _load_font(22)
    page_font = _load_font(22)

    # Header
    draw.text((margin, 72), "GitHub 爆火项目榜", font=eyebrow_font, fill="#94A3B8")
    episode_text = context.episode_label or "第 1 期"
    ep_w, ep_h = _text_size(draw, episode_text, episode_font)
    ep_x = width - margin - ep_w - 40
    ep_y = 58
    draw.rounded_rectangle(
        (ep_x, ep_y, ep_x + ep_w + 40, ep_y + ep_h + 20),
        radius=24,
        fill=(220, 252, 231, 255),
        outline=(134, 239, 172, 255),
        width=1,
    )
    draw.text((ep_x + 20, ep_y + 8), episode_text, font=episode_font, fill="#15803D")

    # Purple badge
    badge_text = f"#{context.rank} {context.tagline}"
    badge_font = _fit_font_size(draw, badge_text, max_width=content_w, start_size=24, min_size=18, bold=True)
    badge_w, badge_h = _text_size(draw, badge_text, badge_font)
    badge_x, badge_y = margin, 148
    draw.rounded_rectangle(
        (badge_x, badge_y, badge_x + badge_w + 36, badge_y + badge_h + 20),
        radius=14,
        fill=(124, 58, 237, 255),
    )
    draw.text((badge_x + 18, badge_y + 8), badge_text, font=badge_font, fill="#FFFFFF")

    # Hero title
    hero_y = 250
    hero_font = _fit_font_size(draw, short_name, max_width=content_w, start_size=88, min_size=52, bold=True)
    draw.text((margin, hero_y), short_name, font=hero_font, fill="#0F172A")

    # Short description
    desc_y = hero_y + 108
    desc_lines = _wrap_text_mixed(context.summary, 28)[:3]
    desc_y = _draw_wrapped_block(
        draw,
        margin,
        desc_y,
        content_w,
        desc_lines,
        font_size=28,
        min_size=24,
        color="#64748B",
        line_gap=42,
    )

    # Stat pills (two rows if needed)
    pill_y = desc_y + 20
    stars_text = f"{context.stars_total:,} Star" if isinstance(context.stars_total, int) else "- Star"
    growth = context.stars_today or "-"
    if growth and growth != "-" and not growth.startswith("+"):
        growth = f"+{growth}" if growth.replace(",", "").isdigit() else growth
    growth_text = f"{growth} 本周" if growth != "-" else "- 本周"
    forks_text = f"{context.forks:,} Fork" if isinstance(context.forks, int) else "- Fork"
    pills = [context.language or "Unknown", stars_text, growth_text, forks_text]
    cursor_x = margin
    row_y = pill_y
    for pill in pills:
        w = _draw_stat_pill(draw, cursor_x, row_y, pill, pill_font)
        next_x = cursor_x + w + 14
        if next_x > width - margin - 80 and cursor_x > margin:
            row_y += 58
            cursor_x = margin
            w = _draw_stat_pill(draw, cursor_x, row_y, pill, pill_font)
            next_x = cursor_x + w + 14
        cursor_x = next_x

    # 一句话看懂 — dynamic height, up to 3 lines
    box_x, box_y, box_w = margin, row_y + 72, content_w
    insight_lines = _wrap_text_mixed(context.one_liner, 18)[:3]
    box_h = 88 + len(insight_lines) * 46
    draw.rounded_rectangle(
        (box_x, box_y, box_x + box_w, box_y + box_h),
        radius=22,
        fill=(15, 23, 42, 255),
    )
    draw.text((box_x + 28, box_y + 22), "一句话看懂", font=insight_label_font, fill="#94A3B8")
    insight_y = box_y + 64
    for line in insight_lines:
        font = _fit_font_size(draw, line, max_width=box_w - 56, start_size=34, min_size=26, bold=True)
        draw.text((box_x + 28, insight_y), line, font=font, fill="#FFFFFF")
        insight_y += 46

    # Feature bullets — multi-line wrap, up to 4 items
    bullet_y = box_y + box_h + 36
    for highlight in context.highlights[:4]:
        draw.text((margin, bullet_y), "◆", font=bullet_font, fill="#22C55E")
        wrapped = _wrap_text_mixed(highlight, 26)[:2]
        inner_y = bullet_y
        for line in wrapped:
            font = _fit_font_size(draw, line, max_width=content_w - 48, start_size=27, min_size=22)
            draw.text((margin + 36, inner_y), line, font=font, fill="#1E293B")
            inner_y += 38
        bullet_y = inner_y + 14

    # 项目解读 — use remaining vertical space
    detail_y = bullet_y + 10
    draw.text((margin, detail_y), "项目解读", font=section_font, fill="#0F172A")
    detail_y += 42
    detail_lines = _wrap_text_mixed(context.detail, 24)[:5]
    detail_y = _draw_wrapped_block(
        draw,
        margin,
        detail_y,
        content_w,
        detail_lines,
        font_size=26,
        min_size=22,
        color="#475569",
        line_gap=38,
    )

    # 适合谁？
    aud_y = min(detail_y + 28, height - 250)
    aud_h = 108
    draw.rounded_rectangle(
        (margin, aud_y, width - margin, aud_y + aud_h),
        radius=18,
        fill=(240, 253, 244, 255),
        outline=(134, 239, 172, 255),
        width=2,
    )
    draw.text((margin + 24, aud_y + 18), "适合谁？", font=section_font, fill="#15803D")
    audience_lines = _wrap_text_mixed("、".join(context.audience), 22)[:2]
    aud_inner_y = aud_y + 56
    for line in audience_lines:
        font = _fit_font_size(draw, line, max_width=content_w - 48, start_size=24, min_size=20)
        draw.text((margin + 24, aud_inner_y), line, font=font, fill="#14532D")
        aud_inner_y += 34

    url = f"https://github.com/{context.repo}"
    draw.text((margin, height - 96), url, font=footer_font, fill="#94A3B8")
    if context.page_label:
        page_w, _ = _text_size(draw, context.page_label, page_font)
        draw.text((width - margin - page_w, height - 96), context.page_label, font=page_font, fill="#94A3B8")

    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, format="PNG")
    return dest.exists() and dest.stat().st_size > 0
