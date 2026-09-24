#!/usr/bin/env python3
"""Query Open Notebook from Hermes Content Studio."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class OpenNotebookQueryClient:
    """Read-only urllib client for the Open Notebook local API."""

    def __init__(self, api_url: str, *, timeout: int = 30) -> None:
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout

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

    def health_ok(self) -> bool:
        try:
            self._request("GET", "/api/notebooks")
            return True
        except (OSError, urllib.error.URLError, urllib.error.HTTPError):
            return False

    def list_notebooks(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/api/notebooks")
        return payload if isinstance(payload, list) else []

    def list_sources(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            f"/api/sources?limit={limit}&offset={offset}",
        )
        return payload if isinstance(payload, list) else []

    def list_all_sources(self) -> list[dict[str, Any]]:
        all_sources: list[dict[str, Any]] = []
        offset = 0
        page_size = 100
        while True:
            page = self.list_sources(limit=page_size, offset=offset)
            if not page:
                break
            all_sources.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
        return all_sources

    def get_source(self, source_id: str) -> dict[str, Any]:
        encoded = urllib.parse.quote(source_id, safe="")
        payload = self._request("GET", f"/api/sources/{encoded}")
        if not isinstance(payload, dict):
            msg = f"Open Notebook returned unexpected payload for source {source_id!r}"
            raise RuntimeError(msg)
        return payload

    def search(
        self,
        query: str,
        *,
        search_type: str = "text",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        payload = self._request(
            "POST",
            "/api/search",
            {
                "query": query,
                "type": search_type,
                "limit": limit,
                "search_sources": True,
                "search_notes": True,
            },
        )
        if not isinstance(payload, dict):
            return []
        results = payload.get("results")
        return results if isinstance(results, list) else []

    def find_source_by_title(self, title: str) -> dict[str, Any] | None:
        needle = title.strip().lower()
        for source in self.list_all_sources():
            current = str(source.get("title") or "").strip().lower()
            if current == needle or needle in current:
                return source
        return None


def _resolve_source(client: OpenNotebookQueryClient, ref: str) -> dict[str, Any]:
    if ref.startswith("source:"):
        return client.get_source(ref)
    match = client.find_source_by_title(ref)
    if match and match.get("id"):
        return client.get_source(str(match["id"]))
    msg = f"No Open Notebook source matched {ref!r}"
    raise RuntimeError(msg)


def _print_search_results(results: list[dict[str, Any]], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return
    if not results:
        print("No matches.")
        return
    for index, item in enumerate(results, start=1):
        title = item.get("title") or item.get("parent_id") or "untitled"
        source_id = item.get("id") or item.get("parent_id") or ""
        score = item.get("score")
        score_text = f" score={score}" if score is not None else ""
        print(f"{index}. {title}{score_text}")
        if source_id:
            print(f"   id: {source_id}")


def _print_source_detail(source: dict[str, Any], *, preview_chars: int, as_json: bool) -> None:
    if as_json:
        print(json.dumps(source, ensure_ascii=False, indent=2))
        return
    title = source.get("title") or "untitled"
    source_id = source.get("id") or ""
    text = source.get("full_text") or ""
    print(f"title: {title}")
    print(f"id: {source_id}")
    print(f"full_text_len: {len(text)}")
    if text:
        preview = text[:preview_chars].replace("\n", " ")
        print(f"preview: {preview}")


def _print_notebooks(client: OpenNotebookQueryClient, *, as_json: bool) -> None:
    notebooks = client.list_notebooks()
    if as_json:
        print(json.dumps(notebooks, ensure_ascii=False, indent=2))
        return
    if not notebooks:
        print("No notebooks.")
        return
    for notebook in notebooks:
        name = notebook.get("name") or "untitled"
        notebook_id = notebook.get("id") or ""
        print(f"- {name} ({notebook_id})")


def load_direct_stats(open_notebook_root: Path) -> dict[str, int] | None:
    """Load accurate counts from Open Notebook DB when local source tree is available."""

    import subprocess

    if not open_notebook_root.is_dir():
        return None

    script = """
import asyncio
import json

