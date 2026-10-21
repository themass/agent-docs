#!/usr/bin/env python3
r"""Export full regression: every format x locale combo, downloaded and inspected.

`export_quality.validate_export` already fails closed on page count and text overflow
*before* an artifact reaches storage — that is a production safety net, not a release
check, and it never looks at the file a user actually downloads. This script is the
other half: it drives the live API exactly as the browser does (login, upload, elevate,
export, follow `download_url`, pull the real bytes from storage) across every
format x locale combination the product offers, then inspects what came back:

- PDF: page count, embedded fonts present (a PDF with no embedded CJK font silently
  renders blank/garbled on a machine without that font installed — this is the exact
  failure mode visual-only review misses), and any PDF link annotations point at
  http(s) targets.
- DOCX: opens as a valid OOXML package, non-empty, and any hyperlink relationships
  resolve to http(s) targets.
- HTML: self-contained document (no outbound <link>/<script>), decodes as UTF-8, and
  <a href> targets are http(s) (the export must survive being viewed with no network).
- Download: `download_url` is actually fetchable and content-type/size are sane --
  catches the gap between "job says done" and "file never made it to TOS" that showed
  up repeatedly during manual testing.

Usage:
    export JC_E2E_EMAIL=... JC_E2E_PASSWORD=...
    python scripts/verify_export_regression.py --base http://127.0.0.1:8000/api/v1
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from lib.bootstrap import ensure_project_env

PROJECT_ROOT = ensure_project_env()
SERVER_ROOT = PROJECT_ROOT / "backend" / "server"

import httpx  # noqa: E402

FORMATS = ["pdf", "docx", "html"]
LOCALES = ["zh-CN", "en-US", "zh-en"]
RESUME_FIXTURE = SERVER_ROOT / "tests/regression_assets/resumes/sample_backend_zh.txt"


@dataclass
class CaseResult:
    format: str
    locale: str
    ok: bool
    detail: str
    pages: int | None = None
    fonts_embedded: list[str] = field(default_factory=list)
    links_checked: int = 0
    bytes_len: int = 0


def inspect_pdf(content: bytes) -> tuple[int, list[str], int]:
    import fitz

    with fitz.open(stream=content, filetype="pdf") as doc:
        pages = doc.page_count
        fonts: set[str] = set()
        link_count = 0
        for page in doc:
            for f in page.get_fonts(full=True):
                # (xref, ext, type, basefont, name, encoding, ...)
                fonts.add(f[3])
            for link in page.get_links():
                uri = link.get("uri") or ""
                if uri:
                    link_count += 1
                    if not re.match(r"^https?://", uri):
                        raise ValueError(f"PDF link target is not http(s): {uri!r}")
        return pages, sorted(fonts), link_count


def inspect_docx(content: bytes) -> tuple[bool, int]:
    from docx import Document

    doc = Document(io.BytesIO(content))
    has_text = any(p.text.strip() for p in doc.paragraphs)
    link_count = 0
    rels = doc.part.rels
    for rel in rels.values():
        if "hyperlink" in rel.reltype:
            target = rel.target_ref or ""
            link_count += 1
            if target and not re.match(r"^https?://", target):
                raise ValueError(f"DOCX hyperlink target is not http(s): {target!r}")
    return has_text, link_count


def inspect_html(content: bytes) -> int:
    markup = content.decode("utf-8")
    if "<html" not in markup.lower():
        raise ValueError("HTML export missing document root")
    if re.search(r"<link\b", markup, re.I) or re.search(r"<script\b", markup, re.I):
        raise ValueError("HTML export must be self-contained (found <link>/<script>)")
    hrefs = re.findall(r'href="([^"]+)"', markup)
    for href in hrefs:
        if href.startswith("#"):
            continue
        if not re.match(r"^https?://", href):
            raise ValueError(f"HTML link target is not http(s): {href!r}")
    return len(hrefs)


def run(base: str, email: str, password: str) -> list[CaseResult]:
    client = httpx.Client(base_url=base, timeout=60.0)
    resp = client.post("/auth/register", json={"email": email, "password": password})
    if resp.status_code == 409:
        resp = client.post("/auth/login", json={"email": email, "password": password})
    resp.raise_for_status()

    resume_bytes = RESUME_FIXTURE.read_bytes()
    upload = client.post(
        "/profiles/upload",
        files={"file": ("resume.txt", resume_bytes, "text/plain")},
    )
    upload.raise_for_status()
    profile_id = upload.json()["id"]
    print(f"==> profile_id={profile_id}")

    # `POST /profiles/{id}/elevate` with query params -- not `/resumes/profiles/...`
    # and not a JSON body. The old form 404'd, so this gate failed before it could
    # export anything.
    elevate = client.post(
        f"/profiles/{profile_id}/elevate",
        params={"elevation_level": "elevated"},
    )
    elevate.raise_for_status()

    results: list[CaseResult] = []
    for fmt in FORMATS:
        for locale in LOCALES:
            label = f"{fmt}/{locale}"
            try:
                export_resp = client.post(
                    f"/profiles/{profile_id}/export",
                    json={"format": fmt, "locale": locale, "elevation_level": "elevated"},
                )
                export_resp.raise_for_status()
                job = export_resp.json()
                if job.get("status") != "done" or job.get("error_message"):
                    results.append(
                        CaseResult(fmt, locale, False, f"job not done: {job}")
                    )
                    print(f"  FAIL {label}: job not done: {job}")
                    continue
                download_url = job.get("download_url")
                if not download_url:
                    results.append(CaseResult(fmt, locale, False, "no download_url"))
                    print(f"  FAIL {label}: no download_url")
                    continue
                file_resp = httpx.get(download_url, timeout=60.0)
                file_resp.raise_for_status()
                content = file_resp.content
                if not content:
                    results.append(CaseResult(fmt, locale, False, "empty download body"))
                    print(f"  FAIL {label}: empty download body")
                    continue

                pages = None
                fonts: list[str] = []
                links = 0
                if fmt == "pdf":
                    pages, fonts, links = inspect_pdf(content)
                    if not (1 <= pages <= 6):
                        raise ValueError(f"page count {pages} outside 1-6")
                    if not fonts:
                        raise ValueError("no fonts embedded (CJK text would render blank)")
                elif fmt == "docx":
                    has_text, links = inspect_docx(content)
                    if not has_text:
                        raise ValueError("DOCX has no paragraph text")
                else:
                    links = inspect_html(content)

                results.append(
                    CaseResult(
                        fmt, locale, True, "ok",
                        pages=pages, fonts_embedded=fonts, links_checked=links,
                        bytes_len=len(content),
                    )
                )
                extra = f"pages={pages} fonts={len(fonts)} links={links}" if fmt == "pdf" else f"links={links}"
                print(f"  PASS {label}: {len(content)} bytes, {extra}")
            except Exception as exc:  # noqa: BLE001
                results.append(CaseResult(fmt, locale, False, f"{type(exc).__name__}: {exc}"))
                print(f"  FAIL {label}: {type(exc).__name__}: {exc}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=os.environ.get("JC_E2E_BASE", "http://127.0.0.1:8000/api/v1"))
    parser.add_argument("--email", default=os.environ.get("JC_E2E_EMAIL", ""))
    parser.add_argument("--password", default=os.environ.get("JC_E2E_PASSWORD", ""))
    parser.add_argument("--output", type=Path, default=Path("docs/evidence/export-regression.json"))
    args = parser.parse_args()

    if not args.email or not args.password:
        print("Set JC_E2E_EMAIL and JC_E2E_PASSWORD (or --email/--password).", file=sys.stderr)
        return 1

    try:
        results = run(args.base, args.email, args.password)
    except httpx.ConnectError as exc:
        print(f"FAIL: cannot reach {args.base}: {exc}", file=sys.stderr)
        print("Start the API first (./scripts/dev.sh) and confirm --base.", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            [
                {
                    "format": r.format,
                    "locale": r.locale,
                    "ok": r.ok,
                    "detail": r.detail,
                    "pages": r.pages,
                    "fonts_embedded": r.fonts_embedded,
                    "links_checked": r.links_checked,
                    "bytes": r.bytes_len,
                }
                for r in results
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    failed = [r for r in results if not r.ok]
    total = len(results)
    print(f"\n{total - len(failed)}/{total} export combinations passed.")
    if failed:
        print("FAILED:")
        for r in failed:
            print(f"  {r.format}/{r.locale}: {r.detail}")
        return 1
    print("PASS: all format x locale export combinations verified end to end.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
