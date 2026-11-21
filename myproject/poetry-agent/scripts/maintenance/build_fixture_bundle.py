#!/usr/bin/env python3
"""Compile a TEST bundle for 《春望》 whose assets are the real placeholder files in C's registry.

Purpose: let the whole pipeline (compile -> deliver -> student app) run end to end before the real
scholarship exists, then be replaced. Nothing here is real content and the output says so:

  * facts come from a fixture, so the manifest carries facts_source = "FIXTURE ...";
  * every asset is a self-generated placeholder (not_for_release), so C's production gate rejects it;
  * other sessions' files are only read. The derived script and fixture facts go to a temp dir, and the
    bundle goes to the compiler's normal output (content-agent/pipeline/dist/bundles/<hash>/), which is
    content-addressed: a new hash is a new directory and nothing existing is overwritten.

    python3 scripts/maintenance/build_fixture_bundle.py --check   # derive + verify, write nothing
    python3 scripts/maintenance/build_fixture_bundle.py           # derive + verify + compile
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

PLATFORM = Path(__file__).resolve().parents[2]
COMPILER = PLATFORM / "content-agent/pipeline/tools/scene-compiler"
SAMPLE_SCRIPT = PLATFORM / "content-agent/pipeline/contracts/sample.chun-wang.json"
ASSETS_FILE = PLATFORM / "student-app/production/published/bundles/chun-wang.assets.json"
DIST = PLATFORM / "content-agent/pipeline/dist/bundles"


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def tail(text: str, limit: int = 700) -> str:
    return text if len(text) <= limit else "..." + text[-limit:]


def fail(message: str) -> int:
    print(f"FAIL  {message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify only; write nothing")
    args = parser.parse_args()

    for path in (SAMPLE_SCRIPT, ASSETS_FILE, COMPILER / "compile.mjs", COMPILER / "fixture-facts.mjs"):
        if not path.is_file():
            return fail(f"missing input: {path.relative_to(PLATFORM)}")

    script = json.loads(SAMPLE_SCRIPT.read_text(encoding="utf-8"))
    registry_assets = json.loads(ASSETS_FILE.read_text(encoding="utf-8"))["assets"]
    if not registry_assets:
        return fail("registry assets block is empty")
    unhashed = [i for i, a in registry_assets.items() if not a.get("hash")]
    if unhashed:
        return fail(f"assets without a hash: {unhashed}")
    not_placeholder = [i for i, a in registry_assets.items() if not a.get("placeholder")]
    if not_placeholder:
        return fail(
            "refusing: these assets are not marked placeholder, so this is no longer test data: "
            f"{not_placeholder}"
        )

    previous = set(script.get("assets", {}))
    script["assets"] = registry_assets
    print(f"assets: {len(previous)} embedded -> {len(registry_assets)} from the registry "
          f"(dropped: {sorted(previous - set(registry_assets))}, "
          f"added: {len(set(registry_assets) - previous)})")

    with tempfile.TemporaryDirectory(prefix="fixture-bundle.") as tmp:
        tmpdir = Path(tmp)
        derived = tmpdir / "script.json"
        facts = tmpdir / "facts.fixture.json"
        derived.write_text(json.dumps(script, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        base_facts = PLATFORM / "content-agent/pipeline/contracts/facts.chun-wang.json"
        made = run(["node", str(COMPILER / "fixture-facts.mjs"), "--from", str(base_facts),
                    "--script", str(derived), "--out", str(facts)])
        if made.returncode != 0:
            return fail(f"fixture-facts failed: {tail(made.stderr or made.stdout)}")
        label = json.loads(facts.read_text(encoding="utf-8")).get("generated_by", "")
        if "FIXTURE" not in label:
            return fail("fixture facts are not labelled FIXTURE; refusing to compile")

        common = ["node", str(COMPILER / "compile.mjs"), "--script", str(derived),
                  "--facts", str(facts), "--out", str(DIST), "--compiled-by", "fixture-test"]
        checked = run([*common, "--check-only"])
        if checked.returncode != 0:
            return fail(f"the 12 rules rejected the derived script:\n{tail(checked.stdout)}")
        print("check-only: COMPILES (12 rules passed against FIXTURE facts)")
        if args.check:
            print("--check: nothing written")
            return 0

        before = {p.name for p in DIST.iterdir() if p.is_dir()} if DIST.is_dir() else set()
        built = run(common)
        if built.returncode != 0:
            return fail(f"compile failed:\n{tail(built.stdout + built.stderr)}")
        print(tail(built.stdout.strip(), 500))
        after = {p.name for p in DIST.iterdir() if p.is_dir()}
        new = sorted(after - before)
        if not new:
            print("note: that bundle already existed (same content, same hash); nothing new written")
            return 0
        manifest = json.loads((DIST / new[0] / "manifest.json").read_text(encoding="utf-8"))
        source = str(manifest.get("facts_source", ""))
        if "FIXTURE" not in source:
            return fail(f"new bundle {new[0]} is not labelled FIXTURE (facts_source={source!r})")
        print(f"new bundle: dist/bundles/{new[0]}/   facts_source={source!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
