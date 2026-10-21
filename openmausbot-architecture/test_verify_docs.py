"""Regression tests for documentation checks; never modifies the source checkout."""
import json
from pathlib import Path
import runpy
import shutil
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / "../../personal-agent/OpenMausBot").resolve()


class DocumentationChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="openmaus-docs-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for file in [*HERE.glob("*.md"), HERE / "source-evidence.json"]:
            destination = self.root / file.name
            if file.suffix == ".md":
                # A copied document must still link to the real read-only checkout.
                destination.write_text(file.read_text().replace("../../personal-agent/OpenMausBot", str(SOURCE)))
            else:
                shutil.copy2(file, destination)
        self.check = runpy.run_path(str(HERE / "verify_docs.py"))["check"]
        self.check.__globals__["HERE"] = self.root

    def report(self):
        return self.check(SOURCE)

    def test_current_documents_pass(self):
        self.assertTrue(self.report()["ok"])

    def test_missing_file_is_detected(self):
        with (self.root / "README.md").open("a") as file:
            file.write("\n[Broken](missing.md)\n")
        self.assertTrue(any("missing link target" in e for e in self.report()["errors"]))

    def test_missing_anchor_is_detected(self):
        with (self.root / "README.md").open("a") as file:
            file.write("\n[Broken](#no-such-anchor)\n")
        self.assertTrue(any("missing explicit anchor" in e for e in self.report()["errors"]))

    def test_unclosed_fence_is_detected(self):
        with (self.root / "README.md").open("a") as file:
            file.write("\n```mermaid\nflowchart LR\n")
        self.assertTrue(any("unclosed code fence" in e for e in self.report()["errors"]))

    def test_source_anchor_drift_is_detected(self):
        path = self.root / "source-evidence.json"
        data = json.loads(path.read_text())
        data["files"][0]["anchors"][0]["line"] = 1_000_000
        path.write_text(json.dumps(data))
        self.assertTrue(any("source anchor drift" in e for e in self.report()["errors"]))

    def test_source_hash_drift_is_detected(self):
        path = self.root / "source-evidence.json"
        data = json.loads(path.read_text())
        data["files"][0]["sha256"] = "0" * 64
        path.write_text(json.dumps(data))
        self.assertTrue(any("source content drift" in e for e in self.report()["errors"]))


if __name__ == "__main__":
    unittest.main()