async def main() -> None:
    from open_notebook.database.repository import repo_query

    total_rows = await repo_query("SELECT count() AS count FROM source GROUP ALL")
    empty_rows = await repo_query(
        "SELECT count() AS count FROM source "
        "WHERE full_text IS NONE OR string::trim(full_text) = '' GROUP ALL"
    )
    notebook_rows = await repo_query("SELECT count() AS count FROM notebook GROUP ALL")
    print(
        json.dumps(
            {
                "sources": int(total_rows[0]["count"]) if total_rows else 0,
                "empty_sources": int(empty_rows[0]["count"]) if empty_rows else 0,
                "notebooks": int(notebook_rows[0]["count"]) if notebook_rows else 0,
            },
            ensure_ascii=False,
        )
    )

asyncio.run(main())
"""
    try:
        completed = subprocess.run(
            ["uv", "run", "--env-file", ".env", "python", "-c", script],
            cwd=open_notebook_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    line = completed.stdout.strip().splitlines()[-1]
    payload = json.loads(line)
    if not isinstance(payload, dict):
        return None
    return {
        "sources": int(payload.get("sources", 0)),
        "empty_sources": int(payload.get("empty_sources", 0)),
        "notebooks": int(payload.get("notebooks", 0)),
    }


def _print_stats(
    client: OpenNotebookQueryClient,
    *,
    as_json: bool,
    open_notebook_root: Path | None,
) -> None:
    direct = load_direct_stats(open_notebook_root) if open_notebook_root else None
    if direct is None:
        sources = client.list_all_sources()
        stats = {
            "api_url": client.api_url,
            "notebooks": len(client.list_notebooks()),
            "sources": len(sources),
            "empty_sources": None,
            "stats_mode": "api_paginated",
        }
    else:
        stats = {
            "api_url": client.api_url,
            "notebooks": direct["notebooks"],
            "sources": direct["sources"],
            "empty_sources": direct["empty_sources"],
            "stats_mode": "direct_db",
        }
    if as_json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return
    print(f"api: {stats['api_url']}")
    print(f"mode: {stats['stats_mode']}")
    print(f"notebooks: {stats['notebooks']}")
    print(f"sources: {stats['sources']}")
    if stats["empty_sources"] is None:
        print("empty_sources: n/a (use direct_db mode via OPEN_NOTEBOOK_ROOT)")
    else:
        print(f"empty_sources: {stats['empty_sources']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-url",
        default=os.getenv("OPEN_NOTEBOOK_API_URL", "http://127.0.0.1:5055"),
        help="Open Notebook API base URL.",
    )
    parser.add_argument(
        "--open-notebook-root",
        type=Path,
        default=Path(
            os.getenv("OPEN_NOTEBOOK_ROOT", "/Users/gqli/work/deepagents/open-notebook")
        ).expanduser(),
        help="Open Notebook source tree for direct_db stats.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Search the knowledge base.")
    search_parser.add_argument("query", help="Search query.")
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument(
        "--type",
        choices=["text", "vector"],
        default="text",
        help="Search mode. Vector search requires embedding model setup.",
    )

    get_parser = subparsers.add_parser("get", help="Fetch one source by id or title.")
    get_parser.add_argument("ref", help="source:id or title substring.")
    get_parser.add_argument("--preview-chars", type=int, default=500)

    subparsers.add_parser("notebooks", help="List Open Notebook notebooks.")
    subparsers.add_parser("stats", help="Show source/notebook counts.")

    args = parser.parse_args()
    client = OpenNotebookQueryClient(args.api_url)
    if not client.health_ok():
        print(
            f"Open Notebook API is unavailable at {args.api_url}. "
            "Start the API first.",
            file=sys.stderr,
        )
        return 2

    try:
        if args.command == "search":
            results = client.search(
                args.query,
                search_type=args.type,
                limit=args.limit,
            )
            _print_search_results(results, as_json=args.json)
            return 0
        if args.command == "get":
            source = _resolve_source(client, args.ref)
            _print_source_detail(
                source,
                preview_chars=args.preview_chars,
                as_json=args.json,
            )
            return 0
        if args.command == "notebooks":
            _print_notebooks(client, as_json=args.json)
            return 0
        if args.command == "stats":
            _print_stats(
                client,
                as_json=args.json,
                open_notebook_root=args.open_notebook_root,
            )
            return 0
    except (RuntimeError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"Open Notebook query failed: {exc}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
