"""Repository layout has one owner, and resolving it must not depend on the cwd.

This file exists because of a defect that no amount of reading could catch:
`llm/router.py` computed the server root as `parents[2]` from `src/jc/llm/`, which is
`src/`, not `backend/server/`. Nothing raised. `.env` loading found no file and
returned early, and the routing config was only ever located by the *fallback*
candidate, which happened to be right whenever the process was started from
`backend/server`. Start the server from anywhere else and it raised FileNotFoundError.

So the assertions here are deliberately about identity ("is this the directory called
`server`?") and about behaviour under a changed cwd — never about index arithmetic,
which is what was wrong in the first place.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from jc import paths


def test_roots_are_the_directories_they_claim_to_be() -> None:
    assert paths.SERVER_ROOT.name == "server"
    assert (paths.SERVER_ROOT / "pyproject.toml").is_file()
    assert paths.BACKEND_ROOT.name == "backend"
    assert paths.AGENT_ROOT.name == "agent"
    assert paths.PROMPTS_ROOT.is_dir()
    assert paths.AGENT_ROOT.parent == paths.BACKEND_ROOT
    assert paths.SERVER_ROOT.parent == paths.BACKEND_ROOT


def test_agent_assets_referenced_in_code_actually_exist() -> None:
    """Every asset path below is loaded at import time by some module.

    A missing one degrades silently (empty prompt, no skills) rather than failing, so
    the only place it can be caught is here.
    """
    required = [
        paths.agent_file("llm", "routing.yaml"),
        paths.agent_file("skills", "public"),
        paths.prompt_file("ingest", "jd_parser.md"),
        paths.prompt_file("ingest", "fit_score.md"),
        paths.prompt_file("ingest", "profile_vision.md"),
        paths.prompt_file("ingest", "profile_structurer.md"),
        paths.prompt_file("elevate", "localize.md"),
        paths.prompt_file("coach", "mock_rubric_five_dims.md"),
        paths.prompt_file("coach", "star_followup_templates.md"),
        paths.prompt_file("coach", "industry_followups.yaml"),
    ]
    missing = [str(p) for p in required if not p.exists()]
    assert not missing, "agent assets referenced by code are missing:\n" + "\n".join(missing)


def test_resolve_under_server_ignores_the_working_directory(tmp_path: Path) -> None:
    """The actual regression. `JC_SKILLS_ROOT` and friends default to `../agent/...`.

    Those defaults are written relative to the server root. Resolving them with a bare
    `Path()` makes them relative to wherever the process was launched.
    """
    before = os.getcwd()
    try:
        os.chdir(tmp_path)
        resolved = paths.resolve_under_server("../agent/llm/routing.yaml")
        assert resolved == (paths.AGENT_ROOT / "llm" / "routing.yaml").resolve()
        assert resolved.is_file()
    finally:
        os.chdir(before)


def test_resolve_under_server_leaves_absolute_paths_alone(tmp_path: Path) -> None:
    """Deployments override these settings with absolute paths; those must pass through."""
    target = tmp_path / "routing.yaml"
    target.write_text("{}", encoding="utf-8")
    assert paths.resolve_under_server(target) == target
    assert paths.resolve_under_server(str(target)) == target


def test_llm_router_loads_from_an_unrelated_working_directory(tmp_path: Path) -> None:
    """End to end on the defect: this raised FileNotFoundError from any other cwd."""
    from jc.llm.router import get_llm_router

    get_llm_router.cache_clear()
    before = os.getcwd()
    try:
        os.chdir(tmp_path)
        assert get_llm_router() is not None
    finally:
        os.chdir(before)
        get_llm_router.cache_clear()


def test_skills_are_discoverable_from_an_unrelated_working_directory(tmp_path: Path) -> None:
    from jc.skills import loader

    before = os.getcwd()
    try:
        os.chdir(tmp_path)
        roots = loader._skills_roots()
        assert roots, "no skill roots resolved; skills would silently vanish"
        assert all(r.is_absolute() for r in roots)
    finally:
        os.chdir(before)


def test_layout_knowledge_is_not_recomputed_outside_paths_module() -> None:
    """`parents[...]` walks in `src/jc` belong in `paths.py` only.

    Eleven call sites spelled this out in four different ways and one was off by a
    level. `config.py` keeps its own because `paths.py` must not import settings, and
    the module-level asserts in `paths.py` cover the same index.
    """
    allowed = {"paths.py", "config.py"}
    offenders: list[str] = []
    for path in sorted((paths.SERVER_ROOT / "src" / "jc").rglob("*.py")):
        if path.name in allowed:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "parents[" in line:
                rel = path.relative_to(paths.SERVER_ROOT / "src" / "jc")
                offenders.append(f"{rel}:{number}: {line.strip()}")
    assert not offenders, (
        "resolve paths through jc.paths instead of recomputing them:\n" + "\n".join(offenders)
    )


@pytest.mark.parametrize("name", ["prompt_file", "agent_file"])
def test_helpers_join_without_losing_segments(name: str) -> None:
    helper = getattr(paths, name)
    assert helper("a", "b").parts[-2:] == ("a", "b")
