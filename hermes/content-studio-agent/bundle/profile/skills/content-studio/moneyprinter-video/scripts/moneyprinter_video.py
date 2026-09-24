#!/usr/bin/env python3
"""MoneyPrinterTurbo 通用短视频生成器（独立于 GitHub 滚动核心链路）。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

TASK_STATE_FAILED = -1
TASK_STATE_COMPLETE = 1
TASK_STATE_PROCESSING = 4

_STAGE_DIRECTION_LINE = re.compile(
    r"^\s*(?:[（(\[]\s*)?"
    r"(?:开场|结尾|第一个|第二个|第三个|第四个|第五个|过渡|转场|pause|break)"
    r"(?:\s*[）)\]]\s*)?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


class MoneyPrinterError(RuntimeError):
    """MoneyPrinterTurbo 视频生成失败。"""


def task_sidecar_path(output_path: Path) -> Path:
    """Sidecar JSON beside the intended mp4 (…-mpt-video.mpt-task.json)."""
    return output_path.with_suffix(".mpt-task.json")


def save_task_sidecar(
    output_path: Path,
    *,
    task_id: str,
    base_url: str,
    script_path: Path,
    voice_name: str,
    video_aspect: str,
    poll_seconds: int,
    last_progress: int | float = 0,
) -> Path:
    """Persist task_id so video-mpt-resume can continue polling."""
    sidecar = task_sidecar_path(output_path)
    payload = {
        "task_id": task_id,
        "base_url": base_url.rstrip("/"),
        "script": str(script_path),
        "output": str(output_path),
        "voice_name": voice_name,
        "video_aspect": video_aspect,
        "poll_seconds": poll_seconds,
        "last_progress": last_progress,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    sidecar.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"💾 任务 sidecar: {sidecar}")
    return sidecar


def load_task_sidecar(output_path: Path) -> dict[str, object]:
    sidecar = task_sidecar_path(output_path)
    if not sidecar.exists():
        msg = f"无 MPT sidecar（无法 resume）: {sidecar}"
        raise MoneyPrinterError(msg)
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("task_id"):
        msg = f"sidecar 无效: {sidecar}"
        raise MoneyPrinterError(msg)
    return data


def clear_task_sidecar(output_path: Path) -> None:
    task_sidecar_path(output_path).unlink(missing_ok=True)


def sanitize_narration_text(text: str) -> str:
    """Remove stage-direction lines before TTS."""
    cleaned = _STAGE_DIRECTION_LINE.sub("", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_narration(script_path: Path) -> str:
    """从视频脚本 Markdown 中提取纯口播文本。"""
    text = script_path.read_text(encoding="utf-8")
    match = re.search(
        r"## 完整口播文本[^\n]*\n(.*?)(?=\n---|\n##|$)",
        text,
        re.DOTALL,
    )
    if match:
        narration = match.group(1).strip()
        narration = re.sub(r"\*+", "", narration)
        narration = re.sub(r"`+", "", narration)
        return sanitize_narration_text(narration)

    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if (
            stripped
            and not stripped.startswith("#")
            and not stripped.startswith("|")
            and not stripped.startswith("```")
            and not stripped.startswith("-")
        ):
            clean = re.sub(r"\*+|`+|#+", "", stripped).strip()
            if clean:
                lines.append(clean)
    return sanitize_narration_text("\n".join(lines[:30]))


def extract_video_subject(script_path: Path) -> str:
    """从脚本提取视频主题关键词。"""
    text = script_path.read_text(encoding="utf-8")
    match = re.search(r"## 本期主题[^\n]*\n(.*?)(?=\n---|\n##|$)", text, re.DOTALL)
    if match:
        subject = match.group(1).strip()
        subject = re.sub(r"\*+|`+|#+", "", subject)
        subject = re.sub(r"\s+", " ", subject).strip()
        if subject:
            return subject[:200]
    return script_path.stem.replace("-video-script", "")[:200]


def normalize_video_url(base_url: str, url: str) -> str:
    """Normalize MoneyPrinterTurbo task output paths to downloadable URLs."""
    base = base_url.rstrip("/")
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/api/v1/"):
        return f"{base}{url}"
    if url.startswith("/tasks/"):
        rel = url.removeprefix("/tasks/")
        return f"{base}/api/v1/download/{rel}"
    if url.startswith("/"):
        return f"{base}{url}"
    return f"{base}/api/v1/download/{url}"


def _http_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    timeout: int = 120,
) -> dict[str, object]:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        msg = f"HTTP {exc.code} {url}: {detail[:500]}"
        raise MoneyPrinterError(msg) from exc
    except urllib.error.URLError as exc:
        msg = f"无法连接 MoneyPrinterTurbo ({url}): {exc.reason}"
        raise MoneyPrinterError(msg) from exc

    if not isinstance(body, dict):
        msg = f"无效 JSON 响应: {url}"
        raise MoneyPrinterError(msg)
    return body


def _unwrap_data(body: dict[str, object]) -> dict[str, object]:
    data = body.get("data")
    if isinstance(data, dict):
        return data
    return body


def pick_video_urls(data: dict[str, object]) -> list[str]:
    """Return downloadable video URLs, preferring final mix over B-roll-only combined clips.

    MoneyPrinterTurbo exposes:
    - ``videos``: final-*.mp4 with narration + BGM
    - ``combined_videos``: combined-*.mp4 video-only (no audio track)
    """
    urls: list[str] = []
    finals = data.get("videos")
    if isinstance(finals, list):
        urls.extend(str(item) for item in finals if item)
    combined = data.get("combined_videos")
    if isinstance(combined, list):
        urls.extend(str(item) for item in combined if item)
    return urls


def has_audio_stream(video_path: Path) -> bool:
    """Return True if the mp4 contains at least one audio stream."""
    result = subprocess.run(
        [
            "ffprobe",
            "-hide_banner",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and "audio" in result.stdout


def download_best_video(
    base_url: str,
    video_urls: list[str],
    dest: Path,
    *,
    timeout: int = 300,
) -> None:
    """Download the first URL with an audio track, or the first URL if probe unavailable."""
    if not video_urls:
        msg = "MoneyPrinterTurbo 未返回可下载视频路径"
        raise MoneyPrinterError(msg)

    last_error: MoneyPrinterError | None = None
    for index, raw_url in enumerate(video_urls):
        download_url = normalize_video_url(base_url, raw_url)
        tmp = dest.with_suffix(f".download{index}.mp4")
        try:
            print(f"⬇️  下载成片 ({index + 1}/{len(video_urls)}): {download_url}")
            download_file(download_url, tmp, timeout=timeout)
            if has_audio_stream(tmp) or index == len(video_urls) - 1:
                if not has_audio_stream(tmp):
                    print(
                        "⚠️  下载的 mp4 无音轨（可能为 combined 纯画面版）",
                        file=sys.stderr,
                    )
                tmp.replace(dest)
                return
            print("⚠️  该版本无音轨，尝试下一个 URL…", file=sys.stderr)
            tmp.unlink(missing_ok=True)
        except MoneyPrinterError as exc:
            tmp.unlink(missing_ok=True)
            last_error = exc

    if last_error is not None:
        raise last_error
    msg = f"无法下载有效视频: {dest}"
    raise MoneyPrinterError(msg)


def download_file(url: str, dest: Path, *, timeout: int = 300) -> None:
    """Download remote video to local path."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, dest.open("wb") as out:
            out.write(resp.read())
    except urllib.error.URLError as exc:
        msg = f"下载视频失败 {url}: {exc.reason}"
        raise MoneyPrinterError(msg) from exc
    if not dest.exists() or dest.stat().st_size <= 1024:
        dest.unlink(missing_ok=True)
        msg = f"下载结果无效: {dest}"
        raise MoneyPrinterError(msg)


