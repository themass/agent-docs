"""Where a lesson's bundle and poem pack come from.

``JavaSource`` is the production path: the agent never trusts content sent by the browser, it asks the Java
student API for the bundle by hash (published-only, immutable, so cached by hash) and for the poem pack.
``FixtureSource`` reads the demo files in ``runtime/contracts`` so the whole app runs with no database and
no Java. The two are selected by ``STUDENT_AGENT_SOURCE``; the default is Java whenever a Java base URL exists.
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Protocol

import httpx

log = logging.getLogger("student_agent.sources")
_HASH = re.compile(r"^[a-f0-9]{64}$")


class SourceError(Exception):
    pass


class Source(Protocol):
    def bundle(self, bundle_hash: str) -> dict[str, Any]: ...

    def pack(self, work_id: str) -> dict[str, Any]: ...


class FixtureSource:
    """Demo files. With ``bundles_dir`` set (dev only), a compiled bundle whose manifest names the requested hash is
    used, so the agent numbers lines against the same bundle the page loaded. Otherwise, or on any mismatch, the
    sample bundle stands in for any hash so the dev flow needs no compile step. Tests leave ``bundles_dir`` unset."""

    def __init__(self, root: Path, bundles_dir: Path | None = None) -> None:
        self.root = root
        self.bundles_dir = bundles_dir

    def _read(self, path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SourceError("fixture unreadable") from exc

    def bundle(self, bundle_hash: str) -> dict[str, Any]:
        if self.bundles_dir is not None and _HASH.match(bundle_hash):
            try:
                directory = self.bundles_dir / bundle_hash[:32]
                manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
                if manifest.get("bundle_hash") == bundle_hash:
                    return self._read(directory / "bundle.json")
            except (OSError, ValueError, SourceError):
                pass  # not compiled / unreadable: fall back to the sample below
        return self._read(self.root / "sample.chun-wang.json")

    def pack(self, work_id: str) -> dict[str, Any]:
        if work_id != "work-chun-wang":
            raise SourceError("no fixture for this work")
        return self._read(self.root / "demo" / "pack.chun-wang.json")


class JavaSource:
    def __init__(self, base: str, transport: httpx.BaseTransport | None = None, pack_ttl: float = 300.0) -> None:
        self.base = base.rstrip("/")
        self._transport = transport
        self._bundles: dict[str, dict[str, Any]] = {}
        self._packs: dict[str, tuple[float, dict[str, Any]]] = {}
        self._ttl = pack_ttl

    def _get(self, path: str) -> Any:
        try:
            with httpx.Client(timeout=4.0, transport=self._transport) as client:
                res = client.get(f"{self.base}/api/student/v1{path}")
        except httpx.HTTPError as exc:
            raise SourceError("student api unreachable") from exc
        if res.status_code != 200:
            raise SourceError(f"student api status {res.status_code}")
        return res.json()

    def bundle(self, bundle_hash: str) -> dict[str, Any]:
        if not _HASH.match(bundle_hash):
            raise SourceError("not a bundle hash")
        if bundle_hash not in self._bundles:  # immutable by hash: cache forever
            self._bundles[bundle_hash] = self._get(f"/bundles/{bundle_hash}")
        return self._bundles[bundle_hash]

    def pack(self, work_id: str) -> dict[str, Any]:
        now = time.monotonic()
        hit = self._packs.get(work_id)
        if hit and now - hit[0] < self._ttl:
            return hit[1]
        body = self._get(f"/works/{work_id}/pack")
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            raise SourceError("pack missing")
        self._packs[work_id] = (now, data)
        return data
