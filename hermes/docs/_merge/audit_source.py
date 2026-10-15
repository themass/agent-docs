#!/usr/bin/env python3
"""Inventory tracked source bytes and resolve documentation symbols; never import Hermes."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent
VOLUMES = DOCS / 'volumes'
DEFAULT_SOURCE = DOCS.parents[2] / 'hermes-dev' / 'hermes-agent'
CODE_SUFFIXES = {'.py', '.ts', '.tsx', '.js', '.mjs', '.cjs', '.rs', '.c', '.cpp', '.h', '.sh', '.ps1', '.fish', '.nix'}
SYMBOL_REF = re.compile(r'(?P<path>(?:[\w-]+/)*[\w-]+\.py):(?P<symbol>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)')
NEW_DOCS = (
    '10-model-backends-and-resilience.md', '11-terminal-execution-backends.md',
    '12-automation-and-package-runtime.md', '13-config-secrets-and-observability.md',
)
ADDED_SECTIONS = {
    '04-prompt-and-context.md': '<a id="sec-4-steer-delivery"></a>',
    '03-runtime-session-and-loop.md': '<!-- compression-detail:start -->',
    '05-capabilities-extensions.md': '<a id="cap-plugin-lifecycle"></a>',
    '07-multi-agent-and-kanban.md': '<a id="multi-runtime-boundaries"></a>',
}
ADDED_SECTION_ENDS = {
    '04-prompt-and-context.md': '<a id="5-和卷三卷五的边界"></a>',
    '03-runtime-session-and-loop.md': '<!-- compression-detail:end -->',
}
CHAPTERS = {
    'agent': ['03-runtime-session-and-loop.md', '04-prompt-and-context.md', '10-model-backends-and-resilience.md'],
    'providers': ['10-model-backends-and-resilience.md'],
    'tools': ['05-capabilities-extensions.md', '11-terminal-execution-backends.md'],
    'plugins': ['05-capabilities-extensions.md', '05-memory-system-reference.md'],
    'gateway': ['06-gateways-channels-and-hitl.md', '07-multi-agent-and-kanban.md'],
    'tui_gateway': ['02-surface-and-presentation.md'],
    'acp_adapter': ['02-surface-and-presentation.md'],
    'hermes_cli': ['02-surface-and-presentation.md', '13-config-secrets-and-observability.md'],
    'cron': ['12-automation-and-package-runtime.md'],
    'pm': ['12-automation-and-package-runtime.md'],
    'hermes_platform': ['13-config-secrets-and-observability.md'],
    'apps': ['02-surface-and-presentation.md'], 'ui-tui': ['02-surface-and-presentation.md'],
    'web': ['01-platform-and-architecture.md', '02-surface-and-presentation.md'],
    'skills': ['05-capabilities-extensions.md'], 'optional-skills': ['05-capabilities-extensions.md'],
    'evals': ['03-runtime-session-and-loop.md'],
    'scripts': ['09-reference-history-and-versions.md'],
    'docker': ['09-reference-history-and-versions.md'], 'nix': ['09-reference-history-and-versions.md'],
    'native': ['01-platform-and-architecture.md'],
    '(root)': ['01-platform-and-architecture.md', '03-runtime-session-and-loop.md'],
}


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(['git', '-C', str(root), *args], text=True)


def role(path: str) -> str:
    parts = Path(path).parts
    name = Path(path).name
    if 'node_modules' in parts or 'vendor' in parts or 'vendored' in parts:
        return 'vendor'
    if (any(x in {'tests', 'tests-js', '__tests__', 'e2e', 'mytest', 'fixtures', '_fixtures'} for x in parts)
            or re.search(r'\.(test|spec)\.', name) or name.startswith('test_') or name.endswith('_tests.rs')):
        return 'test'
    if parts[0] in {'scripts', 'docker', 'nix', '.github', 'contributors', 'evals', 'website'}:
        return 'build-eval-site'
    if parts[0] in {'skills', 'optional-skills'}:
        return 'skill-code'
    return 'runtime'


def symbols(text: str) -> list[dict]:
    tree = ast.parse(text)
    result = []

    def visit(nodes, prefix=''):
        for node in nodes:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + node.name
                result.append({'name': name, 'line': node.lineno, 'kind': type(node).__name__})
                # Keep class methods; omit local implementation functions from the public navigation.
                if isinstance(node, ast.ClassDef):
                    visit(node.body, name + '.')
    visit(tree.body)
    return result


def added_documents() -> dict[str, str]:
    result = {name: (VOLUMES / name).read_text() for name in NEW_DOCS}
    for name, marker in ADDED_SECTIONS.items():
        text = (VOLUMES / name).read_text()
        if marker not in text:
            raise ValueError(f'Missing addition marker: {name}: {marker}')
        fragment = text.split(marker, 1)[1]
        if end := ADDED_SECTION_ENDS.get(name):
            if end not in fragment:
                raise ValueError(f'Missing addition end marker: {name}: {end}')
            fragment = fragment.split(end, 1)[0]
        result[name] = fragment
    return result


def evidence(root: Path) -> dict:
    records = []
    cache = {}
    for doc, text in sorted(added_documents().items()):
        seen = set()
        for match in SYMBOL_REF.finditer(text):
            path, symbol = match.group('path', 'symbol')
            if (path, symbol) in seen:
                continue
            seen.add((path, symbol))
            if path not in cache:
                cache[path] = symbols((root / path).read_text(encoding='utf-8-sig'))
            found = next((x for x in cache[path] if x['name'] == symbol), None)
            if found is None:
                raise ValueError(f'Unresolved source symbol: {doc} -> {path}:{symbol}')
            records.append({'document': doc, 'path': path, 'symbol': symbol, 'line': found['line'],
                            'evidence_kind': 'static-reference', 'runtime_test_executed': False})
    return {'schema_version': 1, 'commit': git(root, 'rev-parse', 'HEAD').strip(),
            'meaning': 'Symbols resolve in the local snapshot; not proof of runtime behavior or whole-file coverage.',
            'records': records}


def inventory(root: Path) -> dict:
    rows = []
    counts = Counter()
    roles = Counter()
    excluded = Counter()
    for rel in sorted(x for x in git(root, 'ls-files', '-z').split('\0') if x):
        p = root / rel
        if p.suffix not in CODE_SUFFIXES:
            continue
        kind = role(rel)
        if kind in {'test', 'vendor'}:
            excluded[kind] += 1
            continue
        if not p.is_file():
            raise ValueError(f'Tracked code missing from checkout: {rel}')
        raw = p.read_bytes()
        group = rel.split('/')[0] if '/' in rel else '(root)'
        text = raw.decode('utf-8-sig')
        row = {'path': rel, 'role': kind, 'group': group, 'sha256': hashlib.sha256(raw).hexdigest(),
               'lines': len(text.splitlines()), 'navigation': CHAPTERS.get(group, []), 'coverage': 'L0-inventory'}
        if p.suffix == '.py':
            try:
                row['symbols'] = symbols(text)
            except SyntaxError as exc:
                row['parse_error'] = str(exc)
        rows.append(row)
        counts[group] += 1
        roles[kind] += 1
    return {'schema_version': 1, 'source_root_hint': 'hermes-dev/hermes-agent',
            'commit': git(root, 'rev-parse', 'HEAD').strip(),
            'dirty': bool(git(root, 'status', '--porcelain').strip()),
            'scope': 'Tracked code by listed extensions, excluding test/vendor paths; build/eval/skill code is separately labelled. No binary assets, config-only catalogs, or untracked code.',
            'extensions': sorted(CODE_SUFFIXES), 'excluded': dict(sorted(excluded.items())),
            'counts_by_group': dict(sorted(counts.items())), 'counts_by_role': dict(sorted(roles.items())),
            'files': rows}


def encoded(value: dict) -> str:
    # One record per line keeps a large inventory diffable without a multi-megabyte pretty print.
    metadata = {k: v for k, v in value.items() if k not in {'files', 'records'}}
    key = 'files' if 'files' in value else 'records'
    prefix = json.dumps(metadata, ensure_ascii=False, indent=2)[:-2]
    return prefix + ',\n  ' + json.dumps(key) + ': [\n' + ',\n'.join(
        '    ' + json.dumps(row, ensure_ascii=False, separators=(',', ':')) for row in value[key]
    ) + '\n  ]\n}\n'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=DEFAULT_SOURCE)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--write', action='store_true')
    mode.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = args.source_root.resolve()
    try:
        outputs = {'SOURCE_INVENTORY.json': inventory(root), 'SOURCE_EVIDENCE.json': evidence(root)}
        for filename, value in outputs.items():
            target = VOLUMES / filename
            if args.write:
                target.write_text(encoded(value), encoding='utf-8')
            elif not target.is_file() or json.loads(target.read_text()) != value:
                raise ValueError(f'{filename} differs from current source/docs; review before --write')
        inv, ev = outputs.values()
        print(f"PASS: {len(inv['files'])} inventoried code files; {len(ev['records'])} exact source-symbol references")
        print(json.dumps(inv['counts_by_role'], ensure_ascii=False))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'FAIL: {exc}\n')


if __name__ == '__main__':
    main()
