#!/usr/bin/env python3
"""Sync MoneyPrinterTurbo LLM settings from Content Studio secrets."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import toml
except ImportError:
    print("toml package required (install in MPT venv or deepagents venv)", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to MoneyPrinterTurbo config.toml")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--base-url", required=True, help="OpenAI-compatible base URL (e.g. proxy /v1)")
    parser.add_argument("--model", default="", help="openai_model_name (e.g. gpt-5-6-luna)")
    args = parser.parse_args()

    path = Path(args.config).expanduser()
    if not path.is_file():
        print(f"config not found: {path}", file=sys.stderr)
        return 1

    data = toml.load(path)
    app = data.setdefault("app", {})
    app["llm_provider"] = app.get("llm_provider") or "openai"
    app["openai_api_key"] = args.api_key
    app["openai_base_url"] = args.base_url.rstrip("/")
    if args.model.strip():
        app["openai_model_name"] = args.model.strip()

    with path.open("w", encoding="utf-8") as fh:
        toml.dump(data, fh)
    model_note = f", openai_model_name={app.get('openai_model_name')}" if args.model.strip() else ""
    print(f"updated {path} openai_api_key + openai_base_url={app['openai_base_url']}{model_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
