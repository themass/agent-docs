#!/usr/bin/env python3
"""Generate a last30days-powered community brief from a GitHub daily report."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path


class CommunityPulseError(RuntimeError):
    """Raised when the community pulse cannot be generated safely."""


class Project:
    """A GitHub project extracted from the daily report."""

    def __init__(self, *, rank: int, name: str, url: str, repo: str) -> None:
        self.rank = rank
        self.name = name
        self.url = url
        self.repo = repo


_DETAIL_SECTION_PATTERN = re.compile(
    r"###\s+0*(?P<rank>\d+)\.\s+(?P<name>[^\n]+).*?"
    r"\|\s*GitHub\s*\|\s*(?P<url>https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s*\|",
    re.S,
)
_GITHUB_URL_PATTERN = re.compile(r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)")


def _repo_from_url(url: str) -> str:
    match = _GITHUB_URL_PATTERN.search(url)
    if not match:
        msg = f"Not a GitHub repo URL: {url}"
        raise CommunityPulseError(msg)
    return match.group(1).rstrip(").,")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip().lower())
    return slug.strip("-") or "repo"


STABLE_SOURCES: frozenset[str] = frozenset({"hackernews", "polymarket"})


def _source_list(sources: str) -> list[str]:
    return [source.strip() for source in sources.split(",") if source.strip()]


def resolve_effective_sources(raw: str | None = None) -> str:
    """Pick sources for cron/CLI runs, preferring stable endpoints by default.

    Even if the shell exports a broad ``CONTENT_STUDIO_COMMUNITY_SOURCES`` value,
    stable mode keeps only HN + Polymarket unless the caller explicitly opts out
    via ``CONTENT_STUDIO_COMMUNITY_STABLE=0``.
    """

    stable_mode = os.environ.get("CONTENT_STUDIO_COMMUNITY_STABLE", "1") != "0"
    requested = raw or os.environ.get("CONTENT_STUDIO_COMMUNITY_SOURCES") or "hackernews,polymarket"
    parts = _source_list(requested)
    if not stable_mode:
        return ",".join(parts)
    filtered = [source for source in parts if source in STABLE_SOURCES]
    if not filtered:
        filtered = sorted(STABLE_SOURCES)
    return ",".join(filtered)


def extract_daily_top_repos(text: str, *, limit: int) -> list[Project]:
    """Extract the ranked GitHub projects from a daily report."""

    projects: list[Project] = []
    seen: set[str] = set()
    for match in _DETAIL_SECTION_PATTERN.finditer(text):
        url = match.group("url")
        repo = _repo_from_url(url)
        if repo in seen:
            continue
        projects.append(
            Project(
                rank=int(match.group("rank")),
                name=match.group("name").strip(),
                url=url,
                repo=repo,
            )
        )
        seen.add(repo)
        if len(projects) >= limit:
            return projects

    for index, match in enumerate(_GITHUB_URL_PATTERN.finditer(text), start=1):
        repo = match.group(1).rstrip(").,")
        if repo in seen:
            continue
        projects.append(
            Project(
                rank=index,
                name=repo.split("/", 1)[1],
                url=f"https://github.com/{repo}",
                repo=repo,
            )
        )
        seen.add(repo)
        if len(projects) >= limit:
            return projects

    return projects


def resolve_last30days_script(explicit: str | None) -> Path:
    """Find the installed last30days engine script."""

    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    env_script = os.environ.get("LAST30DAYS_SCRIPT")
    if env_script:
        candidates.append(Path(env_script).expanduser())
    home = Path.home()
    profile_dir = os.environ.get("CONTENT_STUDIO_PROFILE_DIR") or os.environ.get("HERMES_HOME")
    candidates.extend(
        [
            home / ".hermes/skills/research/last30days/scripts/last30days.py",
            home / ".hermes/profiles/content-studio/skills/research/last30days/scripts/last30days.py",
            home / "work/deepagents/last30days-skill/skills/last30days/scripts/last30days.py",
            Path("/Users/gqli/work/deepagents/last30days-skill/skills/last30days/scripts/last30days.py"),
        ]
    )
    if profile_dir:
        candidates.append(
            Path(profile_dir).expanduser()
            / "skills/research/last30days/scripts/last30days.py"
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    searched = "\n".join(f"  - {candidate}" for candidate in candidates)
    msg = "last30days engine not found. Install it for Hermes first. Searched:\n" + searched
    raise CommunityPulseError(msg)


def build_last30days_command(
    *,
    python_bin: str,
    last30days_script: Path,
    project: Project,
    raw_dir: Path,
    date: str,
    sources: str = "hackernews,polymarket",
) -> list[str]:
    """Build the fail-fast last30days command for a single GitHub project."""

    repo_name = project.repo.split("/", 1)[1]
    topic = f"{repo_name} GitHub repository"
    plan_path = raw_dir / f"{date}-plan-{_slugify(project.repo)}.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan = {
        "intent": "concept",
        "freshness_mode": "strict_recent",
        "cluster_mode": "none",
        "subqueries": [
            {
                "label": "primary",
                "search_query": f"{repo_name} github repository",
                "ranking_query": f"What are developers saying about the {repo_name} GitHub repository?",
                "sources": _source_list(sources),
                "weight": 1.0,
            }
        ],
    }
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    command = [
        python_bin,
        str(last30days_script),
        topic,
        "--days",
        "30",
        "--search",
        sources,
        "--emit",
        "md",
        "--save-dir",
        str(raw_dir),
        "--save-suffix",
        f"{date}-{_slugify(project.repo)}",
        "--quick",
        "--plan",
        str(plan_path),
    ]
    if "github" in _source_list(sources):
        insert_at = command.index("--search")
        command[insert_at:insert_at] = ["--github-repo", project.repo]
    return command


def _terminate_process_tree(pid: int) -> None:
    """Terminate a timed-out last30days run and any child workers."""

    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return


def run_last30days(command: list[str], *, timeout: int) -> tuple[str, str]:
    """Run last30days and return stdout/stderr, failing loudly on errors."""

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _terminate_process_tree(process.pid)
        stdout, stderr = process.communicate()
        msg = (
            f"last30days timed out after {timeout}s.\n"
            f"command: {' '.join(command)}\n"
            f"partial stdout:\n{stdout[-2000:]}\n"
            f"partial stderr:\n{stderr[-4000:]}"
        )
        raise CommunityPulseError(msg) from exc
    if process.returncode != 0:
        msg = (
            "last30days failed.\n"
            f"command: {' '.join(command)}\n"
            f"exit: {process.returncode}\n"
            f"stderr:\n{stderr}"
        )
        raise CommunityPulseError(msg)
    if not stdout.strip():
        msg = "last30days returned empty output for command: " + " ".join(command)
        raise CommunityPulseError(msg)
    return stdout, stderr


def _excerpt(text: str, *, max_lines: int = 28) -> str:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines[:max_lines])


def render_brief(
    *,
    date: str,
    daily_report: Path,
    projects: list[Project],
    raw_outputs: dict[str, tuple[Path, str]],
    sources: str,
) -> str:
    """Render the final community brief markdown."""

    source_label = " / ".join(_source_list(sources))
    lines = [
        f"# 30 天社区热点简报 — {date}",
        "",
        f"📅 {date} | 数据源：last30days（{source_label}）",
        f"📎 基于日报：`{daily_report}`",
        "",
        "---",
        "",
        "## 今日研究对象",
        "",
        "| # | 项目 | 社区研究原始记录 |",
        "|---|------|------------------|",
    ]
    for project in projects:
        raw_path, _ = raw_outputs[project.repo]
        lines.append(f"| {project.rank} | [{project.repo}]({project.url}) | `{raw_path}` |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 社区在说什么",
            "",
        ]
    )

    for project in projects:
        raw_path, raw_text = raw_outputs[project.repo]
        lines.extend(
            [
                f"### {project.rank:02d}. {project.name}",
                "",
                f"- GitHub: {project.url}",
                f"- 30 天研究主题: `{project.repo.split('/', 1)[1]} GitHub repository`",
                f"- Raw: `{raw_path}`",
                "",
                "#### last30days 摘要摘录",
                "",
                _excerpt(raw_text),
                "",
                "#### 值得跟进",
                "",
                "- 结合上方社区证据，判断这个项目是真需求爆发、短期热梗，还是只在 GitHub 内部升温。",
                "- 若用于视频脚本，优先提取带链接的高赞观点、开发者争议点和可演示场景。",
                "",
                "---",
                "",
            ]
        )

    lines.extend(
        [
            "## 横切结论",
            "",
            "1. 今日 Trending 的社区信号以上方 last30days 原始证据为准，不使用无来源推断。",
            "2. 若某个项目证据较薄，应在后续视频脚本中明确标注「社区讨论尚少」。",
            "3. 本简报可作为视频脚本、周报和知识库索引的上游素材。",
            "",
            f"*Generated by Content Studio community-pulse + last30days @ {date}*",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("daily_report", help="Path to the GitHub daily report.")
    parser.add_argument("output", help="Path to write the community pulse.")
    parser.add_argument("date", help="Report date, YYYY-MM-DD.")
    parser.add_argument("--limit", type=int, default=3, help="Number of daily projects to research.")
    parser.add_argument("--raw-dir", help="Directory for last30days raw outputs.")
    parser.add_argument("--python-bin", default=sys.executable, help="Python executable for last30days.")
    parser.add_argument("--last30days-script", help="Path to last30days.py.")
    parser.add_argument(
        "--sources",
        default=None,
        help="Comma-separated last30days sources. Defaults to stable HN + Polymarket.",
    )
    parser.add_argument("--timeout", type=int, default=180, help="Per-project last30days timeout in seconds.")
    args = parser.parse_args()
    effective_sources = resolve_effective_sources(args.sources)

    daily_report = Path(args.daily_report).expanduser()
    output = Path(args.output).expanduser()
    raw_dir = Path(args.raw_dir).expanduser() if args.raw_dir else output.parent / f"{args.date}-community-pulse-raw"
    if not daily_report.is_file():
        raise CommunityPulseError(f"Daily report not found: {daily_report}")

    projects = extract_daily_top_repos(daily_report.read_text(encoding="utf-8", errors="replace"), limit=args.limit)
    if len(projects) < args.limit:
        msg = f"Expected {args.limit} GitHub projects in daily report, found {len(projects)}."
        raise CommunityPulseError(msg)

    last30days_script = resolve_last30days_script(args.last30days_script)
    raw_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"ℹ️  last30days sources: {effective_sources}", file=sys.stderr)
    raw_outputs: dict[str, tuple[Path, str]] = {}
    for project in projects:
        command = build_last30days_command(
            python_bin=args.python_bin,
            last30days_script=last30days_script,
            project=project,
            raw_dir=raw_dir,
            date=args.date,
            sources=effective_sources,
        )
        print(f"🔎 last30days: {project.repo}", file=sys.stderr)
        stdout, stderr = run_last30days(command, timeout=args.timeout)
        slug = _slugify(project.repo)
        raw_path = raw_dir / f"{args.date}-community-pulse-raw-{slug}.md"
        raw_path.write_text(stdout, encoding="utf-8")
        if stderr.strip():
            (raw_dir / f"{args.date}-community-pulse-raw-{slug}.stderr.log").write_text(stderr, encoding="utf-8")
        raw_outputs[project.repo] = (raw_path, stdout)

    output.write_text(
        render_brief(
            date=args.date,
            daily_report=daily_report,
            projects=projects,
            raw_outputs=raw_outputs,
            sources=effective_sources,
        ),
        encoding="utf-8",
    )
    print(f"✅ community pulse written: {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CommunityPulseError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
