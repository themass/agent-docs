"""用真实的火山 TTS/ASR 做一次“合成 → 识别 → 字错率”往返，验证 TTS 准确性检查这条链路能跑通。

用法（在 server/ 目录，.env 里已配 VOLC_* 凭据）：
    PYTHONPATH=src .venv/bin/python tools/qa_tts_roundtrip.py ["要念的句子" ...]

它不碰数据库和对象存储，只花几次合成与识别的调用费。结果解读见 app/voice/tts_accuracy.py 的文档：
这是相对指标，不能当作“念得完全正确”的证明。
"""

import asyncio
import sys

from companion.worker import load_env

load_env()      # 适配器直接读 os.environ，不读 .env

from companion.adapters.voice.stt_transcribe import transcribe_wav
from companion.domain.voice.tts_capture import pcm_to_wav
from companion.adapters.voice.volcengine_livekit import NewConsoleSTT, NewConsoleTTS
from companion.app.voice.tts_accuracy import cer

DEFAULT_SENTENCES = [
    "先歇一会儿，我在这儿陪着你。",
    "明天下午三点有一场面试，别紧张。",
    "你昨天说最近睡得不太好，今天感觉怎么样？",
]


async def main(sentences: list[str]) -> int:
    import os

    tts = NewConsoleTTS(voice=os.getenv("VOLC_TTS_VOICE") or "saturn_zh_female_keainvsheng_tob", sample_rate=16000)
    stt = NewConsoleSTT()
    rates = []
    for text in sentences:
        # 插件的 TTS 只实现了流式接口（和线上 tts_node 走的是同一条路径）
        stream = tts.stream()
        stream.push_text(text)
        stream.end_input()
        frames = [ev.frame async for ev in stream]
        await stream.aclose()
        rate, channels = frames[0].sample_rate, frames[0].num_channels
        pcm = b"".join(bytes(f.data) for f in frames)
        wav = pcm_to_wav(pcm, sample_rate=rate, channels=channels)
        heard = await transcribe_wav(stt, wav)
        c = cer(text, heard)
        rates.append(c.rate)
        print(f"audio={len(pcm) / (2 * channels * rate):.2f}s  CER={c.rate:.3f}\n  念的: {text}\n  听到: {heard}")
    print(f"\n平均 CER = {sum(rates) / len(rates):.3f}（{len(rates)} 句）")
    return 0


if __name__ == "__main__":
    from livekit.agents.utils import http_context

    async def _run() -> int:
        # 在 worker 之外用插件，需要自己提供 HTTP 会话（插件内部从这里取）
        async with http_context.open():
            return await main(sys.argv[1:] or DEFAULT_SENTENCES)

    raise SystemExit(asyncio.run(_run()))
