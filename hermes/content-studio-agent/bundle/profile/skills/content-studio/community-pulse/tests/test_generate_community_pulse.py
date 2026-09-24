from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_community_pulse.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("generate_community_pulse", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_extract_daily_top_repos_from_project_detail_sections() -> None:
    module = _load_module()
    text = """
# GitHub 爆火项目日报

### 01. Alpha Tool

| 字段 | 内容 |
|---|---|
| GitHub | https://github.com/acme/alpha |

### 02. Beta Agent

| 字段 | 内容 |
|---|---|
| GitHub | https://github.com/acme/beta |

### 03. Gamma UI

| 字段 | 内容 |
|---|---|
| GitHub | https://github.com/acme/gamma |
"""

    projects = module.extract_daily_top_repos(text, limit=3)

    assert [project.repo for project in projects] == [
        "acme/alpha",
        "acme/beta",
        "acme/gamma",
    ]
    assert projects[0].rank == 1
    assert projects[0].name == "Alpha Tool"


def test_build_last30days_command_targets_github_repo_and_30_day_window(tmp_path: Path) -> None:
    module = _load_module()
    project = module.Project(
        rank=1,
        name="Alpha Tool",
        url="https://github.com/acme/alpha",
        repo="acme/alpha",
    )

    command = module.build_last30days_command(
        python_bin="/usr/bin/python3",
        last30days_script=tmp_path / "last30days.py",
        project=project,
        raw_dir=tmp_path / "raw",
        date="2026-06-08",
    )

    assert command[:2] == ["/usr/bin/python3", str(tmp_path / "last30days.py")]
    assert "alpha GitHub repository" in command
    assert "acme/alpha GitHub open source" not in command
    assert "--days" in command
    assert "30" in command
    assert "--github-repo" not in command
    assert "--search" in command
    assert "hackernews,polymarket" in command
    assert "reddit,hackernews,github,polymarket" not in command
    assert "--quick" in command
    assert "--plan" in command
    plan_path = Path(command[command.index("--plan") + 1])
    assert plan_path.is_file()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["intent"] == "concept"
    assert plan["subqueries"][0]["search_query"] == "alpha github repository"
    assert plan["subqueries"][0]["sources"] == ["hackernews", "polymarket"]
    assert "--emit" in command
    assert "md" in command
    assert "--save-dir" in command
    assert str(tmp_path / "raw") in command


def test_resolve_effective_sources_filters_flaky_sources_in_stable_mode(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setenv("CONTENT_STUDIO_COMMUNITY_SOURCES", "reddit,hackernews,github,polymarket,youtube")
    monkeypatch.setenv("CONTENT_STUDIO_COMMUNITY_STABLE", "1")

    assert module.resolve_effective_sources() == "hackernews,polymarket"


def test_build_last30days_command_includes_github_repo_only_when_requested(tmp_path: Path) -> None:
    module = _load_module()
    project = module.Project(
        rank=1,
        name="Alpha Tool",
        url="https://github.com/acme/alpha",
        repo="acme/alpha",
    )

    stable_command = module.build_last30days_command(
        python_bin="/usr/bin/python3",
        last30days_script=tmp_path / "last30days.py",
        project=project,
        raw_dir=tmp_path / "raw",
        date="2026-06-08",
        sources="hackernews,polymarket",
    )
    github_command = module.build_last30days_command(
        python_bin="/usr/bin/python3",
        last30days_script=tmp_path / "last30days.py",
        project=project,
        raw_dir=tmp_path / "raw-github",
        date="2026-06-08",
        sources="hackernews,github",
    )

    assert "--github-repo" not in stable_command
    assert "--github-repo" in github_command
    assert "acme/alpha" in github_command