def extract_cover_frame(video_path: Path, output_path: Path) -> bool:
    """Extract cover frame from generated video."""
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            "1",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output_path),
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
        return True
    if output_path.exists() and output_path.stat().st_size == 0:
        output_path.unlink()
    return False


def write_publish_guide(
    script_path: Path,
    video_path: Path,
    cover_path: Path,
    *,
    engine_label: str = "MoneyPrinterTurbo",
) -> Path:
    """Write Xiaohongshu publish guide for MPT output."""
    script_text = script_path.read_text(encoding="utf-8")
    title_match = re.search(r"### 标题备选.*?\n(.*?)(?=###|$)", script_text, re.DOTALL)
    titles = title_match.group(1).strip() if title_match else "「今日 GitHub 热榜解读」"
    tag_match = re.search(r"### 标签\n(.*?)(?=###|$)", script_text, re.DOTALL)
    tags = tag_match.group(1).strip() if tag_match else "#GitHub #开源 #AI #程序员"

    today = script_path.stem.replace("-video-script", "")
    publish_path = script_path.parent / f"{today}-mpt-video-publish.md"
    guide = f"""# 小红书发布指引 — {today}（{engine_label}）

## 快速发布步骤

1. 打开创作者中心：<https://creator.xiaohongshu.com/publish/publish>
2. 选择「发布视频」
3. 上传视频：`{video_path}`
4. 封面：上传 `{cover_path}`（若不存在则截取视频第 1 帧）
5. 标题：见下方推荐
6. 正文：见下方模板
7. 标签：见下方标签

---

## 标题推荐（A/B 任选一）

{titles}

---

## 正文模板

（将脚本中项目介绍复制到这里）

感兴趣的评论区告诉我，明天继续 ~

{tags}

---

## 文件路径

- 视频：`{video_path}`
- 封面：`{cover_path}`
- 脚本：`{script_path}`
- 引擎：{engine_label}
"""
    publish_path.write_text(guide, encoding="utf-8")
    return publish_path


