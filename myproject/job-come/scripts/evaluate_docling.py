#!/usr/bin/env python3
"""Run a bounded Docling evaluation against a local benchmark manifest.

The evaluator is deliberately explicit about where Docling code and model artifacts
come from.  It never retries a remote model download in offline mode; unavailable
weights are recorded as ``blocked_external_model`` so the report remains useful.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

DEFAULT_HF_HOME = "/tmp/jobcome-docling-models"
DEFAULT_XDG_CACHE = "/tmp/jobcome-docling-cache"


def configure_environment(*, offline: bool, artifacts_path: Path | None) -> None:
    """Set process-local cache/offline settings before importing Docling."""
    os.environ.setdefault("HF_HOME", DEFAULT_HF_HOME)
    os.environ.setdefault("XDG_CACHE_HOME", DEFAULT_XDG_CACHE)
    if artifacts_path is not None:
        os.environ["DOCLING_ARTIFACTS_PATH"] = str(artifacts_path)
    if offline:
        os.environ.update(
            {
                "HF_HUB_OFFLINE": "1",
                "HF_DATASETS_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
            }
        )


def _ocr_options(engine: str):
    from docling.datamodel.pipeline_options import OcrMacOptions, RapidOcrOptions

    if engine == "mac":
        return OcrMacOptions(lang=["zh-Hans", "en-US"], recognition="accurate")
    if engine == "rapidocr":
        return RapidOcrOptions(lang=["ch"])
    return None


def _blocked_external_model(exc: BaseException) -> bool:
    message = str(exc).lower()
    markers = (
        "huggingface",
        "modelscope",
        "rapidocr",
        "checkpoint",
        "model file",
        "snapshot_download",
        "offline mode",
        "could not find the requested files",
        "429",
        "too many requests",
        "connection",
        "download",
        "no module named 'ocrmac'",
        "ocrmac is not correctly installed",
        "vision",
        "quartz",
    )
    return any(marker in message for marker in markers)


def _make_converter(*, ocr_engine: str, artifacts_path: Path | None, source: Path | None):
    if source is not None:
        sys.path.insert(0, str(source))

    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    ocr_options = _ocr_options(ocr_engine)
    options_kwargs = {
        "document_timeout": 120,
        "enable_remote_services": False,
        "allow_external_plugins": False,
        "do_ocr": ocr_engine != "none",
    }
    if artifacts_path is not None:
        options_kwargs["artifacts_path"] = artifacts_path
    if ocr_options is not None:
        options_kwargs["ocr_options"] = ocr_options
    options = PdfPipelineOptions(**options_kwargs)
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )


def evaluate(
    manifest: Path,
    output: Path,
    *,
    source: Path | None = None,
    artifacts_path: Path | None = None,
    offline: bool = False,
    ocr_engine: str = "none",
) -> dict:
    configure_environment(offline=offline, artifacts_path=artifacts_path)
    cases = json.loads(manifest.read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "version": None,
        "source": str(source) if source else "installed-package",
        "artifacts_path": str(artifacts_path) if artifacts_path else None,
        "offline": offline,
        "ocr_engine": ocr_engine,
        "cases": [],
    }

    try:
        importlib.metadata.version("docling")
        converter = _make_converter(
            ocr_engine=ocr_engine, artifacts_path=artifacts_path, source=source
        )
        report["version"] = importlib.metadata.version("docling")
    except Exception as exc:
        report["status"] = (
            "blocked_external_model" if _blocked_external_model(exc) else "error"
        )
        report["blocked_reason"] = type(exc).__name__ + ": " + str(exc)[:800]
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return report

    for case in cases:
        path = Path(case["path"])
        started = time.monotonic()
        try:
            if path.suffix == ".txt":
                # Docling supports Markdown, not raw TXT: explicit no-content-change adapter.
                with TemporaryDirectory(prefix="jobcome-docling-") as temp_dir:
                    adapted = Path(temp_dir) / (path.stem + ".md")
                    adapted.write_bytes(path.read_bytes())
                    text = converter.convert(adapted).document.export_to_markdown()
            else:
                text = converter.convert(path).document.export_to_markdown()

            def squash(value):
                return "".join(value.split())

            normalized = squash(text)
            hits = [squash(a) in normalized for a in case["anchors"]]
            positions = [normalized.find(squash(a)) for a in case["anchors"]]
            row = {
                "file": path.name,
                "engine": "docling",
                "status": "ok",
                "scanned": case["scanned"],
                "adapter": "txt-as-markdown" if path.suffix == ".txt" else None,
                "anchor_recall": sum(hits) / len(hits),
                "anchor_order_preserved": all(a <= b for a, b in zip(positions, positions[1:]))
                if all(hits)
                else None,
                "characters": len(text),
                "quality_status": "ok" if all(hits) else "insufficient_anchors",
            }
        except Exception as exc:
            blocked = _blocked_external_model(exc)
            row = {
                "file": path.name,
                "engine": "docling",
                "status": "blocked_external_model" if blocked else "error",
                "scanned": case["scanned"],
                "error": type(exc).__name__ + ": " + str(exc)[:800],
            }
        row["seconds"] = round(time.monotonic() - started, 3)
        report["cases"].append(row)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(path.name, row["status"], row.get("anchor_recall"), flush=True)

    report["status"] = (
        "ok"
        if all(
            r["status"] == "ok" and r.get("quality_status", "ok") == "ok"
            for r in report["cases"]
        )
        else "partial"
    )
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("/tmp/jobcome-docling-cases/manifest.json"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/jobcome-docling-result.json")
    )
    parser.add_argument("--source", type=Path, help="Local Docling source checkout")
    parser.add_argument(
        "--artifacts-path",
        type=Path,
        help="Directory containing pre-downloaded model artifacts",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Disable Hugging Face/transformers network resolution",
    )
    parser.add_argument("--ocr-engine", choices=("none", "mac", "rapidocr"), default="none")
    args = parser.parse_args()
    report = evaluate(
        args.manifest,
        args.output,
        source=args.source,
        artifacts_path=args.artifacts_path,
        offline=args.offline,
        ocr_engine=args.ocr_engine,
    )
    if report.get("status") == "error":
        raise SystemExit(1)
