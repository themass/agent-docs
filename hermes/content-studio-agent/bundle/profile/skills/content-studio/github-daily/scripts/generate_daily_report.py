#!/usr/bin/env python3
"""Generate a GitHub Trending daily report from the live Trending page."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


TRENDING_URL = "https://github.com/trending"
SEARCH_URL = "https://api.github.com/search/repositories"
USER_AGENT = "hermes-content-studio/1.0"


@dataclass
class Repo:
    rank: int
    name: str
    url: str
    description: str
    language: str
    stars_today: str
    category: str


def fetch_trending_html() -> str:
    last_error: Exception | None = None
    timeout = int(os.environ.get("CONTENT_STUDIO_FETCH_TIMEOUT", "15"))
    attempts = int(os.environ.get("CONTENT_STUDIO_FETCH_ATTEMPTS", "2"))
    for _ in range(attempts):
        req = urllib.request.Request(
            TRENDING_URL,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Encoding": "identity",
                "Connection": "close",
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except http.client.IncompleteRead as exc:
            last_error = exc
            partial_bytes = getattr(exc, "partial", b"")
            partial = partial_bytes.decode("utf-8", errors="replace")
            if "</article>" in partial:
                return partial
        except OSError as exc:
            last_error = exc
    msg = f"failed to fetch GitHub Trending: {last_error}"
    raise RuntimeError(msg)


def clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("&amp;", "&")
    value = value.replace("&quot;", '"')
    value = value.replace("&#39;", "'")
    return re.sub(r"\s+", " ", value).strip()


def parse_trending(html: str, *, limit: int) -> list[Repo]:
    articles = re.findall(r"<article[^>]*>(.*?)</article>", html, flags=re.DOTALL)
    repos: list[Repo] = []
    seen: set[str] = set()

    for article in articles:
        link = re.search(r'<h2[^>]*>\s*<a[^>]+href="/([^/]+/[^"]+)"', article, flags=re.DOTALL)
        if not link:
            continue
        name = link.group(1).strip()
        if name in seen:
            continue
        seen.add(name)

        desc_match = re.search(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', article, flags=re.DOTALL)
        description = clean_html(desc_match.group(1)) if desc_match else ""

        lang_match = re.search(r'itemprop="programmingLanguage"[^>]*>(.*?)</span>', article, flags=re.DOTALL)
        language = clean_html(lang_match.group(1)) if lang_match else "Unknown"

        today_match = re.search(r"([0-9][0-9,]*)\s+stars today", article, flags=re.IGNORECASE)
        stars_today = f"+{today_match.group(1)}" if today_match else "-"

        repos.append(
            Repo(
                rank=len(repos) + 1,
                name=name,
                url=f"https://github.com/{name}",
                description=description or "暂无描述",
                language=language,
                stars_today=stars_today,
                category=classify(name, description, language),
            )
        )
        if len(repos) >= limit:
            break

    if repos:
        return repos

    # Fallback for minor GitHub HTML changes: use the simpler h2 scan.
    for match in re.finditer(r'<h2[^>]*>\s*<a[^>]+href="/([^/]+/[^"]+)"', html, flags=re.DOTALL):
        name = match.group(1).strip()
        if name in seen:
            continue
        seen.add(name)
        repos.append(
            Repo(
                rank=len(repos) + 1,
                name=name,
                url=f"https://github.com/{name}",
                description="暂无描述",
                language="Unknown",
                stars_today="-",
                category="Other",
            )
        )
        if len(repos) >= limit:
            break
    return repos


def fetch_search_fallback(date: str, *, limit: int) -> list[Repo]:
    """Return a clearly labeled fallback list when GitHub Trending is unavailable."""
    query = urllib.parse.urlencode(
        {
            "q": f"stars:>1000 pushed:>={date}",
            "sort": "stars",
            "order": "desc",
            "per_page": str(limit),
        }
    )
    req = urllib.request.Request(
        f"{SEARCH_URL}?{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    timeout = int(os.environ.get("CONTENT_STUDIO_FETCH_TIMEOUT", "15"))
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))

    repos: list[Repo] = []
    for item in data.get("items", [])[:limit]:
        name = item.get("full_name")
        if not name:
            continue
        description = item.get("description") or "暂无描述"
        language = item.get("language") or "Unknown"
        repos.append(
            Repo(
                rank=len(repos) + 1,
                name=name,
                url=item.get("html_url") or f"https://github.com/{name}",
                description=description,
                language=language,
                stars_today="-",
                category=classify(name, description, language),
            )
        )
    return repos


def classify(name: str, description: str, language: str) -> str:
    text = f"{name} {description} {language}".lower()
    if any(word in text for word in ("agent", "claude", "cursor", "skill", "llm", "ai", "tts", "model")):
        return "AI/Agent"
    if any(word in text for word in ("video", "upload", "social", "short")):
        return "Video/Content"
    if any(word in text for word in ("parser", "markdown", "document", "dev", "plugin", "tool")):
        return "DevTools"
    if any(word in text for word in ("proxy", "clash", "wifi", "network")):
        return "Network"
    if any(word in text for word in ("course", "learn", "build-your-own", "training")):
        return "Learning"
    return "Other"


def weekday_zh(date: str) -> str:
    names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return names[datetime.strptime(date, "%Y-%m-%d").weekday()]


def enrich_with_gh(repo: Repo) -> Repo:
    """Fill missing metadata with `gh repo view` when available."""
    try:
        result = subprocess.run(
            [
                "gh",
                "repo",
                "view",
                repo.name,
                "--json",
                "description,primaryLanguage,repositoryTopics",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return repo
    if result.returncode != 0:
        return repo
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return repo

    description = repo.description
    if not description or description == "暂无描述":
        description = data.get("description") or description
    language = repo.language
    primary = data.get("primaryLanguage") or {}
    if language == "Unknown" and primary.get("name"):
        language = primary["name"]
    return Repo(
        rank=repo.rank,
        name=repo.name,
        url=repo.url,
        description=description or "暂无描述",
        language=language,
        stars_today=repo.stars_today,
        category=classify(repo.name, description or "", language),
    )


def render_report(date: str, repos: list[Repo], *, source: str, degraded: bool) -> str:
    title = "# GitHub Trending 日报（降级）" if degraded else "# GitHub Trending 日报"
    source_line = (
        f"📅 {date}（{weekday_zh(date)}）| 数据源：{source}"
        if degraded
        else f"📅 {date}（{weekday_zh(date)}）| 数据源：[GitHub Trending]({TRENDING_URL})"
    )
    lines: list[str] = [
        title,
        "",
        source_line,
        "",
        "---",
        "",
        "## 一、今日总览",
        "",
        "| # | 项目 | 地址 | 今日新增 | 语言 | 分类 | 一句话简介 |",
        "|---|------|------|----------|------|------|------------|",
    ]
    for repo in repos:
        lines.append(
            f"| {repo.rank} | {repo.name} | {repo.url} | {repo.stars_today} | "
            f"{repo.language} | {repo.category} | {repo.description} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 二、今日要点",
            "",
            f"1. **今日第一名是 {repos[0].name}** — {'这是 GitHub Search 降级结果，不代表 Trending 页面排名。' if degraded else '这是 GitHub Trending 页面当前排在最前的项目，页面顺序为唯一排名依据。'}",
            f"2. **AI/Agent 与内容工具继续占据高位** — Top {len(repos)} 中相关项目数量较多，说明开发者仍在关注自动化、Agent 和内容生产工具。",
            "3. **本报告为降级产物** — GitHub Trending 页面不可达时使用 GitHub Search 维持日报、社区简报和视频流水线不中断。" if degraded else "3. **本报告不使用 GitHub Search 排名** — Search/API 只可补充元数据，不改变 Trending 页面顺序。",
            "",
            "---",
            "",
            "## 三、项目详解",
            "",
        ]
    )
    for repo in repos:
        lines.extend(
            [
                f"### {repo.rank:02d}. {repo.name}",
                "",
                "| 字段 | 内容 |",
                "|---|---|",
                f"| 项目定位 | {repo.description} |",
                f"| GitHub | {repo.url} |",
                f"| 技术栈 | {repo.language} |",
                f"| 今日新增 | {repo.stars_today} |",
                f"| 分类 | {repo.category} |",
                "",
                "**为什么值得看？**",
                "",
                f"> {'该项目来自 GitHub Search 降级列表第' if degraded else '该项目当前位于 GitHub Trending 第'} {repo.rank} 位。建议优先查看 README、Release 和 Issues，判断是否适合继续跟踪或试用。",
                "",
                "---",
                "",
            ]
        )

    counts: dict[str, int] = {}
    for repo in repos:
        counts[repo.category] = counts.get(repo.category, 0) + 1
    lines.extend(["## 四、领域分布", "", "| 领域 | 项目数 |", "|------|--------|"])
    for category, count in sorted(counts.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"| {category} | {count} |")
    lines.extend(
        [
            "",
            "---",
            "",
            "## 五、分析师点评",
            "",
            "> 今日报告因 GitHub Trending 页面不可达而使用 GitHub Search 降级生成。后续社区简报与视频流水线仍必须只从本日报中的项目选择素材，不能引入日报外项目。" if degraded else "> 今日报告严格基于 GitHub Trending 页面顺序生成。后续社区简报与视频流水线必须只从本日报中的项目选择素材，不能引入日报外项目。",
            "",
            "---",
            "",
            "## 六、产物位置",
            "",
            "- 日报文件：`~/.hermes/profiles/content-studio/reports/YYYY/MM/YYYY-MM-DD.md`",
            "- 报告索引：`~/.hermes/profiles/content-studio/reports/index.md`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--report-dir", default="~/.hermes/profiles/content-studio/reports")
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()

    degraded = False
    source = f"[GitHub Trending]({TRENDING_URL})"
    try:
        repos = parse_trending(fetch_trending_html(), limit=args.limit)
    except Exception as exc:
        print(f"warning: GitHub Trending unavailable, using search fallback: {exc}", file=sys.stderr)
        repos = fetch_search_fallback(args.date, limit=args.limit)
        degraded = True
        source = f"[GitHub Search fallback]({SEARCH_URL})"
    if not repos:
        print("failed to build daily report from Trending or fallback", file=sys.stderr)
        return 1
    repos = [enrich_with_gh(repo) for repo in repos]

    year, month, *_ = args.date.split("-")
    root = Path(args.report_dir).expanduser()
    out = root / year / month / f"{args.date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_report(args.date, repos, source=source, degraded=degraded), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
