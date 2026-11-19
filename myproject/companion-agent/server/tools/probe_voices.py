"""探测火山 seed-tts-2.0 下哪些 speaker id 真能出声。

用法（server/ 目录，.env 里有 VOLC_* 凭据）：
    PYTHONPATH=src .venv/bin/python tools/probe_voices.py [id ...]

不打印任何凭据，只报告每个 id 的成败与音频长度。角色卡里的 ``voice_id`` 必须是
这里验证过的值——写一个不存在的 speaker，线上表现是语音回合只有静音加一条 400。
"""

import asyncio
import sys

from companion.worker import load_env

load_env()

from companion.service.voice.volcengine_livekit import NewConsoleTTS

LINE = "先说清楚你现在卡在哪儿，我们再一起看下一步。"

#: 常见候选：seed-tts-2.0 的 saturn 系列。名字是猜的，所以必须实测。
CANDIDATES = [
    "saturn_zh_female_keainvsheng_tob",
    "saturn_zh_female_wenroujiejie_tob",
    "saturn_zh_female_zhixingjiejie_tob",
    "saturn_zh_male_chengshudashu_tob",
    "saturn_zh_male_lengjunxingnan_tob",
    "saturn_zh_male_wenrouxuezhang_tob",
    "saturn_zh_male_qingniandashu_tob",
    "zh_male_calm",
    "male_calm",
    "female_warm",
]


async def probe(voice: str) -> tuple[str, bool, str]:
    tts = NewConsoleTTS(voice=voice, sample_rate=16000)
    try:
        stream = tts.stream()
        stream.push_text(LINE)
        stream.end_input()
        frames = [ev.frame async for ev in stream]
        await stream.aclose()
        pcm = b"".join(bytes(f.data) for f in frames)
        if not pcm:
            return voice, False, "无音频帧"
        seconds = len(pcm) / (2 * frames[0].sample_rate)
        return voice, True, f"{seconds:.2f}s"
    except Exception as exc:  # noqa: BLE001 —— 探测就是要看每一种失败长什么样
        return voice, False, f"{type(exc).__name__}: {str(exc)[:120]}"


async def main(voices: list[str]) -> int:
    from livekit.agents.utils import http_context

    async with http_context.open():
        for voice in voices:
            name, ok, detail = await probe(voice)
            print(f"{'OK  ' if ok else 'FAIL'} {name:46s} {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:] or CANDIDATES)))
