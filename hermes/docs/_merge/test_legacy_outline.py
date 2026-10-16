"""Regression checks for visible legacy directories (no renderer/runtime required)."""
import unittest

from audit_legacy import check_outline


class LegacyOutlineTests(unittest.TestCase):
    def document(self):
        return '''# Module design

## 目录
<!-- visible-toc:start -->
- [1. Responsibilities](#section-1)
  - [1.1 Startup](#section-1-1)
<!-- visible-toc:end -->
<a id="section-1"></a>
## 1. Responsibilities
<a id="section-1-1"></a>
### 1.1 Startup
````markdown
# This is a sample title, not an extra document H1
```python
## This is also sample text
```
````
'''

    def test_visible_directory_and_nested_fences(self):
        self.assertEqual(check_outline(self.document()), [])

    def test_reject_collapsed_generated_navigation(self):
        text = self.document() + '<details><summary>章节目录：hidden</summary></details>'
        self.assertTrue(any('collapsed' in e for e in check_outline(text)))

    def test_detect_missing_toc_entry(self):
        text = self.document().replace('  - [1.1 Startup](#section-1-1)\n', '')
        self.assertTrue(any('missing chapter' in e for e in check_outline(text)))

    def test_reject_extra_h1(self):
        self.assertTrue(any('H1' in e for e in check_outline(self.document() + '\n# Wrong root\n')))

    def test_detect_skipped_level(self):
        text = self.document().replace('### 1.1 Startup', '#### 1.1 Startup')
        self.assertTrue(any('level skipped' in e for e in check_outline(text)))

    def test_detect_duplicate_explicit_anchor(self):
        text = self.document() + '\n<a id="section-1"></a>\n'
        self.assertTrue(any('duplicate explicit' in e for e in check_outline(text)))

    def test_reject_absent_visible_directory(self):
        self.assertTrue(any('visible H2' in e for e in check_outline('# Module\n')))


if __name__ == '__main__':
    unittest.main()
