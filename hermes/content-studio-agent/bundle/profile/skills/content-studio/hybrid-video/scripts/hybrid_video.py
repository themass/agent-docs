#!/usr/bin/env python3
"""Hybrid video pipeline orchestrator."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_REPORT_DIR = Path("/Users/gqli/.hermes/profiles/content-studio/reports")
PYTHON = os.environ.get("CONTENT_STUDIO_PYTHON") or os.environ.get("DEEPAGENTS_PYTHON") or sys.executable


def paths(date: str, report_dir: Path) -> dict[str, Path]:
    year, month, _ = date.split("-")
    base = report_dir / year / month
    asset_dir = base / "assets" / f"{date}-hybrid"
    return {
        "base": base,
        "script": base / f"{date}-video-script.md",
        "storyboard": base / f"{date}-hybrid-storyboard.md",
        "spec": base / f"{date}-hybrid-production-spec.yaml",
        "video": base / f"{date}-hybrid-video.mp4",
        "cover": base / f"{date}-hybrid-video-cover.jpg",
        "publish": base / f"{date}-hybrid-video-publish.md",
        "asset_dir": asset_dir,
        "asset_status": asset_dir / "hybrid-assets-status.json",
    }


def progress(date: str, stage: str, total: str, status: str, msg: str, artifact: Path | str = "") -> None:
    print(
        f"CONTENT_STUDIO_PROGRESS date={date} pipeline=hybrid-video "
        f"stage={stage}/{total} status={status} msg={msg} artifact={artifact}"
    )


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, text=True, check=False)
    if result.returncode != 0:
        msg = f"Command failed ({result.returncode}): {' '.join(cmd)}"
        raise RuntimeError(msg)


def run_spec(date: str, report_dir: Path) -> Path:
    p = paths(date, report_dir)
    if not p["script"].exists():
        msg = f"视频脚本不存在: {p['script']}"
        raise FileNotFoundError(msg)
    progress(date, "1", "4", "running", "生成 hybrid spec", p["spec"])
    run(
        [
            PYTHON,
            str(SCRIPT_DIR / "hybrid_spec.py"),
            "--date",
            date,
            "--report-dir",
            str(report_dir),
        ]
    )
    progress(date, "1", "4", "ok", "hybrid spec 已生成", p["spec"])
    return p["spec"]


def run_assets(date: str, report_dir: Path) -> Path:
    p = paths(date, report_dir)
    if not p["spec"].exists():
        run_spec(date, report_dir)
    progress(date, "2", "4", "running", "生成 hybrid assets", p["asset_dir"])
    run([PYTHON, str(SCRIPT_DIR / "hybrid_assets.py"), "--spec", str(p["spec"])])
    progress(date, "2", "4", "ok", "hybrid assets 已生成", p["asset_dir"])
    return p["asset_dir"]


def run_render(date: str, report_dir: Path) -> Path:
    p = paths(date, report_dir)
    if not p["asset_status"].exists():
        run_assets(date, report_dir)
    progress(date, "3", "4", "running", "合成 hybrid v1 视频", p["video"])
    run([PYTHON, str(SCRIPT_DIR / "hybrid_compositor.py"), "--spec", str(p["spec"])])
    progress(date, "3", "4", "ok", "hybrid v1 视频已合成", p["video"])
    write_publish(date, report_dir)
    return p["video"]


def write_publish(date: str, report_dir: Path) -> Path:
    p = paths(date, report_dir)
    content = f"""# Hybrid 视频发布指引 — {date}

## 文件

- 视频：`{p['video']}`
- 脚本：`{p['script']}`
- 分镜：`{p['storyboard']}`
- Spec：`{p['spec']}`
- 素材目录：`{p['asset_dir']}`

## 说明

这是第三条独立 hybrid 链路产物，不覆盖 sop 视频或 mpt 视频。

v1 视频以概念卡、GitHub 证据占位卡和 AI b-roll fallback 为主；Seedance 配置完成后，`ai_broll` 段会替换为真实 AI 素材。
"""
    p["publish"].write_text(content, encoding="utf-8")
    progress(date, "4", "4", "ok", "hybrid 发布指引已生成", p["publish"])
    return p["publish"]


def status(date: str, report_dir: Path) -> None:
    p = paths(date, report_dir)
    print(f"📊 Hybrid 视频状态 — {date}")
    print("")
    for label in ("script", "storyboard", "spec", "video", "publish"):
        file = p[label]
        if file.exists():
            print(f"✅ {label}: {file} ({_size(file)})")
        else:
            print(f"❌ {label}: {file}")
    print("")
    asset_dir = p["asset_dir"]
    if asset_dir.exists():
        print(f"✅ asset_dir: {asset_dir}")
        for child in ("cards", "github", "ai-broll", "clips"):
            folder = asset_dir / child
            count = len([item for item in folder.iterdir() if item.is_file()]) if folder.exists() else 0
            print(f"   - {child}: {count} files")
    else:
        print(f"❌ asset_dir: {asset_dir}")

    if p["asset_status"].exists():
        data = json.loads(p["asset_status"].read_text(encoding="utf-8"))
        print("")
        print("资产统计:")
        print(json.dumps(data.get("counts", {}), ensure_ascii=False, indent=2))


def _size(path: Path) -> str:
    size = path.stat().st_size
    if size > 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MB"
    if size > 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def pipeline(date: str, report_dir: Path) -> None:
    run_spec(date, report_dir)
    run_assets(date, report_dir)
    try:
        run_render(date, report_dir)
    except Exception as exc:
        progress(date, "3", "4", "fail", f"hybrid 视频合成失败: {exc}", paths(date, report_dir)["video"])
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["spec", "assets", "render", "pipeline", "status"])
    parser.add_argument("--date", required=True)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()

    if args.mode == "spec":
        run_spec(args.date, args.report_dir)
    elif args.mode == "assets":
        run_assets(args.date, args.report_dir)
    elif args.mode == "render":
        run_render(args.date, args.report_dir)
    elif args.mode == "pipeline":
        pipeline(args.date, args.report_dir)
    elif args.mode == "status":
        status(args.date, args.report_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
