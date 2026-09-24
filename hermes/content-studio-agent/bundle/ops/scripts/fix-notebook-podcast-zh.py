#!/usr/bin/env python3
"""Set Content Studio episode/speaker profiles for Chinese GitHub-style podcasts.

Writes Open Notebook DB profiles via API (no Open Notebook source changes).
Short-form prompt templates are injected by ``content_studio_podcast_bootstrap`` at worker start.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

DEFAULT_API = "http://127.0.0.1:5055"

# Open Notebook allows num_segments 3–20; use 3 (minimum) for short daily briefings.
SOLO_NUM_SEGMENTS = 3

SOLO_BRIEFING = """你是一位中文科技口播作者。请严格基于用户提供的笔记本资料生成播客。

硬性要求：
1. 全程使用简体中文口播（专有名词如 GitHub、项目仓库名可保留英文）
2. 必须引用资料中的具体项目名、榜单、要点，不要改写成泛泛的英文科普
3. 风格：短视频口播，开场 10 秒要有 hook，句子短、信息密度高
4. 若资料含「今日 GitHub TOP / 热榜 / 开源项目」，必须按资料顺序介绍这些项目
5. 不要编造资料里没有的项目或数据

时长与篇幅（必须遵守）：
6. 全 episode 口播稿总字数（含标点）≤ 600 字，目标音频时长 2–3 分钟
7. 大纲恰好 3 段（num_segments=3），不要单独的开场段/结尾段
8. 每段 size 必须为 short，禁止 medium 和 long
9. 每轮对话不超过 80 字，避免长段独白和重复信息"""

SOLO_SPEAKER = {
    "name": "科技主播",
    "personality": "节奏明快、口语化，像给开发者朋友讲今日 GitHub 热榜",
    "backstory": "资深开源社区观察者，擅长把 GitHub Trending 讲成 3 分钟能听完的口播稿",
    "voice_id": "nova",
}


def _get(base: str, path: str) -> list | dict:
    with urllib.request.urlopen(f"{base}{path}", timeout=30) as resp:
        return json.loads(resp.read())


def _put(base: str, path: str, body: dict) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode()
    req = urllib.request.Request(
        f"{base}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API, help="Open Notebook API base URL")
    args = parser.parse_args()
    base = args.api_url.rstrip("/")

    try:
        profiles = _get(base, "/api/episode-profiles")
        speakers = _get(base, "/api/speaker-profiles")
    except urllib.error.URLError as exc:
        print(f"API unavailable: {exc}", file=sys.stderr)
        return 1

    for p in profiles:
        if p.get("name") != "solo_expert":
            continue
        _put(
            base,
            f"/api/episode-profiles/{p['id']}",
            {
                "name": "solo_expert",
                "description": "中文短口播（≤600字，3段，solo_expert）",
                "speaker_config": p["speaker_config"],
                "outline_llm": p.get("outline_llm"),
                "transcript_llm": p.get("transcript_llm"),
                "language": "zh-CN",
                "default_briefing": SOLO_BRIEFING,
                "num_segments": SOLO_NUM_SEGMENTS,
            },
        )
        print(
            f"updated episode profile: solo_expert "
            f"(zh-CN briefing, num_segments={SOLO_NUM_SEGMENTS})"
        )

    for sp in speakers:
        if sp.get("name") != "solo_expert":
            continue
        new_speakers = [{**SOLO_SPEAKER}]
        _put(
            base,
            f"/api/speaker-profiles/{sp['id']}",
            {
                "name": "solo_expert",
                "description": "中文科技口播单人主持",
                "voice_model": sp.get("voice_model"),
                "speakers": new_speakers,
                "tts_provider": sp.get("tts_provider"),
                "tts_model": sp.get("tts_model"),
            },
        )
        print("updated speaker profile: solo_expert (中文主播)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
