"""FixtureSource: compiled bundle by hash when a bundles dir is configured, sample otherwise. No network."""
from __future__ import annotations

import json
from pathlib import Path

from student_agent.sources import FixtureSource

HASH = "a1" * 32
# Not `from conftest import ...`: with --import-mode=importlib every project's conftest shares the
# bare name `conftest`, so the first one collected (content-agent's) wins and this import grabbed
# the wrong module. Derived here instead so the module is independent of collection order.
CONTRACTS = Path(__file__).resolve().parents[2] / "runtime" / "contracts"


def compile_bundle(root, bundle_hash, assets):
    d = root / bundle_hash[:32]
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({"bundle_hash": bundle_hash}), encoding="utf-8")
    (d / "bundle.json").write_text(json.dumps({"steps": [], "assets": assets}), encoding="utf-8")


def test_without_a_bundles_dir_every_hash_gets_the_sample(tmp_path):
    src = FixtureSource(CONTRACTS)
    assert src.bundle(HASH) == src.bundle("b2" * 32)


def test_a_compiled_bundle_is_used_only_when_its_manifest_names_the_same_hash(tmp_path):
    compile_bundle(tmp_path, HASH, {"x": {}})
    src = FixtureSource(CONTRACTS, tmp_path)
    assert src.bundle(HASH)["assets"] == {"x": {}}
    (tmp_path / HASH[:32] / "manifest.json").write_text(json.dumps({"bundle_hash": "c3" * 32}), encoding="utf-8")
    assert "x" not in src.bundle(HASH)["assets"]            # manifest disagrees -> sample, not the file


def test_hostile_or_malformed_hashes_never_reach_the_filesystem(tmp_path):
    compile_bundle(tmp_path, HASH, {"x": {}})
    src = FixtureSource(CONTRACTS, tmp_path)
    for bad in ("../" + HASH, "..", HASH.upper(), HASH[:40], HASH + "0", ""):
        assert "x" not in src.bundle(bad)["assets"], bad
