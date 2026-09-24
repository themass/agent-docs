#!/usr/bin/env python3
"""Build markdown and HTML indexes for Content Studio generated reports."""

from __future__ import annotations

import argparse
import html
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


REPORT_KINDS = {
    "production-radar": "生产级工具雷达",
    "community-pulse": "社区脉搏简报",
    "video-cover": "视频封面",
    "video-file": "视频成片",
    "video-publish": "视频发布指引",
    "video-script": "视频脚本",
    "weekly": "周报",
    "daily": "日报",
}


def detect_kind(path: Path) -> str:
    stem = path.stem
    if stem.endswith("-video-cover"):
        return "video-cover"
    if stem.endswith("-video"):
        return "video-file"
    if stem.endswith("-production-radar"):
        return "production-radar"
    if stem.endswith("-community-pulse"):
        return "community-pulse"
    if stem.endswith("-video-publish"):
        return "video-publish"
    if stem.endswith("-video-script"):
        return "video-script"
    if stem.endswith("-weekly"):
        return "weekly"
    return "daily"


def report_date(path: Path) -> str:
    stem = path.stem
    for suffix in (
        "-video-cover",
        "-video",
        "-production-radar",
        "-community-pulse",
        "-video-publish",
        "-video-script",
        "-weekly",
    ):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def title(path: Path) -> str:
    if path.suffix.lower() in {".mp4", ".jpg", ".jpeg", ".png", ".webp"}:
        return path.name
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.name


def collect_reports(root: Path) -> list[Path]:
    markdown_reports = [
        path
        for path in root.glob("*/*/*.md")
        if path.name != "index.md"
        and not path.name.endswith(".invalid.md")
        and path.is_file()
    ]
    media_reports = [
        path
        for pattern in ("*/*/*-video.mp4", "*/*/*-video-cover.jpg")
        for path in root.glob(pattern)
        if path.is_file()
    ]
    reports = markdown_reports + media_reports
    reports.sort(key=lambda path: (report_date(path), detect_kind(path)), reverse=True)
    return reports


def build_index(root: Path) -> str:
    reports = collect_reports(root)
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path in reports:
        grouped[report_date(path)].append(path)

    lines = [
        "# 内容策划主编报告索引",
        "",
        f"更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "在浏览器中查看（推荐）：运行 `content-studio.sh browse` 或 Workspace Chat 说 **打开报告库网页**。",
        "",
        "## 最近报告",
        "",
    ]

    if not reports:
        lines.append("_暂无报告。_")
        return "\n".join(lines) + "\n"

    for date in sorted(grouped.keys(), reverse=True):
        lines.extend([f"### {date}", ""])
        for path in sorted(grouped[date], key=lambda item: detect_kind(item)):
            kind = REPORT_KINDS[detect_kind(path)]
            rel = path.relative_to(root)
            lines.append(f"- **{kind}**: [{title(path)}]({rel.as_posix()})")
        lines.append("")

    lines.extend(
        [
            "## 文件命名规则",
            "",
            "- `YYYY-MM-DD.md`：日报",
            "- `YYYY-MM-DD-weekly.md`：周报",
            "- `YYYY-MM-DD-production-radar.md`：生产级工具雷达",
            "- `YYYY-MM-DD-community-pulse.md`：社区脉搏简报",
            "- `YYYY-MM-DD-video-script.md`：视频脚本",
            "- `YYYY-MM-DD-video-publish.md`：视频发布指引",
            "- `YYYY-MM-DD-video.mp4`：视频成片",
            "- `YYYY-MM-DD-video-cover.jpg`：视频封面",
            "",
            "## Chat 指令（无需记命令）",
            "",
            "- `报告库` / `打开报告库网页`：浏览全部报告",
            "- `打开最新日报`",
            "- `打开最新视频`",
            "",
        ]
    )
    return "\n".join(lines)


def build_catalog(root: Path) -> list[dict[str, object]]:
    """JSON-serializable catalog for the HTML viewer."""
    catalog: list[dict[str, object]] = []
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path in collect_reports(root):
        grouped[report_date(path)].append(path)

    for date in sorted(grouped.keys(), reverse=True):
        items: list[dict[str, str]] = []
        for path in sorted(grouped[date], key=lambda item: detect_kind(item)):
            rel = path.relative_to(root).as_posix()
            suffix = path.suffix.lower()
            media_type = "markdown"
            if suffix == ".mp4":
                media_type = "video"
            elif suffix in {".jpg", ".jpeg", ".png", ".webp"}:
                media_type = "image"
            items.append(
                {
                    "kind": REPORT_KINDS[detect_kind(path)],
                    "title": title(path),
                    "path": rel,
                    "mediaType": media_type,
                }
            )
        catalog.append({"date": date, "items": items})
    return catalog


