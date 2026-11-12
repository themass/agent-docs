"""火山引擎语音的 LiveKit 适配：复用社区插件 livekit-plugins-volcengine，只改鉴权。

为什么要改：插件的 STT/TTS 把鉴权头写死成旧版控制台格式（``X-Api-App-Key`` +
``X-Api-Access-Key``）。我们的凭据是新版控制台签发的，服务端只认 ``X-Api-Key``
（实测：旧版头走同一个地址返回 401）。插件本身不暴露改 header 的入口，所以这里
**只覆盖 ``get_ws_header``**，流式分包、重连、响应解析全部沿用插件。

这样做的边界很明确：
- 插件升级后如果改了内部结构，这里的测试会失败，而不是线上悄悄不说话。
- 不做的事：不改协议、不改音频格式、不改分包策略。
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from livekit.plugins.volcengine.stt import STTOptions
from livekit.plugins.volcengine.stt import STT as _PluginSTT
from livekit.plugins.volcengine.tts import TTS as _PluginTTS
from livekit.plugins.volcengine.tts import _TTSOptions as _PluginTTSOptions


class NewConsoleSTTOptions(STTOptions):
    """新版控制台鉴权：``X-Api-Key`` + ``X-Api-Resource-Id``。

    资源 id 必须是 2.0 的那两个（``volc.seedasr.sauc.*``）；用 1.0 的
    （``volc.bigasr.sauc.*``）会 403，实测过。
    """

    api_key: str = ""
    resource_id: str | None = None

    def get_ws_header(self, reqid: str | None = None) -> dict[str, str]:
        from livekit.plugins.volcengine import utils

        if reqid is None:
            reqid = utils.shortuuid()
        key = self.api_key or os.environ.get("VOLC_ASR_API_KEY", "")
        if not key:
            raise ValueError("VOLC_ASR_API_KEY is not set")
        header = {
            "X-Api-Key": key,
            "X-Api-Resource-Id": self.resource_id or "volc.seedasr.sauc.duration",
            "X-Api-Connect-Id": reqid,
            "X-Api-Request-Id": reqid,
        }
        return header


class NewConsoleSTT(_PluginSTT):
    """火山流式识别（新版控制台凭据）。

    构造参数与插件一致，只是把 ``access_token`` 换成 ``api_key``；其余能力
    （流式、中间结果、静音判定）都用插件的。
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        resource_id: str | None = None,
        base_url: str = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel",
        model_name: str = "bigmodel",
        enable_itn: bool = False,
        enable_punc: bool = True,
        enable_ddc: bool = False,
        vad_segment_duration: int = 3000,
        end_window_size: int = 500,
        force_to_speech_time: int = 1000,
        http_session=None,
        interim_results: bool = True,
    ) -> None:
        key = api_key or os.environ.get("VOLC_ASR_API_KEY", "")
        # 父类要求带 app_id / access_token，这里给占位值：真正的鉴权在
        # NewConsoleSTTOptions.get_ws_header 里，父类字段不会进入请求。
        super().__init__(
            app_id="new-console",
            access_token=key,
            base_url=base_url,
            model_name=model_name,
            enable_itn=enable_itn,
            enable_punc=enable_punc,
            enable_ddc=enable_ddc,
            vad_segment_duration=vad_segment_duration,
            end_window_size=end_window_size,
            force_to_speech_time=force_to_speech_time,
            http_session=http_session,
            interim_results=interim_results,
        )
        # 换成我们的选项类型：其余字段从父类构造结果里抄过来，避免漏掉插件的默认值。
        ours = NewConsoleSTTOptions(**{
            name: getattr(self._opts, name)
            for name in ("source_type", "resource_id", "base_url", "format", "sample_rate", "bits",
                         "num_channels", "language", "model_name", "codec", "enable_itn", "enable_punc",
                         "enable_ddc", "show_utterance", "result_type", "vad_segment_duration",
                         "end_window_size", "force_to_speech_time")
        })
        ours.api_key = key
        ours.resource_id = resource_id
        self._opts = ours


def volcengine_available(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return bool((source.get("VOLC_ASR_API_KEY") or "").strip())


class NewConsoleTTSOptions(_PluginTTSOptions):
    """新版控制台鉴权：``X-Api-Key``。其余（URL、请求体、编码）保持插件的实现。"""

    api_key: str = ""

    def get_http_header(self, reqid: str | None = None) -> dict[str, str]:
        key = self.api_key or os.environ.get("VOLC_TTS_API_KEY", "")
        if not key:
            raise ValueError("VOLC_TTS_API_KEY is not set")
        resource_id = self.resource_id or os.environ.get("VOLC_TTS_RESOURCE_ID", "seed-tts-2.0")
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": key,
            "X-Api-Resource-Id": resource_id,
            "X-Api-App-Id": self.app_id,
            "X-Api-App-Key": self.app_id,
        }
        if reqid is not None:
            headers["X-Api-Request-Id"] = reqid
        return headers


class NewConsoleTTS(_PluginTTS):
    """火山流式（HTTP 单向流）合成，新版控制台凭据。

    协议、请求体、音频编码都沿用插件；只把鉴权换成 ``X-Api-Key``。
    """

    def __init__(self, *, api_key: str | None = None, app_id: str | None = None,
                 resource_id: str | None = None,
                 voice: str = "zh_female_xiaohe_uranus_bigtts", speed: float = 1.0,
                 volume: float = 1.0, pitch: float = 1.0, sample_rate: int = 16000,
                 http_session=None) -> None:
        key = api_key or os.environ.get("VOLC_TTS_API_KEY", "")
        app = app_id or os.environ.get("VOLC_TTS_APP_ID", "")
        super().__init__(app_id=app or "new-console", access_token=key or None,
                         resource_id=resource_id, voice=voice, speed=speed, volume=volume,
                         pitch=pitch, sample_rate=sample_rate, http_session=http_session)
        ours = NewConsoleTTSOptions(**self._opts.model_dump())
        ours.api_key = key
        ours.resource_id = resource_id
        self._opts = ours
