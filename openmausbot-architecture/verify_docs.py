#!/usr/bin/env python3
"""Read-only checks for the documentation and its pinned local source evidence.

Uses only Python's standard library; does not start OpenMausBot or read live data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent


def check(source_root: Path | None = None) -> dict:
    evidence = json.loads((HERE / "source-evidence.json").read_text())
    source = source_root or (HERE / evidence["source_root_relative"]).resolve()
    errors: list[str] = []
    documents = sorted(HERE.glob("*.md"))
    link_count = diagram_count = anchor_count = 0
    for path in documents:
        text = path.read_text()
        if "## 目录" not in text:
            errors.append(f"{path.name}: missing visible table of contents")
        ids = re.findall(r'<a\s+id="([^"]+)"\s*></a>', text)
        if len(ids) != len(set(ids)):
            errors.append(f"{path.name}: duplicate explicit anchor")
        anchor_count += len(ids)
        fence = None
        visible: list[str] = []
        for number, line in enumerate(text.splitlines(), 1):
            match = re.match(r"^(`{3,}|~{3,})(.*)$", line)
            if match:
                marker, info = match.groups()
                if fence is None:
                    fence = marker
                    if info.strip() == "mermaid":
                        diagram_count += 1
                elif marker[0] == fence[0] and len(marker) >= len(fence):
                    fence = None
                continue
            if fence is None:
                visible.append(line)
        if fence is not None:
            errors.append(f"{path.name}: unclosed code fence")
        for dest in re.findall(r"(?<!!)\[[^\]]+\]\(([^\s)]+)\)", "\n".join(visible)):
            link_count += 1
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", dest):
                continue
            location, _, fragment = unquote(dest).partition("#")
            target = (path.parent / location).resolve() if location else path
            if not target.is_file():
                errors.append(f"{path.name}: missing link target {dest}")
                continue
            if not fragment:
                continue
            if re.fullmatch(r"L\d+", fragment):
                line = int(fragment[1:])
                if not 1 <= line <= len(target.read_text().splitlines()):
                    errors.append(f"{path.name}: invalid source line {dest}")
            elif target.suffix == ".md":
                target_ids = re.findall(r'<a\s+id="([^"]+)"\s*></a>', target.read_text())
                if fragment not in target_ids:
                    errors.append(f"{path.name}: missing explicit anchor {dest}")
    if not source.is_dir():
        errors.append(f"source directory missing: {source}")
    else:
        result = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"], capture_output=True, text=True)
        if result.returncode or result.stdout.strip() != evidence["commit"]:
            errors.append("source HEAD differs from pinned evidence")
        package = source / "package.json"
        if not package.is_file() or json.loads(package.read_text()).get("version") != evidence["version"]:
            errors.append("source package version differs from pinned evidence")
        for record in evidence["files"]:
            path = source / record["path"]
            if not path.is_file():
                errors.append(f"missing source: {record['path']}")
                continue
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != record["sha256"]:
                errors.append(f"source content drift: {record['path']}")
            lines = raw.decode().splitlines()
            for anchor in record["anchors"]:
                index = anchor["line"] - 1
                if not 0 <= index < len(lines) or anchor["match"] not in lines[index]:
                    errors.append(f"source anchor drift: {record['path']}:{anchor['line']}")
    return {
        "ok": not errors,
        "markdown_files": len(documents),
        "links": link_count,
        "explicit_anchors": anchor_count,
        "mermaid_blocks": diagram_count,
        "source_files": len(evidence["files"]),
        "source_anchors": sum(len(r["anchors"]) for r in evidence["files"]),
        "errors": errors,
        "limits": "Static links, fences and source identity only; no Mermaid rendering or runtime verification.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Alternate local OpenMausBot checkout")
    args = parser.parse_args()
    report = check(args.source.resolve() if args.source else None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["ok"] else 1)
