"""按环境变量选择 LLM 后端：LiveKit Inference 或 Hermes Gateway（OpenAI 兼容）。"""

from __future__ import annotations

import os

from livekit.agents import inference


def create_llm():
    """创建 AgentSession 使用的 LLM 实例。

    HERMES_COMPANION_LLM:
      - ``inference``（默认）：LiveKit Inference，需 LIVEKIT_API_KEY
      - ``hermes``：Hermes Gateway ``/v1/chat/completions``（需 gateway 运行）
    """
    mode = os.environ.get("HERMES_COMPANION_LLM", "inference").strip().lower()
    if mode == "hermes":
        from livekit.plugins import openai

        base = os.environ.get("HERMES_GATEWAY_URL", "http://127.0.0.1:8642/v1")
        key = os.environ.get("HERMES_API_KEY") or os.environ.get("API_SERVER_KEY", "change-me-local-dev")
        model = os.environ.get("HERMES_MODEL", "hermes-agent")
        return openai.LLM(model=model, base_url=base, api_key=key)

    model = os.environ.get("LIVEKIT_LLM_MODEL", "openai/gpt-4.1-mini")
    return inference.LLM(model)


def create_stt():
    """STT：默认 Deepgram，中文优先。"""
    model = os.environ.get("LIVEKIT_STT_MODEL", "deepgram/nova-3")
    lang = os.environ.get("HERMES_COMPANION_STT_LANG", "zh")
    return inference.STT(model, language=lang)


def create_tts():
    """TTS：默认 Cartesia；可通过环境变量换音色。"""
    model = os.environ.get("LIVEKIT_TTS_MODEL", "cartesia/sonic-3")
    voice = os.environ.get("HERMES_COMPANION_TTS_VOICE", "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc")
    return inference.TTS(model, voice=voice)
