#!/usr/bin/env python3
"""Small offline checker for the Rakazo architecture notes."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = Path('/Users/gqli/work/deepagents/personal-agent/rakazo')
MD = sorted(ROOT.glob('*.md'))
errors: list[str] = []

for path in MD:
    text = path.read_text(encoding='utf-8')
    if '## 目录' not in text:
        errors.append(f'{path.name}: missing visible table of contents')
    fence_count = sum(1 for line in text.splitlines() if line.startswith('```'))
    if fence_count % 2:
        errors.append(f'{path.name}: unclosed fenced block')
    anchors = re.findall(r'<a id="([^"]+)"></a>', text)
    if len(anchors) != len(set(anchors)):
        errors.append(f'{path.name}: duplicate explicit anchors')
    for link in re.findall(r'\]\((\.[^)#]+)(?:#[^)]+)?\)', text):
        target = (path.parent / link).resolve()
        if not target.exists():
            errors.append(f'{path.name}: broken local link {link}')

if not SOURCE.is_dir():
    errors.append(f'missing source root: {SOURCE}')
else:
    head = subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip()
    expected = '60684ee3c7de23486b2ecbbda904a0ba7478ea6e'
    if head != expected:
        errors.append(f'source HEAD drifted: expected {expected}, got {head}')

print(f'Markdown files: {len(MD)}')
print(f'Mermaid diagrams: {sum(p.read_text(encoding="utf-8").count("```mermaid") for p in MD)}')
print(f'Errors: {len(errors)}')
for error in errors:
    print(f'- {error}')
raise SystemExit(1 if errors else 0)
