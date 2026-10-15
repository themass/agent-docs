#!/usr/bin/env python3
"""Check additive documentation structure and local references. No Mermaid rendering."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

from audit_source import ADDED_SECTIONS, DOCS, NEW_DOCS, VOLUMES, added_documents

FENCE = re.compile(r'^\s*(`{3,}|~{3,})(.*)$')
LINK = re.compile(r'(?<!!)\[[^\]\n]+\]\(([^\s)]+)(?:\s+"[^"\n]*")?\)')
HTML_ID = re.compile(r'<a\s+id=["\']([^"\']+)["\']')
SUPPLEMENT = '<a id="source-supplement"></a>'


def outside_fences(text: str) -> tuple[str, int]:
    lines = []
    active = None
    diagrams = 0
    for number, line in enumerate(text.splitlines(), 1):
        match = FENCE.match(line)
        if match:
            marker, info = match.groups()
            if active is None:
                active = marker
                diagrams += int(info.strip() == 'mermaid')
            elif marker[0] == active[0] and len(marker) >= len(active) and not info.strip():
                active = None
            else:
                continue
            continue
        if active is None:
            lines.append(line)
    if active is not None:
        raise ValueError('Unclosed Markdown fence')
    return '\n'.join(lines), diagrams


def heading_slug(text: str) -> str:
    text = text.lower().replace('`', '')
    text = ''.join(c for c in text if c in {'-', '_', ' '} or not unicodedata.category(c).startswith('P'))
    return text.strip().replace(' ', '-')


def anchors(text: str) -> set[str]:
    plain, _ = outside_fences(text)
    found = set(HTML_ID.findall(plain))
    counts = {}
    for line in plain.splitlines():
        match = re.match(r'^#{1,6}\s+(.+)$', line)
        if match:
            slug = heading_slug(match.group(1))
            count = counts.get(slug, 0)
            found.add(slug + (f'-{count}' if count else ''))
            counts[slug] = count + 1
    return found


def check_links(path: Path, text: str) -> list[str]:
    plain, _ = outside_fences(text)
    errors = []
    for target in LINK.findall(plain):
        if re.match(r'^[a-zA-Z][\w+.-]*:', target):
            continue
        rel, _, anchor = target.partition('#')
        dest = (path.parent / rel).resolve() if rel else path
        if not dest.is_file():
            errors.append(f'{path.name}: missing link target {target}')
        elif anchor and dest.suffix == '.md' and anchor not in anchors(dest.read_text()):
            errors.append(f'{path.name}: missing anchor {target}')
    return errors


def without_reviewed_insertions(relative_path: str, payload: bytes) -> bytes:
    """Only volume 03 has explicitly bounded in-chapter/TOC insertions; old bytes stay ordered."""
    if relative_path != 'volumes/03-runtime-session-and-loop.md':
        return payload
    for name in ('compression-toc', 'compression-detail'):
        start = f'<!-- {name}:start -->'.encode()
        end = f'<!-- {name}:end -->'.encode()
        if start not in payload and end not in payload:
            continue
        if payload.count(start) != 1 or payload.count(end) != 1:
            raise ValueError(f'Missing or duplicated bounded insertion: {name}')
        before, remainder = payload.split(start, 1)
        if end not in remainder:
            raise ValueError(f'Reversed bounded insertion: {name}')
        _, after = remainder.split(end, 1)
        if not after.startswith(b'\n'):
            raise ValueError(f'Missing bounded insertion newline: {name}')
        payload = before + after[1:]
    return payload


def preservation(baseline: Path) -> list[str]:
    errors = []
    before = json.loads((baseline / 'baseline.json').read_text())
    for rel, meta in before.items():
        old = (baseline / rel).read_bytes()
        now = DOCS / rel
        if hashlib.sha256(old).hexdigest() != meta['sha256']:
            errors.append(f'Corrupt verification baseline: {rel}')
        elif not now.is_file():
            errors.append(f'Original file is missing: {rel}')
        else:
            try:
                retained = without_reviewed_insertions(rel, now.read_bytes())
                if not retained.startswith(old):
                    errors.append(f'Original bytes changed outside reviewed additions: {rel}')
            except ValueError as exc:
                errors.append(f'{rel}: {exc}')
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, help='Optional pre-edit snapshot directory with baseline.json')
    args = parser.parse_args()
    docs = {VOLUMES / name: text for name, text in added_documents().items()}
    for name in ['README.md', 'VOLUME_STANDARD.md', 'SOURCE_AUDIT.md', 'CHANGES.md']:
        p = VOLUMES / name
        docs[p] = p.read_text()
    for name in ['README.md', 'CATALOG.md', 'HERMES.md', 'volumes/MANIFEST.md',
                 'volumes/01-platform-and-architecture.md', 'volumes/09-reference-history-and-versions.md']:
        p = DOCS / name
        text = p.read_text()
        if SUPPLEMENT in text:
            docs[p] = text.split(SUPPLEMENT, 1)[1]
    errors = []
    diagrams = 0
    for p, text in docs.items():
        try:
            _, count = outside_fences(text)
            diagrams += count
            errors.extend(check_links(p, text))
            ids = HTML_ID.findall(text)
            if len(ids) != len(set(ids)):
                errors.append(f'{p.name}: duplicate explicit anchors in addition')
            # Check IDs against the complete document, not just the newly appended fragment.
            full_ids = HTML_ID.findall(p.read_text())
            if len(full_ids) != len(set(full_ids)):
                errors.append(f'{p.name}: duplicate explicit anchors in full document')
        except ValueError as exc:
            errors.append(f'{p.name}: {exc}')
    if args.baseline:
        errors.extend(preservation(args.baseline))
    if errors:
        print('\n'.join('FAIL: ' + e for e in errors), file=sys.stderr)
        raise SystemExit(1)
    print(f'PASS: {len(docs)} new/addition fragments; {diagrams} Mermaid fences; local links and anchors resolve')
    if args.baseline:
        print('PASS: original Markdown bytes preserved (append-only, or bounded volume-03 insertions)')
    print('LIMIT: text structure only; Mermaid rendering and Hermes runtime tests not performed')


if __name__ == '__main__':
    main()
