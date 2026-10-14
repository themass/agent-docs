"""Content enrichment for the Web Story page.

Pulls real project facts (GitHub API + README) and, when an OpenAI-compatible
LLM endpoint is reachable (OpenInspector proxy by default), turns them into a
short Chinese introduction per project plus a summary / takeaways block.

Everything degrades gracefully: no network -> report data only, no LLM ->
extractive README digest. Nothing here may raise into the renderer.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

USER_AGENT = "content-studio-web-story/1.0"
README_MAX_CHARS = 14_000
LLM_DIGEST_CHARS = 1_600

CATEGORY_LABELS = {
    "AI/Agent": "AI Agent 工具",
    "DevTools": "开发者工具",
    "Other": "其他方向",
}
CATEGORY_AUDIENCE = {
    "AI/Agent": "正在搭建或使用 AI Agent / 编码助手的开发者",
    "DevTools": "需要提升工程效率的开发者与技术负责人",
    "Other": "关注该方向前沿进展的研究者与创作者",
}


# ── GitHub facts ─────────────────────────────────────────────────────────


def _http_get(url: str, *, accept: str, timeout: float = 20.0) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept": accept}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https host
        return response.read().decode("utf-8", errors="replace")


def fetch_repo_facts(repo: str, cache_dir: Path) -> dict[str, Any]:
    """Return ``{"meta": {...}, "readme": str}``; empty values when unavailable."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{repo.replace('/', '__')}-facts.json"
    if cache_path.is_file():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(cached, dict) and cached.get("meta"):
                return cached
        except (OSError, ValueError):
            pass

    facts: dict[str, Any] = {"meta": {}, "readme": ""}
    try:
        meta = json.loads(
            _http_get(f"https://api.github.com/repos/{repo}", accept="application/vnd.github+json")
        )
        license_info = meta.get("license") or {}
        facts["meta"] = {
            "description": meta.get("description") or "",
            "stars": meta.get("stargazers_count"),
            "forks": meta.get("forks_count"),
            "issues": meta.get("open_issues_count"),
            "language": meta.get("language") or "",
            "license": license_info.get("spdx_id") or license_info.get("name") or "",
            "topics": list(meta.get("topics") or [])[:6],
            "homepage": meta.get("homepage") or "",
            "pushedAt": meta.get("pushed_at") or "",
            "createdAt": meta.get("created_at") or "",
        }
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return facts
    try:
        readme = _http_get(
            f"https://api.github.com/repos/{repo}/readme",
            accept="application/vnd.github.raw",
        )
        facts["readme"] = readme[:README_MAX_CHARS]
    except (urllib.error.URLError, TimeoutError, OSError):
        pass
    try:
        cache_path.write_text(json.dumps(facts, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return facts


def _humanize_count(value: Any) -> str:
    if not isinstance(value, int):
        return ""
    if value >= 1000:
        return f"{value / 1000:.1f}k"
    return str(value)


def _relative_time(iso: str) -> str:
    if not iso:
        return ""
    try:
        moment = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return ""
    days = (datetime.now(timezone.utc) - moment).days
    if days <= 0:
        return "今天更新"
    if days == 1:
        return "昨天更新"
    if days < 30:
        return f"{days} 天前更新"
    if days < 365:
        return f"{days // 30} 个月前更新"
    return f"{days // 365} 年前更新"


# ── README digest (extractive, no LLM) ───────────────────────────────────

_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.MULTILINE)
_FEATURE_HEADING = re.compile(r"feature|highlight|why|what|capabilit|key|overview|特性|功能|亮点|特点|简介", re.I)
_INSTALL_HEADING = re.compile(r"install|quick ?start|getting started|usage|安装|快速开始|使用", re.I)


def _clean_inline(text: str) -> str:
    text = re.sub(r"\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)", "", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[*_`>]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -|:")


def _paragraphs(markdown: str) -> list[str]:
    without_code = _FENCE.sub("\n", markdown)
    blocks = re.split(r"\n\s*\n", without_code)
    result: list[str] = []
    for block in blocks:
        lines = [line for line in block.splitlines() if not line.lstrip().startswith(("#", "|", "- ", "* ", "+ "))]
        cleaned = _clean_inline(" ".join(lines))
        letters = sum(ch.isalpha() or "\u4e00" <= ch <= "\u9fff" for ch in cleaned)
        if len(cleaned) >= 40 and letters > len(cleaned) * 0.6:
            result.append(cleaned)
    return result


def _section_text(markdown: str, pattern: re.Pattern[str]) -> str:
    matches = list(_HEADING.finditer(markdown))
    for index, match in enumerate(matches):
        if pattern.search(match.group(2)):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
            return markdown[match.end() : end]
    return ""


def _list_items(markdown: str, limit: int) -> list[str]:
    items: list[str] = []
    for line in _FENCE.sub("\n", markdown).splitlines():
        match = re.match(r"^\s*(?:[-*+]|\d+\.)\s+(.+)$", line)
        if not match:
            continue
        cleaned = _clean_inline(match.group(1))
        if 8 <= len(cleaned) <= 140:
            items.append(cleaned)
        if len(items) >= limit:
            break
    return items


def digest_readme(readme: str) -> dict[str, Any]:
    """Extractive digest: intro paragraph, feature bullets, quick-start lines."""
    if not readme.strip():
        return {"intro": "", "bullets": [], "quickstart": ""}
    paragraphs = _paragraphs(readme)
    intro = paragraphs[0] if paragraphs else ""
    bullets = _list_items(_section_text(readme, _FEATURE_HEADING), 5) or _list_items(readme, 5)
    quickstart = ""
    install = _section_text(readme, _INSTALL_HEADING)
    code = _FENCE.search(install) if install else None
    if code:
        lines = [line.strip() for line in code.group(1).splitlines() if line.strip() and not line.strip().startswith("#")]
        quickstart = " && ".join(lines[:2])[:120]
    return {"intro": intro[:240], "bullets": [item[:60] for item in bullets], "quickstart": quickstart}


# ── LLM enrichment ───────────────────────────────────────────────────────


def _profile_llm_settings(profile_dir: Path) -> tuple[str, str, str]:
    base = os.environ.get("CONTENT_STUDIO_LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or ""
    model = os.environ.get("CONTENT_STUDIO_LLM_MODEL") or os.environ.get("OPENAI_MODEL") or ""
    key = (
        os.environ.get("CONTENT_STUDIO_LLM_API_KEY")
        or os.environ.get("CUSTOM_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ""
    )
    config = profile_dir / "config.yaml"
    if config.is_file() and (not base or not model):
        text = config.read_text(encoding="utf-8", errors="replace")
        model_block = re.search(r"^model:\s*\n((?:[ \t]+.*\n?)+)", text, re.MULTILINE)
        block = model_block.group(1) if model_block else ""
        if not base:
            found = re.search(r"base_url:\s*(\S+)", block)
            base = found.group(1).strip("\"'") if found else ""
        if not model:
            found = re.search(r"default:\s*(\S+)", block)
            model = found.group(1).strip("\"'") if found else ""
    env_file = profile_dir / ".env"
    if not key and env_file.is_file():
        env_text = env_file.read_text(encoding="utf-8", errors="replace")
        for name in ("CUSTOM_API_KEY", "OPENAI_API_KEY"):
            found = re.search(rf"^{name}=(.+)$", env_text, re.MULTILINE)
            if found:
                key = found.group(1).strip().strip("\"'")
                break
    return base.rstrip("/"), model, key


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text[text.find("{") : text.rfind("}") + 1]
    try:
        data = json.loads(candidate)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def llm_enrich(
    projects: list[dict[str, Any]],
    *,
    date: str,
    profile_dir: Path,
    timeout: float = 150.0,
) -> dict[str, Any] | None:
    """One LLM call for theme + per-project copy + summary. ``None`` on any failure."""
    if os.environ.get("CONTENT_STUDIO_WEB_STORY_SKIP_LLM") == "1":
        return None
    base, model, key = _profile_llm_settings(profile_dir)
    if not base or not model:
        return None

    brief = [
        {
            "repo": item["repo"],
            "rank": item["rank"],
            "category": item.get("category", ""),
            "language": item.get("language", ""),
            "starsToday": item.get("starsToday", ""),
            "stars": item.get("stars", ""),
            "description": item.get("description", ""),
            "topics": item.get("topics", []),
            "readmeIntro": item.get("readmeIntro", "")[:LLM_DIGEST_CHARS],
            "readmeBullets": item.get("readmeBullets", []),
        }
        for item in projects
    ]
    repos = [item["repo"] for item in projects]
    prompt = (
        f"你是技术趋势栏目主编。下面是 {date} GitHub Trending 的 {len(brief)} 个项目资料(JSON)。\n"
        "请只依据资料写作，不要编造功能、数字或链接；资料不足就写得保守。输出严格 JSON，不要任何解释：\n"
        '{"theme":{"title":"≤10字主题","thesis":"≤40字今日判断","tags":["3-4个标签"]},'
        '"projects":{"<repo>":{"role":"≤12字定位","intro":"60-100字中文介绍：它是什么、解决什么问题",'
        '"highlights":["3条，每条≤28字"],"audience":"≤32字适合谁","quickstart":"≤48字怎么上手，无把握留空",'
        '"verdict":"≤30字一句话点评"}},'
        '"summary":{"oneLine":"≤30字总括","takeaways":[{"label":"趋势","text":"≤50字"},'
        '{"label":"机会","text":"≤50字"},{"label":"行动","text":"≤50字"}],'
        '"picks":[{"scenario":"≤14字使用场景","repo":"<repo>","reason":"≤26字"}]}}\n'
        f"projects 的键必须恰好是这些仓库：{json.dumps(repos, ensure_ascii=False)}；picks 给 3-4 条。\n\n"
        f"资料：{json.dumps(brief, ensure_ascii=False)}"
    )
    payload = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "stream": False}
    ).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(f"{base}/chat/completions", data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured proxy
            body = json.loads(response.read().decode("utf-8", errors="replace"))
        content = body["choices"][0]["message"]["content"]
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, IndexError):
        return None
    return _extract_json(content or "")


# ── Assembly with fallbacks ──────────────────────────────────────────────


def _clip(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _fallback_highlights(project: dict[str, Any], digest: dict[str, Any]) -> list[str]:
    if digest["bullets"]:
        return digest["bullets"][:3]
    facts = []
    if project.get("stars"):
        facts.append(f"累计 {project['stars']} Star，今日 {project.get('starsToday', '')}")
    if project.get("language"):
        facts.append(f"主要语言 {project['language']}")
    if project.get("updated"):
        facts.append(project["updated"])
    return facts[:3] or ["暂无更多公开资料"]


def build_project_copy(
    base: dict[str, Any],
    facts: dict[str, Any],
    llm_project: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge report data, GitHub facts and optional LLM copy for one project."""
    meta = facts.get("meta", {}) or {}
    digest = digest_readme(facts.get("readme", ""))
    description = meta.get("description") or base.get("summary", "")
    category = base.get("category", "")
    label = CATEGORY_LABELS.get(category, "热门开源项目")
    llm = llm_project or {}

    highlights_raw = llm.get("highlights")
    highlights = (
        [_clip(item, 40) for item in highlights_raw if str(item).strip()][:3]
        if isinstance(highlights_raw, list)
        else []
    )
    stars_text = _humanize_count(meta.get("stars"))
    updated = _relative_time(meta.get("pushedAt", ""))
    return {
        "role": _clip(llm.get("role"), 16) or label,
        "intro": _clip(llm.get("intro"), 140) or _clip(digest["intro"] or description, 200),
        "highlights": highlights or _fallback_highlights({**base, "stars": stars_text, "updated": updated}, digest),
        "audience": _clip(llm.get("audience"), 40) or CATEGORY_AUDIENCE.get(category, "关注开源动态的开发者"),
        "quickstart": _clip(llm.get("quickstart"), 70) or digest["quickstart"],
        "verdict": _clip(llm.get("verdict"), 40)
        or f"热榜第 {base.get('rank', '-')} 名，今日 {base.get('starsToday', '-')} Star",
        "description": description,
        "stars": stars_text,
        "forks": _humanize_count(meta.get("forks")),
        "license": meta.get("license", ""),
        "updated": updated,
        "topics": meta.get("topics", []),
        "homepage": meta.get("homepage", ""),
        "language": base.get("language") or meta.get("language", ""),
        "readmeIntro": digest["intro"],
        "readmeBullets": digest["bullets"],
    }


def _stars_to_int(text: str) -> int:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else 0


def build_summary(projects: list[dict[str, Any]], llm_summary: dict[str, Any] | None) -> dict[str, Any]:
    """Summary block: one-liner, labelled takeaways, scenario picks, stats."""
    llm = llm_summary or {}
    total_today = sum(_stars_to_int(item.get("starsToday", "")) for item in projects)
    languages: list[str] = []
    for item in projects:
        lang = item.get("language")
        if lang and lang not in languages:
            languages.append(lang)
    categories: dict[str, list[str]] = {}
    for item in projects:
        categories.setdefault(item.get("category") or "Other", []).append(item["shortName"])

    takeaways: list[dict[str, str]] = []
    takeaways_raw = llm.get("takeaways")
    if isinstance(takeaways_raw, list):
        for item in takeaways_raw[:3]:
            if isinstance(item, dict) and item.get("text"):
                takeaways.append({"label": _clip(item.get("label"), 4) or "判断", "text": _clip(item["text"], 80)})
    if len(takeaways) < 3:
        top_cat, names = max(categories.items(), key=lambda pair: len(pair[1]))
        hottest = max(projects, key=lambda item: _stars_to_int(item.get("starsToday", "")))
        defaults = [
            {
                "label": "趋势",
                "text": f"{CATEGORY_LABELS.get(top_cat, top_cat)}占 {len(names)}/{len(projects)} 席：{'、'.join(names[:3])}",
            },
            {
                "label": "机会",
                "text": f"{hottest['shortName']} 今日 {hottest.get('starsToday', '')} Star，增速最快，值得优先关注",
            },
            {
                "label": "行动",
                "text": f"先 Star 并读 {projects[0]['shortName']} 的 README，再挑一个最小场景验证",
            },
        ]
        takeaways = (takeaways + defaults[len(takeaways) :])[:3]

    repos = {item["repo"]: item for item in projects}
    picks: list[dict[str, str]] = []
    picks_raw = llm.get("picks")
    if isinstance(picks_raw, list):
        for item in picks_raw[:4]:
            if isinstance(item, dict) and item.get("repo") in repos:
                picks.append(
                    {
                        "scenario": _clip(item.get("scenario"), 18),
                        "repo": item["repo"],
                        "shortName": repos[item["repo"]]["shortName"],
                        "reason": _clip(item.get("reason"), 40),
                    }
                )
    if not picks:
        picks = [
            {
                "scenario": item.get("role", "")[:14],
                "repo": item["repo"],
                "shortName": item["shortName"],
                "reason": _clip(item.get("verdict", ""), 40),
            }
            for item in projects[:4]
        ]

    return {
        "oneLine": _clip(llm.get("oneLine"), 40)
        or f"今日 Top {len(projects)}：{'、'.join(item['shortName'] for item in projects[:3])} 领跑",
        "takeaways": takeaways,
        "picks": picks,
        "stats": {
            "projects": len(projects),
            "starsToday": f"+{total_today:,}" if total_today else "-",
            "languages": languages[:5],
        },
    }


def build_theme(
    script_theme: dict[str, Any],
    script_is_fallback: bool,
    llm_theme: dict[str, Any] | None,
    projects: list[dict[str, Any]],
) -> dict[str, Any]:
    llm = llm_theme or {}
    tags_raw = llm.get("tags")
    llm_tags = [_clip(tag, 10) for tag in tags_raw if str(tag).strip()][:4] if isinstance(tags_raw, list) else []
    if not script_is_fallback:
        return {
            "title": script_theme.get("title") or _clip(llm.get("title"), 12) or "GitHub 热榜",
            "thesis": script_theme.get("thesis") or _clip(llm.get("thesis"), 50),
            "tags": script_theme.get("tags") or llm_tags,
            "chain": script_theme.get("chain", []),
        }
    categories = [item.get("category") for item in projects if item.get("category")]
    top = max(set(categories), key=categories.count) if categories else ""
    tags = llm_tags or [CATEGORY_LABELS.get(top, "开源"), "GitHub Trending", "今日热榜"]
    return {
        "title": _clip(llm.get("title"), 12) or f"GitHub 热榜 Top {len(projects)}",
        "thesis": _clip(llm.get("thesis"), 50)
        or f"今天的热榜由 {'、'.join(item['shortName'] for item in projects[:3])} 领跑",
        "tags": tags,
        "chain": [],
    }
