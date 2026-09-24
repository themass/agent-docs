#!/usr/bin/env python3
"""Sync Content Studio markdown reports into Open Notebook."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from open_notebook_lib import (
    NOTEBOOK_DESCRIPTIONS,
    build_source_title,
    classify_source,
    collect_markdown_files,
)


@dataclass(frozen=True)
class SyncSummary:
    """Counts returned after syncing sources."""

    created: int = 0
    skipped: int = 0
    failed: int = 0


class OpenNotebookClientProtocol(Protocol):
    """Client surface used by `sync_sources`."""

    def ensure_notebook(self, name: str, description: str) -> str: ...

    def source_exists(self, title: str) -> bool: ...

    def create_text_source(
        self,
        *,
        title: str,
        content: str,
        notebook_ids: list[str],
        embed: bool,
    ) -> str: ...


class OpenNotebookClient:
    """Small urllib client for the Open Notebook local API."""

    def __init__(self, api_url: str, *, timeout: int = 30) -> None:
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self._notebook_cache: dict[str, str] | None = None
        self._source_titles: set[str] | None = None

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> object:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            f"{self.api_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = resp.read()
        if not body:
            return None
        return json.loads(body.decode("utf-8"))

    def _load_notebooks(self) -> dict[str, str]:
        if self._notebook_cache is None:
            payload = self._request("GET", "/api/notebooks")
            notebooks = payload if isinstance(payload, list) else []
            self._notebook_cache = {
                str(item.get("name")): str(item.get("id"))
                for item in notebooks
                if isinstance(item, dict) and item.get("name") and item.get("id")
            }
        return self._notebook_cache

    def ensure_notebook(self, name: str, description: str) -> str:
        notebooks = self._load_notebooks()
        if name in notebooks:
            return notebooks[name]
        payload = self._request(
            "POST",
            "/api/notebooks",
            {"name": name, "description": description},
        )
        if not isinstance(payload, dict) or not payload.get("id"):
            msg = f"Open Notebook did not return an id for notebook {name!r}"
            raise RuntimeError(msg)
        notebook_id = str(payload["id"])
        notebooks[name] = notebook_id
        return notebook_id

    def _load_source_titles(self) -> set[str]:
        if self._source_titles is None:
            payload = self._request("GET", "/api/sources")
            sources = payload if isinstance(payload, list) else []
            self._source_titles = {
                str(item.get("title"))
                for item in sources
                if isinstance(item, dict) and item.get("title")
            }
        return self._source_titles

    def source_exists(self, title: str) -> bool:
        return title in self._load_source_titles()

    def create_text_source(
        self,
        *,
        title: str,
        content: str,
        notebook_ids: list[str],
        embed: bool,
    ) -> str:
        payload = self._request(
            "POST",
            "/api/sources/json",
            {
                "type": "text",
                "title": title,
                "content": content,
                "notebooks": notebook_ids,
                "embed": embed,
                "async_processing": False,
            },
        )
        if not isinstance(payload, dict) or not payload.get("id"):
            msg = f"Open Notebook did not return an id for source {title!r}"
            raise RuntimeError(msg)
        source_id = str(payload["id"])
        if self._source_titles is not None:
            self._source_titles.add(title)
        return source_id


class DirectNotebookClient:
    """Write sources directly via Open Notebook domain models."""

    def __init__(self) -> None:
        from open_notebook.database.repository import repo_query
        from open_notebook.domain.notebook import Notebook, Source

        self._repo_query = repo_query
        self._Notebook = Notebook
        self._Source = Source
        self._notebook_cache: dict[str, str] = {}
        self._source_titles: set[str] | None = None

    async def _load_source_titles(self) -> set[str]:
        if self._source_titles is None:
            rows = await self._repo_query("SELECT title FROM source")
            self._source_titles = {
                str(row.get("title"))
                for row in rows
                if isinstance(row, dict) and row.get("title")
            }
        return self._source_titles

    async def ensure_notebook(self, name: str, description: str) -> str:
        if name in self._notebook_cache:
            return self._notebook_cache[name]
        rows = await self._repo_query(
            "SELECT * FROM notebook WHERE name = $name LIMIT 1",
            {"name": name},
        )
        if rows:
            notebook_id = str(rows[0]["id"])
        else:
            notebook = self._Notebook(name=name, description=description)
            await notebook.save()
            notebook_id = str(notebook.id)
        self._notebook_cache[name] = notebook_id
        return notebook_id

    async def source_exists(self, title: str) -> bool:
        titles = await self._load_source_titles()
        return title in titles

    async def create_text_source(
        self,
        *,
        title: str,
        content: str,
        notebook_ids: list[str],
        embed: bool,
    ) -> str:
        del embed  # Direct import stores full_text immediately; embedding is optional later.
        source = self._Source(title=title, topics=[], full_text=content)
        await source.save()
        for notebook_id in notebook_ids:
            await source.add_to_notebook(notebook_id)
        if self._source_titles is not None:
            self._source_titles.add(title)
        return str(source.id)


def sync_sources(
    client: OpenNotebookClientProtocol,
    files: list[Path],
    *,
    report_root: Path,
    embed: bool,
    dry_run: bool = False,
) -> SyncSummary:
    """Sync markdown files into Open Notebook as text sources."""

    created = 0
    skipped = 0
    failed = 0
    notebook_ids: dict[str, str] = {}

    for path in files:
        title = build_source_title(path, report_root)
        notebooks = classify_source(path, report_root)
        try:
            if client.source_exists(title):
                skipped += 1
                print(f"SKIP existing: {title}")
                continue
            if dry_run:
                created += 1
                print(f"DRY-RUN create: {title} -> {', '.join(notebooks)}")
                continue
            ids = []
            for notebook in notebooks:
                if notebook not in notebook_ids:
                    notebook_ids[notebook] = client.ensure_notebook(
                        notebook,
                        NOTEBOOK_DESCRIPTIONS[notebook],
                    )
                ids.append(notebook_ids[notebook])
            client.create_text_source(
                title=title,
                content=path.read_text(encoding="utf-8", errors="replace"),
                notebook_ids=ids,
                embed=embed,
            )
            created += 1
            print(f"CREATE source: {title}")
        except (OSError, RuntimeError, urllib.error.URLError) as exc:
            failed += 1
            print(f"FAILED source: {title}: {exc}", file=sys.stderr)

    return SyncSummary(created=created, skipped=skipped, failed=failed)


async def sync_sources_direct(
    files: list[Path],
    *,
    report_root: Path,
    embed: bool,
    dry_run: bool = False,
) -> SyncSummary:
    """Sync markdown files using the direct Open Notebook domain backend."""

    client = DirectNotebookClient()
    created = 0
    skipped = 0
    failed = 0
    notebook_ids: dict[str, str] = {}

    for path in files:
        title = build_source_title(path, report_root)
        notebooks = classify_source(path, report_root)
        try:
            if await client.source_exists(title):
                skipped += 1
                print(f"SKIP existing: {title}")
                continue
            if dry_run:
                created += 1
                print(f"DRY-RUN create: {title} -> {', '.join(notebooks)}")
                continue
            ids = []
            for notebook in notebooks:
                if notebook not in notebook_ids:
                    notebook_ids[notebook] = await client.ensure_notebook(
                        notebook,
                        NOTEBOOK_DESCRIPTIONS[notebook],
                    )
                ids.append(notebook_ids[notebook])
            await client.create_text_source(
                title=title,
                content=path.read_text(encoding="utf-8", errors="replace"),
                notebook_ids=ids,
                embed=embed,
            )
            created += 1
            print(f"CREATE source: {title}")
        except (OSError, RuntimeError) as exc:
            failed += 1
            print(f"FAILED source: {title}: {exc}", file=sys.stderr)

    return SyncSummary(created=created, skipped=skipped, failed=failed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-url",
        default=os.getenv("OPEN_NOTEBOOK_API_URL", "http://127.0.0.1:5055"),
        help="Open Notebook API base URL (api backend only).",
    )
    parser.add_argument(
        "--backend",
        choices=["direct", "api"],
        default=os.getenv("OPEN_NOTEBOOK_SYNC_BACKEND", "direct"),
        help="Import backend. direct writes full_text reliably; api uses REST.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("~/.hermes/profiles/content-studio/reports").expanduser(),
        help="Content Studio report directory.",
    )
    parser.add_argument(
        "--include-github-rank",
        action="store_true",
        help="Also import github-daily-rank markdown files.",
    )
    parser.add_argument(
        "--github-rank-dir",
        type=Path,
        default=Path("/Users/gqli/work/deepagents/github-daily-rank"),
        help="github-daily-rank directory used with --include-github-rank.",
    )
    parser.add_argument(
        "--embed",
        action="store_true",
        help="Ask Open Notebook to embed imported text. Requires model/API key setup.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview changes only.")
    parser.add_argument("--limit", type=int, default=0, help="Limit files for smoke tests.")
    args = parser.parse_args()

    roots = [args.report_dir.expanduser()]
    if args.include_github_rank:
        roots.append(args.github_rank_dir.expanduser())
    files = collect_markdown_files(*roots)
    if args.limit > 0:
        files = files[: args.limit]

    if not files:
        print("No markdown files found to sync.")
        return 0

    if args.backend == "direct":
        summary = asyncio.run(
            sync_sources_direct(
                files,
                report_root=args.report_dir.expanduser(),
                embed=args.embed,
                dry_run=args.dry_run,
            )
        )
    else:
        client = OpenNotebookClient(args.api_url)
        summary = sync_sources(
            client,
            files,
            report_root=args.report_dir.expanduser(),
            embed=args.embed,
            dry_run=args.dry_run,
        )

    print(
        "Open Notebook sync summary: "
        f"created={summary.created} skipped={summary.skipped} failed={summary.failed}"
    )
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
