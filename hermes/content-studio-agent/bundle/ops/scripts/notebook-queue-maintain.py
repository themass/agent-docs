#!/usr/bin/env python3
"""Keep Open Notebook worker queue healthy for podcast generation.

Purges stale ``embed_source`` jobs when embedding is disabled or Ollama is down,
so ``generate_podcast`` commands are not blocked behind hundreds of embed tasks.
"""

from __future__ import annotations

import asyncio
import os
import sys
import urllib.error
import urllib.request

from surrealdb import AsyncSurreal


async def _ollama_up(base_url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=3) as resp:
            return resp.status == 200
    except (OSError, urllib.error.URLError):
        return False


async def maintain() -> int:
    surreal_url = os.getenv("SURREAL_URL", "ws://localhost:8000/rpc")
    surreal_user = os.getenv("SURREAL_USER", "root")
    surreal_password = os.getenv("SURREAL_PASSWORD", "root")
    namespace = os.getenv("SURREAL_NAMESPACE", "open_notebook")
    database = os.getenv("SURREAL_DATABASE", "open_notebook")
    ollama_base = os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434")

    db = AsyncSurreal(surreal_url)
    await db.signin({"username": surreal_user, "password": surreal_password})
    await db.use(namespace, database)

    defaults = await db.query(
        "SELECT default_embedding_model FROM open_notebook:default_models"
    )
    default_embedding = None
    if defaults and isinstance(defaults[0], dict):
        default_embedding = defaults[0].get("default_embedding_model")

    purge_embed = default_embedding is None or not await _ollama_up(ollama_base)
    if not purge_embed:
        print("notebook-queue: embedding enabled and Ollama reachable — no purge")
        return 0

    before = await db.query(
        'SELECT count() AS cnt FROM command WHERE name = "embed_source" GROUP ALL'
    )
    before_cnt = before[0]["cnt"] if before else 0
    if before_cnt:
        await db.query('DELETE command WHERE name = "embed_source"')
        print(f"notebook-queue: purged {before_cnt} embed_source command(s)")

    pending = await db.query(
        'SELECT name, status, count() AS cnt FROM command WHERE status = "new" GROUP BY name, status'
    )
    print(f"notebook-queue: pending new jobs: {pending}")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(maintain()))


if __name__ == "__main__":
    main()