def submit_video_task(
    *,
    base_url: str,
    video_subject: str,
    video_script: str,
    voice_name: str,
    video_aspect: str,
    poll_seconds: int,
    timeout_seconds: int,
) -> str:
    """Submit video generation task and return task_id."""
    payload: dict[str, object] = {
        "video_subject": video_subject[:200],
        "video_script": video_script,
        "video_language": "zh-CN",
        "video_aspect": video_aspect,
        # MPT schema 默认 pexels，但 profile 通常只配 pixabay key；显式指定避免卡在 40%。
        "video_source": "pixabay",
        "voice_name": voice_name,
        "voice_rate": 1.0,
        "bgm_type": "random",
        "bgm_volume": 0.15,
        "subtitle_enabled": True,
        "subtitle_position": "bottom",
        "font_size": 48,
        "n_threads": 2,
    }
    body = _http_json(
        f"{base_url.rstrip('/')}/api/v1/videos",
        method="POST",
        payload=payload,
        timeout=120,
    )
    data = _unwrap_data(body)
    task_id = data.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        msg = f"MoneyPrinterTurbo 未返回 task_id: {body}"
        raise MoneyPrinterError(msg)
    print(f"⏳ MoneyPrinterTurbo 任务 {task_id} 已提交，等待生成（最多 {timeout_seconds // 60} 分钟）…")
    return task_id


