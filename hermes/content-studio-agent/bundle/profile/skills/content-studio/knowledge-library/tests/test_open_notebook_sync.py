from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module(name: str, script: Path):
    spec = importlib.util.spec_from_file_location(name, script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
SYNC_SCRIPT = SCRIPT_DIR / "open_notebook_sync.py"
QUERY_SCRIPT = SCRIPT_DIR / "open_notebook_query.py"
LIB_SCRIPT = SCRIPT_DIR / "open_notebook_lib.py"


def test_classify_content_studio_report_files(tmp_path: Path) -> None:
    module = _load_module("open_notebook_lib", LIB_SCRIPT)
    report_root = tmp_path / "reports"
    month = report_root / "2026" / "06"
    raw = month / "2026-06-08-community-pulse-raw"
    raw.mkdir(parents=True)

    daily = month / "2026-06-08.md"
    pulse = month / "2026-06-08-community-pulse.md"
    script = month / "2026-06-08-video-script.md"
    raw_item = raw / "2026-06-08-community-pulse-raw-example.md"
    for path in (daily, pulse, script, raw_item):
        path.write_text("# Example\n\nBody", encoding="utf-8")

    assert module.classify_source(daily, report_root) == ["Content Studio Daily"]
    assert module.classify_source(pulse, report_root) == ["Community Pulse"]
    assert module.classify_source(script, report_root) == ["Video Production"]
    assert module.classify_source(raw_item, report_root) == ["Raw Research Archive"]


def test_classify_github_rank_files(tmp_path: Path) -> None:
    module = _load_module("open_notebook_lib", LIB_SCRIPT)
    rank_root = tmp_path / "github-daily-rank"
    report = rank_root / "2026" / "GITHUB_2026_FULL_REPORT.md"
    report.parent.mkdir(parents=True)
    report.write_text("# GitHub 2026 Full Report\n\nBody", encoding="utf-8")

    assert module.classify_source(report, rank_root) == ["GitHub Radar"]


def test_build_source_title_uses_heading_and_relative_date(tmp_path: Path) -> None:
    module = _load_module("open_notebook_lib", LIB_SCRIPT)
    report_root = tmp_path / "reports"
    report = report_root / "2026" / "06" / "2026-06-08-community-pulse.md"
    report.parent.mkdir(parents=True)
    report.write_text("# 社区脉搏简报\n\nBody", encoding="utf-8")

    assert module.build_source_title(report, report_root) == "2026-06-08 · 社区脉搏简报"


class FakeClient:
    def __init__(self) -> None:
        self.notebooks: dict[str, str] = {}
        self.sources: list[dict[str, object]] = []

    def ensure_notebook(self, name: str, description: str) -> str:
        self.notebooks.setdefault(name, f"notebook-{len(self.notebooks) + 1}")
        return self.notebooks[name]

    def source_exists(self, title: str) -> bool:
        return any(source["title"] == title for source in self.sources)

    def create_text_source(
        self,
        *,
        title: str,
        content: str,
        notebook_ids: list[str],
        embed: bool,
    ) -> str:
        source_id = f"source-{len(self.sources) + 1}"
        self.sources.append(
            {
                "id": source_id,
                "title": title,
                "content": content,
                "notebook_ids": notebook_ids,
                "embed": embed,
            }
        )
        return source_id


def test_sync_sources_creates_notebooks_and_skips_existing_titles(tmp_path: Path) -> None:
    module = _load_module("open_notebook_sync", SYNC_SCRIPT)
    report_root = tmp_path / "reports"
    month = report_root / "2026" / "06"
    month.mkdir(parents=True)
    daily = month / "2026-06-08.md"
    daily.write_text("# Daily Report\n\nBody", encoding="utf-8")

    client = FakeClient()
    first = module.sync_sources(client, [daily], report_root=report_root, embed=False)
    second = module.sync_sources(client, [daily], report_root=report_root, embed=False)

    assert first.created == 1
    assert first.skipped == 0
    assert second.created == 0
    assert second.skipped == 1
    assert client.notebooks == {"Content Studio Daily": "notebook-1"}
    assert client.sources[0]["title"] == "2026-06-08 · Daily Report"
    assert client.sources[0]["notebook_ids"] == ["notebook-1"]


def test_query_client_search_payload(monkeypatch) -> None:
    module = _load_module("open_notebook_query", QUERY_SCRIPT)
    captured: dict[str, object] = {}

    class FakeResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def read(self) -> bytes:
            import json

            return json.dumps(self._payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(req, timeout=30):
        captured["path"] = req.full_url
        captured["method"] = req.get_method()
        if req.full_url.endswith("/api/notebooks"):
            return FakeResponse([])
        if req.full_url.endswith("/api/search"):
            import json

            captured["payload"] = json.loads(req.data.decode("utf-8"))
            return FakeResponse({"results": [{"title": "demo", "id": "source:1"}], "total_count": 1})
        raise AssertionError(f"unexpected url: {req.full_url}")

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    client = module.OpenNotebookQueryClient("http://127.0.0.1:5055")
    results = client.search("agent", limit=3)
    assert results[0]["title"] == "demo"
    assert captured["payload"] == {
        "query": "agent",
        "type": "text",
        "limit": 3,
        "search_sources": True,
        "search_notes": True,
    }
