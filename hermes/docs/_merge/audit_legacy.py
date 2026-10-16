#!/usr/bin/env python3
"""Validate reviewed legacy docs, not every historical code excerpt or runtime behavior."""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from collections import Counter

from verify_volumes import HTML_ID, anchors, check_links, outside_fences

DOCS = Path(__file__).resolve().parents[1]
LEGACY = DOCS / 'archive' / 'legacy'
DEFAULT_SOURCE = DOCS.parents[2] / 'hermes-dev' / 'hermes-agent'


def check_outline(text: str) -> list[str]:
    """Check visible navigation and Markdown hierarchy, excluding code samples."""
    errors = []
    plain, _ = outside_fences(text)
    headings = re.findall(r'^(#{1,6})\s+(.+)$', plain, re.M)
    if sum(level == '#' for level, _ in headings) != 1:
        errors.append('expected exactly one document H1')
    if sum(level == '##' and title == '目录' for level, title in headings) != 1:
        errors.append('expected exactly one visible H2 directory')
    if '<summary>章节目录' in plain:
        errors.append('generated directory must not be collapsed')
    if plain.count('<!-- visible-toc:start -->') != 1 or plain.count('<!-- visible-toc:end -->') != 1:
        errors.append('expected one bounded visible directory')
    else:
        toc = plain.split('<!-- visible-toc:start -->', 1)[1].split('<!-- visible-toc:end -->', 1)[0]
        if not re.search(r'^- \[.+\]\(#.+\)$', toc, re.M):
            errors.append('visible directory contains no chapter links')
        # Chapter/section entries must cover all actual H2/H3 titles, not a stale snapshot.
        for level, title in headings:
            if level in ('##', '###') and title != '目录' and f'[{title}](' not in toc:
                errors.append(f'directory missing chapter: {title}')
    previous = 0
    for level, title in headings:
        if len(level) > previous + 1:
            errors.append(f'heading level skipped: {title}')
        previous = len(level)
    duplicate = [key for key, count in Counter(HTML_ID.findall(plain)).items() if count > 1]
    if duplicate:
        errors.append(f'duplicate explicit anchors: {duplicate}')
    return errors


def mermaid_blocks(text: str) -> Counter:
    """Collect diagram payloads across moved chapters; ignore only trailing whitespace."""
    blocks = Counter()
    active = None
    kind = ''
    body = []
    for line in text.splitlines():
        match = re.match(r'^\s*(`{3,}|~{3,})(.*)$', line)
        if match:
            marker, info = match.groups()
            if active is None:
                active, kind, body = marker, info.strip(), []
            elif marker[0] == active[0] and len(marker) >= len(active) and not info.strip():
                if kind == 'mermaid':
                    blocks['\n'.join(part.rstrip() for part in body)] += 1
                active = None
            else:
                body.append(line)
        elif active is not None:
            body.append(line)
    return blocks


def audit(source: Path, baseline: Path | None = None, preserve_diagrams: bool = False) -> list[str]:
    errors = []
    files = sorted(LEGACY.rglob('*.md'))
    diagrams = 0
    current_diagrams = Counter()
    for path in files:
        text = path.read_text()
        try:
            _, n = outside_fences(text)
            diagrams += n
            current_diagrams.update(mermaid_blocks(text))
            errors.extend(check_links(path, text))
            errors.extend(f'{path.name}: {error}' for error in check_outline(text))
            if baseline and (old := baseline / path.relative_to(LEGACY)).is_file():
                lost = anchors(old.read_text()) - anchors(text)
                if lost:
                    errors.append(f'{path.name}: lost old anchors {sorted(lost)}')
        except ValueError as exc:
            errors.append(f'{path.name}: {exc}')
    if baseline and preserve_diagrams:
        old_diagrams = Counter()
        for old_path in baseline.rglob('*.md'):
            old_diagrams.update(mermaid_blocks(old_path.read_text()))
        missing = old_diagrams - current_diagrams
        if missing:
            errors.append(f'{sum(missing.values())} baseline Mermaid diagrams removed or changed')
    manifest = json.loads((LEGACY / 'SOURCE_REVIEW.json').read_text())
    symbols = 0
    for item in manifest['source_checks']:
        path = source / item['path']
        if not path.is_file():
            errors.append(f'Missing source {item["path"]}')
            continue
        tree = ast.parse(path.read_text())
        names = {n.name for n in ast.walk(tree)
                 if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))}
        for symbol in item['symbols']:
            if symbol not in names:
                errors.append(f'{item["path"]}: missing symbol {symbol}')
            symbols += 1
    # Narrow ownership checks prevent a same-named function elsewhere passing as a method.
    for rel, cls, method in manifest['method_owners']:
        tree = ast.parse((source / rel).read_text())
        owners = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls]
        if not owners or not any(
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method
            for n in owners[0].body
        ):
            errors.append(f'{rel}: missing method {cls}.{method}')
    if errors:
        for error in errors:
            print(f'ERROR: {error}', file=sys.stderr)
    else:
        print(f'PASS: {len(files)} legacy Markdown files; {diagrams} Mermaid fences; '
              f'{len(manifest["source_checks"])} source files; {symbols} symbols; '
              f'{len(manifest["method_owners"])} method owners')
        if baseline:
            print('PASS: old heading anchors preserved against supplied baseline')
            if preserve_diagrams:
                print('PASS: baseline Mermaid payloads preserved across chapter moves')
    try:
        head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
        if head != manifest['source_commit']:
            print(f'NOTICE: HEAD {head} differs from reviewed {manifest["source_commit"]}; re-review semantics')
    except subprocess.CalledProcessError:
        print('NOTICE: source git identity unavailable')
    print('LIMIT: symbol/structure audit only; not historical excerpt equivalence, Mermaid rendering, or runtime tests')
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--preserve-diagrams', action='store_true',
                        help='Require baseline diagrams unchanged; use for outline-only reorganization')
    args = parser.parse_args()
    return int(bool(audit(args.source_root, args.baseline, args.preserve_diagrams)))


if __name__ == '__main__':
    raise SystemExit(main())