def poll_video_task(
    *,
    base_url: str,
    task_id: str,
    poll_seconds: int,
    timeout_seconds: int,
    output_path: Path | None = None,
    script_path: Path | None = None,
    voice_name: str = "",
    video_aspect: str = "9:16",
) -> list[str]:
    """Poll task until complete and return downloadable video URLs."""
    deadline = time.time() + timeout_seconds
    last_progress: int | float = 0
    while time.time() < deadline:
        time.sleep(poll_seconds)
        body = _http_json(
            f"{base_url.rstrip('/')}/api/v1/tasks/{task_id}",
            timeout=60,
        )
        data = _unwrap_data(body)
        state = data.get("state")
        progress = data.get("progress", 0)
        last_progress = progress if isinstance(progress, (int, float)) else 0
        print(f"  状态: state={state} progress={progress}")

        if output_path is not None and script_path is not None:
            save_task_sidecar(
                output_path,
                task_id=task_id,
                base_url=base_url,
                script_path=script_path,
                voice_name=voice_name,
                video_aspect=video_aspect,
                poll_seconds=poll_seconds,
                last_progress=last_progress,
            )

        if state == TASK_STATE_COMPLETE:
            video_urls = pick_video_urls(data)
            if video_urls:
                if output_path is not None:
                    clear_task_sidecar(output_path)
                return video_urls
            msg = f"任务完成但未返回视频路径: {data}"
            raise MoneyPrinterError(msg)
        if state == TASK_STATE_FAILED:
            if output_path is not None:
                clear_task_sidecar(output_path)
            msg = f"MoneyPrinterTurbo 任务失败: {data}"
            raise MoneyPrinterError(msg)

    if output_path is not None and script_path is not None:
        save_task_sidecar(
            output_path,
            task_id=task_id,
            base_url=base_url,
            script_path=script_path,
            voice_name=voice_name,
            video_aspect=video_aspect,
            poll_seconds=poll_seconds,
            last_progress=last_progress,
        )
        print(
            f"⚠️  轮询超时；task_id={task_id} 已写入 sidecar。"
            f" 续跑: content-studio.sh video-mpt-resume",
            file=sys.stderr,
        )
    msg = f"MoneyPrinterTurbo 超时（{timeout_seconds}s）"
    raise MoneyPrinterError(msg)


def generate_video(
    *,
    script_path: Path,
    output_path: Path,
    base_url: str,
    voice_name: str,
    video_aspect: str,
    poll_seconds: int,
    timeout_seconds: int,
) -> Path:
    """Generate video via MoneyPrinterTurbo HTTP API."""
    narration = extract_narration(script_path)
    if not narration:
        msg = f"无法从脚本提取口播文本: {script_path}"
        raise MoneyPrinterError(msg)

    subject = extract_video_subject(script_path)
    print(f"📝 口播文本 ({len(narration)} 字)，主题: {subject[:60]}…")
    print(f"🔗 MoneyPrinterTurbo: {base_url}")

    task_id = submit_video_task(
        base_url=base_url,
        video_subject=subject,
        video_script=narration,
        voice_name=voice_name,
        video_aspect=video_aspect,
        poll_seconds=poll_seconds,
        timeout_seconds=timeout_seconds,
    )
    save_task_sidecar(
        output_path,
        task_id=task_id,
        base_url=base_url,
        script_path=script_path,
        voice_name=voice_name,
        video_aspect=video_aspect,
        poll_seconds=poll_seconds,
    )
    video_urls = poll_video_task(
        base_url=base_url,
        task_id=task_id,
        poll_seconds=poll_seconds,
        timeout_seconds=timeout_seconds,
        output_path=output_path,
        script_path=script_path,
        voice_name=voice_name,
        video_aspect=video_aspect,
    )
    download_best_video(base_url, video_urls, output_path)
    print(f"✅ MoneyPrinterTurbo 视频已生成: {output_path}")
    return output_path