def build_html(root: Path) -> str:
    catalog = build_catalog(root)
    updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    catalog_json = json.dumps(catalog, ensure_ascii=False)
    updated_escaped = html.escape(updated)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>内容策划主编 · 报告库</title>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    :root {{
      --bg: #0f1419;
      --panel: #1a2332;
      --panel-hover: #243044;
      --border: #2d3a4d;
      --text: #e7ecf3;
      --muted: #8b9cb3;
      --accent: #3b82f6;
      --accent-soft: rgba(59, 130, 246, 0.15);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
        "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }}
    header {{
      padding: 1.25rem 1.5rem;
      border-bottom: 1px solid var(--border);
      background: linear-gradient(135deg, #1a2332 0%, #0f1419 100%);
    }}
    header h1 {{ margin: 0 0 0.35rem; font-size: 1.35rem; font-weight: 600; }}
    header p {{ margin: 0; color: var(--muted); font-size: 0.9rem; }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(240px, 320px) 1fr;
      min-height: calc(100vh - 76px);
    }}
    @media (max-width: 768px) {{
      .layout {{ grid-template-columns: 1fr; }}
      aside {{ max-height: 40vh; border-right: none; border-bottom: 1px solid var(--border); }}
    }}
    aside {{
      overflow-y: auto;
      border-right: 1px solid var(--border);
      background: var(--panel);
      padding: 0.75rem;
    }}
    .day {{ margin-bottom: 1rem; }}
    .day-title {{
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
      margin: 0 0 0.5rem 0.35rem;
    }}
    .item {{
      display: block;
      width: 100%;
      text-align: left;
      border: 1px solid transparent;
      border-radius: 8px;
      padding: 0.55rem 0.65rem;
      margin-bottom: 0.35rem;
      background: transparent;
      color: var(--text);
      cursor: pointer;
      font: inherit;
    }}
    .item:hover {{ background: var(--panel-hover); }}
    .item.active {{
      background: var(--accent-soft);
      border-color: var(--accent);
    }}
    .item-kind {{ font-size: 0.72rem; color: var(--accent); margin-bottom: 0.15rem; }}
    .item-title {{ font-size: 0.88rem; line-height: 1.35; }}
    main {{
      overflow-y: auto;
      padding: 1.5rem 2rem 3rem;
      max-width: 52rem;
    }}
    .empty {{
      color: var(--muted);
      padding: 3rem 1rem;
      text-align: center;
    }}
    .content h1, .content h2, .content h3 {{ margin-top: 1.5rem; }}
    .content a {{ color: #93c5fd; }}
    .content pre {{
      background: #0b0f14;
      padding: 1rem;
      border-radius: 8px;
      overflow-x: auto;
    }}
    .content table {{ border-collapse: collapse; width: 100%; }}
    .content th, .content td {{
      border: 1px solid var(--border);
      padding: 0.4rem 0.6rem;
    }}
    .media-box {{
      margin-top: 1rem;
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid var(--border);
    }}
    .media-box video, .media-box img {{ display: block; max-width: 100%; }}
  </style>
</head>
<body>
  <header>
    <h1>内容策划主编 · 报告库</h1>
    <p>更新于 {updated_escaped} · 左侧选报告，右侧阅读</p>
  </header>
  <div class="layout">
    <aside id="sidebar"></aside>
    <main>
      <div id="viewer" class="empty">← 从左侧选择一份报告</div>
    </main>
  </div>
  <script id="catalog-data" type="application/json">{catalog_json}</script>
  <script>
    const catalog = JSON.parse(document.getElementById("catalog-data").textContent);
    const sidebar = document.getElementById("sidebar");
    const viewer = document.getElementById("viewer");
    let activeBtn = null;

    function setActive(btn) {{
      if (activeBtn) activeBtn.classList.remove("active");
      activeBtn = btn;
      if (btn) btn.classList.add("active");
    }}

    async function showItem(item) {{
      viewer.className = "content";
      viewer.innerHTML = "<p style='color:var(--muted)'>加载中…</p>";
      if (item.mediaType === "markdown") {{
        const res = await fetch(item.path);
        if (!res.ok) {{
          viewer.innerHTML = "<p>无法加载：" + item.path + "</p>";
          return;
        }}
        const text = await res.text();
        viewer.innerHTML = marked.parse(text);
        return;
      }}
      if (item.mediaType === "video") {{
        viewer.innerHTML =
          '<h2>' + item.title + '</h2>' +
          '<div class="media-box"><video controls src="' + item.path + '"></video></div>';
        return;
      }}
      if (item.mediaType === "image") {{
        viewer.innerHTML =
          '<h2>' + item.title + '</h2>' +
          '<div class="media-box"><img alt="" src="' + item.path + '" /></div>';
        return;
      }}
      viewer.innerHTML = "<p>不支持的类型</p>";
    }}

    if (!catalog.length) {{
      sidebar.innerHTML = "<p class='empty'>暂无报告</p>";
    }} else {{
      catalog.forEach((day) => {{
        const section = document.createElement("div");
        section.className = "day";
        const heading = document.createElement("p");
        heading.className = "day-title";
        heading.textContent = day.date;
        section.appendChild(heading);
        day.items.forEach((item) => {{
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "item";
          btn.innerHTML =
            '<div class="item-kind">' + item.kind + '</div>' +
            '<div class="item-title">' + item.title + '</div>';
          btn.addEventListener("click", () => {{
            setActive(btn);
            showItem(item);
          }});
          section.appendChild(btn);
        }});
        sidebar.appendChild(section);
      }});
      const first = catalog[0]?.items?.[0];
      if (first) {{
        const firstBtn = sidebar.querySelector(".item");
        if (firstBtn) {{
          firstBtn.click();
        }}
      }}
    }}
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-dir",
        default="~/.hermes/profiles/content-studio/reports",
        help="Report root directory.",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Also write index.html for the browser viewer.",
    )
    args = parser.parse_args()

    root = Path(args.report_dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    index_md = root / "index.md"
    index_md.write_text(build_index(root), encoding="utf-8")
    print(index_md)
    if args.html:
        index_html = root / "index.html"
        index_html.write_text(build_html(root), encoding="utf-8")
        print(index_html)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
