#!/usr/bin/env python3
"""OpenAI-compatible TTS proxy for Volcengine (火山引擎) speech synthesis.

Exposes POST /v1/audio/speech so Open Notebook / Esperanto can use volcano TTS
via the openai_compatible provider.

Environment:
    VOLCENGINE_APP_ID / VOLCENGINE_TOKEN — required
    VOLCENGINE_CLUSTER — default volcano_tts
    VOLCENGINE_VOICE_TYPE — default voice when request voice is unknown
    VOLCENGINE_TTS_PROXY_PORT — listen port (default 8968)
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

VOLCENGINE_API_URL = "https://openspeech.bytedance.com/api/v1/tts"

# Map Open Notebook / OpenAI voice aliases to Volcengine voice_type IDs.
VOICE_MAP: dict[str, str] = {
    "alloy": "zh_male_M392_conversation_wvae_bigtts",
    "echo": "zh_male_M392_conversation_wvae_bigtts",
    "fable": "zh_female_wanwanxiaohe_moon_bigtts",
    "onyx": "zh_male_M392_conversation_wvae_bigtts",
    "nova": "zh_female_wanwanxiaohe_moon_bigtts",
    "shimmer": "zh_female_shuangkuaisisi_moon_bigtts",
    "default": "zh_female_wanwanxiaohe_moon_bigtts",
}


class SpeechRequest(BaseModel):
    input: str = Field(..., min_length=1)
    model: str = "volcano-tts"
    voice: str = "nova"
    response_format: str = "mp3"
    speed: float | None = None


def _volc_credentials() -> tuple[str, str]:
    app_id = os.getenv("VOLCENGINE_APP_ID", "").strip()
    token = os.getenv("VOLCENGINE_TOKEN", "").strip()
    if not app_id or not token:
        msg = (
            "VOLCENGINE_APP_ID and VOLCENGINE_TOKEN must be set for volcano TTS proxy"
        )
        raise HTTPException(status_code=503, detail=msg)
    return app_id, token


def _resolve_voice(voice: str) -> str:
    voice = (voice or "nova").strip()
    if voice in VOICE_MAP:
        return VOICE_MAP[voice]
    if "_" in voice or voice.startswith("zh_") or voice.startswith("BV"):
        return voice
    return os.getenv("VOLCENGINE_VOICE_TYPE", VOICE_MAP["default"])


def synthesize_volcengine(text: str, voice: str, speed: float | None) -> bytes:
    app_id, token = _volc_credentials()
    cluster = os.getenv("VOLCENGINE_CLUSTER", "volcano_tts")
    voice_type = _resolve_voice(voice)
    speed_ratio = speed if speed is not None else float(os.getenv("VOLCENGINE_SPEED_RATIO", "1.1"))

    payload: dict[str, Any] = {
        "app": {"appid": app_id, "token": token, "cluster": cluster},
        "user": {"uid": "open-notebook"},
        "audio": {
            "voice_type": voice_type,
            "encoding": "mp3",
            "speed_ratio": speed_ratio,
            "volume_ratio": 1.0,
            "pitch_ratio": 1.0,
        },
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": text,
            "text_type": "plain",
            "operation": "query",
            "with_frontend": 1,
            "frontend_type": "unitTson",
        },
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer;{token}",
    }

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(VOLCENGINE_API_URL, headers=headers, json=payload)
        resp.raise_for_status()
        body = resp.json()

    if body.get("code") != 3000:
        msg = body.get("message") or json.dumps(body, ensure_ascii=False)[:500]
        raise HTTPException(status_code=502, detail=f"Volcengine TTS error: {msg}")

    data_b64 = body.get("data")
    if not data_b64:
        raise HTTPException(status_code=502, detail="Volcengine TTS returned empty audio")

    return base64.b64decode(data_b64)


app = FastAPI(title="Volcengine TTS Proxy", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "provider": "volcengine"}


@app.get("/v1/models")
def list_models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [{"id": "volcano-tts", "object": "model", "owned_by": "volcengine"}],
    }


@app.post("/v1/audio/speech")
def audio_speech(req: SpeechRequest) -> Response:
    audio = synthesize_volcengine(req.input, req.voice, req.speed)
    media = "audio/mpeg" if req.response_format in {"mp3", "mpeg"} else "audio/wav"
    return Response(content=audio, media_type=media)


def main() -> None:
    port = int(os.getenv("VOLCENGINE_TTS_PROXY_PORT", "8968"))
    host = os.getenv("VOLCENGINE_TTS_PROXY_HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
