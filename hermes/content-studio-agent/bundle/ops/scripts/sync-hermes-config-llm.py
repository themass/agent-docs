#!/usr/bin/env python3
"""Point Hermes profile config at the local LLM proxy (model + manifest + custom_providers)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to HERMES_HOME/config.yaml")
    parser.add_argument("--base-url", required=True, help="LLM proxy URL, e.g. http://127.0.0.1:3011/v1")
    parser.add_argument("--model", required=True, help="Default model id")
    parser.add_argument(
        "--api-key",
        default="",
        help="If set, update custom_providers[].api_key (TencentDB sk-mem user_key)",
    )
    parser.add_argument(
        "--align-auxiliary",
        action="store_true",
        help="Set auxiliary.*.base_url to --base-url (replaces legacy OpenInspector :8080)",
    )
    args = parser.parse_args()

    path = Path(args.config)
    if not path.is_file():
        print(f"config not found: {path}", file=sys.stderr)
        return 1

    try:
        from ruamel.yaml import YAML
    except ImportError:
        print("ruamel.yaml not installed; skip Hermes config.yaml sync", file=sys.stderr)
        return 0

    yaml = YAML()
    yaml.preserve_quotes = True
    data = yaml.load(path.read_text()) or {}

    model = data.get("model")
    if not isinstance(model, dict):
        model = {}
    model["base_url"] = args.base_url
    model["default"] = args.model
    data["model"] = model

    providers = data.get("providers")
    if isinstance(providers, dict):
        manifest = providers.get("manifest")
        if isinstance(manifest, dict):
            manifest["base_url"] = args.base_url

    custom = data.get("custom_providers")
    if isinstance(custom, list):
        for entry in custom:
            if not isinstance(entry, dict):
                continue
            if entry.get("base_url"):
                entry["base_url"] = args.base_url
            if args.api_key and (entry.get("api_key") or entry.get("base_url")):
                entry["api_key"] = args.api_key

    auxiliary = data.get("auxiliary")
    if isinstance(auxiliary, dict):
        for _task, task_cfg in auxiliary.items():
            if isinstance(task_cfg, dict):
                # Auxiliary calls must use the same MemoryProxy route as the main turn.
                task_cfg["base_url"] = args.base_url

    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh)

    print(f"updated {path} → model.base_url + custom_providers → {args.base_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
