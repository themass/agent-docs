"""Offline regression tests for documentation checks; never imports Hermes."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import audit_source as audit
import verify_volumes as verify


class SourceAuditTests(unittest.TestCase):
    def test_role_separates_tests_vendor_and_assets(self):
        cases = {
            'agent/loop.py': 'runtime',
            'apps/ui/src/page.tsx': 'runtime',
            'agent/tests/loop.py': 'test',
            'tools/test_exec.py': 'test',
            'apps/ui/loop.spec.ts': 'test',
            'apps/node_modules/a/index.js': 'vendor',
            'skills/a/main.py': 'skill-code',
            'optional-skills/a/code.ts': 'skill-code',
            'scripts/install.py': 'build-eval-site',
            'evals/run.py': 'build-eval-site',
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(audit.role(path), expected)

    def test_symbols_include_methods_not_function_locals(self):
        text = '''class Service:
    async def run(self):
        def private():
            pass

def top():
    class Inner:
        pass
'''
        self.assertEqual([r['name'] for r in audit.symbols(text)],
                         ['Service', 'Service.run', 'top'])
        self.assertEqual(audit.symbols(text)[1]['line'], 2)

    def test_invalid_python_does_not_silently_pass(self):
        with self.assertRaises(SyntaxError):
            audit.symbols('def broken(:')

    def test_encoded_json_roundtrips_both_schemas(self):
        for key in ['files', 'records']:
            for rows in [[], [{'path': '中文.py', 'line': 1}]]:
                value = {'schema_version': 1, 'commit': 'abc', key: rows}
                self.assertEqual(json.loads(audit.encoded(value)), value)


class VolumeChecksTests(unittest.TestCase):
    def test_fences_hide_embedded_links_and_count_diagrams(self):
        plain, count = verify.outside_fences(
            '# Intro\n```mermaid\n[not a link](missing.md)\n```\n~~~python\npass\n~~~\n')
        self.assertEqual(count, 1)
        self.assertNotIn('missing.md', plain)

    def test_mismatched_fence_is_not_closing_fence(self):
        with self.assertRaises(ValueError):
            verify.outside_fences('````python\nx = 1\n```\n')

    def test_explicit_and_repeated_heading_anchors(self):
        found = verify.anchors('<a id="manual"></a>\n## Repeated\n## Repeated\n')
        self.assertTrue({'manual', 'repeated', 'repeated-1'} <= found)

    def test_links_check_files_and_anchors(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            entry = root / 'a.md'
            dest = root / 'b.md'
            dest.write_text('<a id="okay"></a>\n')
            entry.write_text('[good](b.md#okay)')
            self.assertEqual(verify.check_links(entry, entry.read_text()), [])
            errors = verify.check_links(entry, '[bad](b.md#unknown) [absent](c.md)')
            self.assertEqual(len(errors), 2)

    def test_external_links_are_not_fetched(self):
        self.assertEqual(verify.check_links(Path('/a.md'),
                         '[web](https://example.com/a#b) [mail](mailto:a@example.com)'), [])

    def test_preservation_accepts_only_unchanged_prefix(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            baseline, current = root / 'baseline', root / 'current'
            baseline.mkdir()
            current.mkdir()
            old = b'# Original\n'
            (baseline / 'one.md').write_bytes(old)
            (baseline / 'baseline.json').write_text(json.dumps({
                'one.md': {'sha256': hashlib.sha256(old).hexdigest(), 'bytes': len(old)}
            }))
            with patch.object(verify, 'DOCS', current):
                (current / 'one.md').write_bytes(old + b'\n# Addition\n')
                self.assertEqual(verify.preservation(baseline), [])
                (current / 'one.md').write_bytes(b'# Changed\n')
                self.assertEqual(len(verify.preservation(baseline)), 1)
                (current / 'one.md').unlink()
                self.assertEqual(len(verify.preservation(baseline)), 1)

    def test_only_volume03_reviewed_regions_are_removed(self):
        payload = (b'# Old\n<!-- compression-toc:start -->\nnew toc\n'
                   b'<!-- compression-toc:end -->\n## Old chapter\n'
                   b'<!-- compression-detail:start -->\nnew section\n'
                   b'<!-- compression-detail:end -->\n## Next old chapter\n')
        expected = b'# Old\n## Old chapter\n## Next old chapter\n'
        self.assertEqual(verify.without_reviewed_insertions(
            'volumes/03-runtime-session-and-loop.md', payload), expected)
        self.assertEqual(verify.without_reviewed_insertions('other.md', payload), payload)

    def test_unbalanced_reviewed_regions_fail_closed(self):
        for payload in [b'<!-- compression-detail:start -->\nnew',
                        b'<!-- compression-detail:end -->\n',
                        b'<!-- compression-detail:end --><!-- compression-detail:start -->\n']:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                verify.without_reviewed_insertions('volumes/03-runtime-session-and-loop.md', payload)

    def test_corrupt_baseline_fails_even_if_current_matches(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'one.md').write_text('wrong baseline')
            (root / 'baseline.json').write_text(json.dumps({
                'one.md': {'sha256': '0' * 64, 'bytes': 10}
            }))
            with patch.object(verify, 'DOCS', root):
                self.assertEqual(len(verify.preservation(root)), 1)


if __name__ == '__main__':
    unittest.main()