def resume_video(
    *,
    output_path: Path,
    timeout_seconds: int,
) -> Path:
    """Continue polling from sidecar without re-submitting."""
    sidecar = load_task_sidecar(output_path)
    task_id = str(sidecar["task_id"])
    base_url = str(sidecar.get("base_url", "http://127.0.0.1:8082"))
    script_path = Path(str(sidecar.get("script", ""))).expanduser().resolve()
    voice_name = str(sidecar.get("voice_name", "zh-CN-XiaoxiaoNeural-Female"))
    video_aspect = str(sidecar.get("video_aspect", "9:16"))
    poll_seconds = int(sidecar.get("poll_seconds", 10) or 10)
    print(f"🔁 续跑 MPT 任务 {task_id}（最多再等 {timeout_seconds // 60} 分钟）…")
    video_urls = poll_video_task(
        base_url=base_url,
        task_id=task_id,
        poll_seconds=max(3, poll_seconds),
        timeout_seconds=max(60, timeout_seconds),
        output_path=output_path,
        script_path=script_path,
        voice_name=voice_name,
        video_aspect=video_aspect,
    )
    download_best_video(base_url, video_urls, output_path)
    print(f"✅ MoneyPrinterTurbo 视频已生成: {output_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="MoneyPrinterTurbo 通用短视频生成器")
    parser.add_argument("--script", help="视频脚本 Markdown 路径（--resume 时可省略）")
    parser.add_argument("--output", required=True, help="输出视频路径 (.mp4)")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8082",
        help="MoneyPrinterTurbo 服务地址",
    )
    parser.add_argument(
        "--voice-name",
        default="zh-CN-XiaoxiaoNeural-Female",
        help="TTS 音色",
    )
    parser.add_argument(
        "--video-aspect",
        default="9:16",
        help="视频比例（小红书竖屏默认 9:16）",
    )
    parser.add_argument("--poll-seconds", type=int, default=10, help="轮询间隔秒数")
    parser.add_argument("--timeout", type=int, default=900, help="最长等待秒数")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="从 sidecar 续轮询，不重新 POST /api/v1/videos",
    )
    parser.add_argument(
        "--finalize-only",
        action="store_true",
        help="仅生成封面与发布指引（mp4 已存在时使用）",
    )
    parser.add_argument(
        "--skip-publish-guide",
        action="store_true",
        help="不生成发布指引 Markdown",
    )
    args = parser.parse_args()

    output_path = Path(args.output).expanduser().resolve()
    script_path = Path(args.script).expanduser().resolve() if args.script else Path()

    if args.finalize_only:
        if not output_path.is_file():
            print(f"❌ 视频不存在: {output_path}", file=sys.stderr)
            sys.exit(1)
        if not script_path.is_file():
            sidecar = load_task_sidecar(output_path)
            script_path = Path(str(sidecar.get("script", ""))).expanduser().resolve()
        if not script_path.is_file():
            print(f"❌ 无法确定脚本路径（sidecar 无 script）: {output_path}", file=sys.stderr)
            sys.exit(1)
    elif args.resume:
        if not script_path.is_file():
            sidecar = load_task_sidecar(output_path)
            script_path = Path(str(sidecar.get("script", ""))).expanduser().resolve()
        if not script_path.is_file():
            print(f"❌ resume 需要 sidecar 中的 script 字段: {output_path}", file=sys.stderr)
            sys.exit(1)
    elif not args.script or not script_path.is_file():
        print(f"❌ 脚本不存在或未指定: {args.script}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.finalize_only:
            pass
        elif args.resume:
            resume_video(
                output_path=output_path,
                timeout_seconds=max(60, args.timeout),
            )
        else:
            generate_video(
                script_path=script_path,
                output_path=output_path,
                base_url=args.base_url.rstrip("/"),
                voice_name=args.voice_name,
                video_aspect=args.video_aspect,
                poll_seconds=max(3, args.poll_seconds),
                timeout_seconds=max(60, args.timeout),
            )
    except MoneyPrinterError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(1)

    if args.finalize_only or args.resume:
        if not script_path.is_file():
            sidecar = load_task_sidecar(output_path)
            script_path = Path(str(sidecar.get("script", ""))).expanduser().resolve()

    cover_path = output_path.with_name(output_path.stem + "-cover.jpg")
    if extract_cover_frame(output_path, cover_path):
        print(f"🖼️  封面已提取: {cover_path}")
    else:
        cover_path = output_path
        print("⚠️  封面提取失败，发布时使用视频首帧")

    if not args.skip_publish_guide:
        publish_path = write_publish_guide(script_path, output_path, cover_path)
        print(f"📋 发布指引: {publish_path}")


if __name__ == "__main__":
    main()
