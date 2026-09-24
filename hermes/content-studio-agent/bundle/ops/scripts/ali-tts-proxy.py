#!/usr/bin/env python3
"""OpenAI-compatible TTS proxy for Aliyun NLS (阿里语音合成).

Reads provider config from Content Studio ``tts-providers.yaml`` (ALI_DEF by default)
and exposes POST /v1/audio/speech for Open Notebook / Esperanto.

Environment:
    CONTENT_STUDIO_TTS_CONFIG — path to tts-providers.yaml
    ALI_TTS_PROVIDER — provider key in yaml (default ALI_DEF)
    ALI_TTS_PROXY_PORT — listen port (default 8969)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import uvicorn
import yaml
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

_token_cache: dict[str, Any] = {"token": "", "expires_at": 0.0}
_token_lock = threading.Lock()
_tts_lock = threading.Lock()

# OpenAI voice aliases → Ali NLS voices that support 中文及中英文混合场景.
VOICE_MAP: dict[str, str] = {
    "alloy": "stella",  # 知性女声
    "echo": "zhida",  # 普通话男声
    "fable": "stanley",  # 沉稳男声
    "onyx": "zhixiang",  # 磁性男声
    "nova": "zhiqian",  # 资讯女声
    "shimmer": "rosa",  # 自然女声
    "ash": "zhida",
    "sage": "kenny",  # 沉稳男声
    "coral": "zhiru",  # 新闻女声
    "ballad": "aishuo",  # 自然男声
    "verse": "zhiyuan",  # 普通话女声
    "default": "stella",
}

# OpenAI TTS voice ids used by Open Notebook speaker profiles — map to Ali NLS voice.
_OPENAI_TTS_VOICES = frozenset(
    {
        "alloy",
        "ash",
        "ballad",
        "coral",
        "echo",
        "fable",
        "onyx",
        "nova",
        "sage",
        "shimmer",
        "verse",
        "default",
    }
)


class SpeechRequest(BaseModel):
    input: str = Field(..., min_length=1)
    model: str = "ali-tts"
    voice: str = "nova"
    response_format: str = "wav"
    speed: float | None = None


def _tts_config_path() -> Path:
    explicit = os.getenv("CONTENT_STUDIO_TTS_CONFIG", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    hermes_home = os.getenv("HERMES_HOME", str(Path.home() / ".hermes/profiles/content-studio"))
    return Path(hermes_home) / "config" / "tts-providers.yaml"


def _load_ali_config() -> dict[str, Any]:
    provider = os.getenv("ALI_TTS_PROVIDER", "ALI_DEF")
    path = _tts_config_path()
    if not path.is_file():
        msg = f"TTS config not found: {path}"
        raise HTTPException(status_code=503, detail=msg)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    providers = data.get("ttsEngConfig") or {}
    config = providers.get(provider)
    if not isinstance(config, dict):
        msg = f"Provider '{provider}' not found in {path}"
        raise HTTPException(status_code=503, detail=msg)
    return config


def _percent_encode(value: str) -> str:
    return urllib.parse.quote(value, safe="-_.~")


def _create_nls_token(config: dict[str, Any]) -> str:
    now = time.time()
    with _token_lock:
        if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
            return str(_token_cache["token"])

    access_key = str(config.get("access_key", "")).strip()
    access_key_secret = str(config.get("access_key_secret", "")).strip()
    if not access_key or not access_key_secret:
        raise HTTPException(status_code=503, detail="Ali TTS missing access_key credentials")

    params = {
        "AccessKeyId": access_key,
        "Action": "CreateToken",
        "Format": "JSON",
        "RegionId": "cn-shanghai",
        "SignatureMethod": "HMAC-SHA1",
        "SignatureNonce": str(uuid.uuid4()),
        "SignatureVersion": "1.0",
        "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "Version": "2019-02-28",
    }
    canonical = "&".join(
        f"{_percent_encode(key)}={_percent_encode(params[key])}" for key in sorted(params)
    )
    string_to_sign = f"GET&%2F&{_percent_encode(canonical)}"
    digest = hmac.new(
        (access_key_secret + "&").encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    params["Signature"] = base64.b64encode(digest).decode("ascii")
    query = urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(
            f"https://nls-meta.cn-shanghai.aliyuncs.com/?{query}",
            timeout=30,
        ) as resp:
            body = json.loads(resp.read())
    except OSError as exc:
        raise HTTPException(status_code=502, detail=f"Ali NLS token error: {exc}") from exc

    token_obj = body.get("Token") if isinstance(body.get("Token"), dict) else {}
    token = token_obj.get("Id") if isinstance(token_obj, dict) else ""
    expire = token_obj.get("ExpireTime") if isinstance(token_obj, dict) else 0
    if not token:
        raise HTTPException(status_code=502, detail=f"Ali NLS token response invalid: {body}")

    with _token_lock:
        _token_cache["token"] = token
        _token_cache["expires_at"] = float(expire) if expire else now + 3600
    return str(token)


def _resolve_voice(config: dict[str, Any], voice: str) -> str:
    default = str(config.get("voice_type") or config.get("uid") or VOICE_MAP["default"])
    voice = (voice or "nova").strip()
    key = voice.lower()
    if key in VOICE_MAP:
        return VOICE_MAP[key]
    if key in _OPENAI_TTS_VOICES:
        return default
    # Speaker display names (e.g. "Johny Bing") — not valid Ali voice ids.
    if " " in voice or not voice.isascii():
        return default
    return voice


def synthesize_ali(text: str, voice: str, speed: float | None) -> tuple[bytes, str]:
    # Aliyun NLS rejects concurrent stream TTS on the same appkey/token.
    with _tts_lock:
        return _synthesize_ali_unlocked(text, voice, speed)


def _synthesize_ali_unlocked(text: str, voice: str, speed: float | None) -> tuple[bytes, str]:
    config = _load_ali_config()
    appkey = str(config.get("appid", "")).strip()
    if not appkey:
        raise HTTPException(status_code=503, detail="Ali TTS missing appid in tts-providers.yaml")

    token = str(config.get("token") or config.get("nls_token") or "").strip()
    if not token:
        token = _create_nls_token(config)

    text_type = str(config.get("text_type", "plain"))
    request_text = text
    if text_type == "ssml" and "<speak" not in request_text:
        request_text = f"<speak>{html.escape(text)}</speak>"

    speed_ratio = speed if speed is not None else float(config.get("speed_ratio", 1.0) or 1.0)
    speech_rate = max(-500, min(500, int((speed_ratio - 1.0) * 500)))
    audio_format = str(config.get("encoding", "wav") or "wav")
    payload = {
        "appkey": appkey,
        "token": token,
        "text": request_text,
        "format": audio_format,
        "sample_rate": int(config.get("sample_rate", 16000)),
        "voice": _resolve_voice(config, voice),
        "volume": int(config.get("volume_ratio", 50)),
        "speech_rate": speech_rate,
    }
    url = str(
        config.get("url", "https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/tts")
    )
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            content = resp.read()
            content_type = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise HTTPException(
            status_code=502,
            detail=f"Ali TTS HTTP {exc.code}: {detail}",
        ) from exc
    except OSError as exc:
        raise HTTPException(status_code=502, detail=f"Ali TTS network error: {exc}") from exc

    if "application/json" in content_type:
        msg = content.decode("utf-8", errors="replace")[:300]
        raise HTTPException(status_code=502, detail=f"Ali TTS error: {msg}")

    media = "audio/wav" if audio_format == "wav" else "audio/mpeg"
    return content, media


app = FastAPI(title="Aliyun TTS Proxy", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "provider": "aliyun-nls"}


@app.get("/v1/models")
def list_models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [{"id": "ali-tts", "object": "model", "owned_by": "aliyun"}],
    }


@app.post("/v1/audio/speech")
def audio_speech(req: SpeechRequest) -> Response:
    audio, media = synthesize_ali(req.input, req.voice, req.speed)
    return Response(content=audio, media_type=media)


def main() -> None:
    port = int(os.getenv("ALI_TTS_PROXY_PORT", "8969"))
    host = os.getenv("ALI_TTS_PROXY_HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
