"""语音网关：把 VoiceRef 路由到已注册的供应商，并兜住供应商故障。

三件事在这里，不在适配器里：

1. **按句断句**。agent 吐的是任意切分的文本片段，TTS 要整句才自然；断句策略是
   供应商无关的，所以放在网关（设计文档第 13 节）。
2. **短句缓存**。问候语这类固定短句每回合都要合成一次，缓存能省掉首包延迟。
   只缓存短句：长句千变万化，缓存命中率低还占内存。
3. **故障切换**。连续失败 N 次后切到备用供应商，每次切换都记日志。

不做的事：不转码、不改采样率、不重放已经吐出去的音频。半句音频已经发给客户端
再换供应商会混音色，比报错更糟，所以只在「一个音频块都还没吐」时才重试。
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from companion.text.splitter import SentenceSplitter
from companion.voice.port import AudioChunk, Transcript, UnknownVoiceProvider, VoiceProvider, VoiceProviderError, VoiceRef, VoiceUnavailable

log = logging.getLogger("companion.voice")

DEFAULT_FAILURE_THRESHOLD = 2
DEFAULT_MAX_PHRASE_CHARS = 32
DEFAULT_CACHE_CAPACITY = 64


@dataclass(frozen=True)
class ProviderSwitch:
    """一次故障切换的审计记录。"""

    provider_from: str
    provider_to: str
    direction: str
    failures: int
    reason: str


@dataclass(frozen=True)
class FailureOutcome:
    """一次失败之后网关该怎么走。"""

    retry_on: str | None
    switched: bool


def cache_key(voice_ref: VoiceRef, provider_name: str, text: str) -> tuple[str, str, str]:
    """缓存键。

    带上实际出声的供应商：切到备用供应商后，同一个 ``voice_id`` 未必是同一个
    音色，把两家供应商的音频混用一个键会让耳朵听出「不是我」。
    """
    return (f"{voice_ref.provider}/{voice_ref.voice_id}@{voice_ref.stable_key()}", provider_name, text)


class VoiceGateway:
    """按 VoiceRef 路由，带短句缓存与备用供应商。

    ``primary`` / ``secondary`` 是供应商名（对应注册表的 key），不是 VoiceRef 里的
    provider —— 前者是「这次用谁出力」，后者是「角色要什么声音」。默认都取
    ``voice_ref.provider``，即不配置就没有备用。
    """

    def __init__(
        self,
        providers: Mapping[str, VoiceProvider],
        *,
        primary: str | None = None,
        secondary: str | None = None,
        asr_provider: str | None = None,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        max_phrase_chars: int = DEFAULT_MAX_PHRASE_CHARS,
        cache_capacity: int = DEFAULT_CACHE_CAPACITY,
    ) -> None:
        if not providers:
            raise ValueError("VoiceGateway 至少需要一个供应商")
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be positive")
        if max_phrase_chars < 1:
            raise ValueError("max_phrase_chars must be positive")
        self._providers: dict[str, VoiceProvider] = dict(providers)
        self._primary = primary
        self._secondary = secondary
        self._asr_provider = asr_provider
        self._failure_threshold = failure_threshold
        self._max_phrase_chars = max_phrase_chars
        self._cache_capacity = cache_capacity

        self._cache: dict[tuple[str, str, str], tuple[AudioChunk, ...]] = {}
        # 每个方向记住「已经切到谁了」。按方向分开：TTS 出事不代表 ASR 也出事。
        self._active: dict[str, str] = {}
        self._consecutive: dict[str, int] = {}
        self.switches: list[ProviderSwitch] = []
        self.cache_hits = 0

    # ---- 查询 ----

    @property
    def registered(self) -> list[str]:
        return sorted(self._providers)

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    def active_provider(self, direction: str = "tts") -> str | None:
        return self._active.get(direction)

    def reset_fallback(self) -> None:
        """运维手段：手动恢复主供应商。

        不自动切回：供应商刚恢复就切回去，抖动时会在两家之间来回跳，每次跳都要
        重建连接、换音色，体验比稳定用备用更差。
        """
        self._active.clear()
        self._consecutive.clear()

    # ---- TTS ----

    def tts(self, text_stream: AsyncIterator[str], voice_ref: VoiceRef) -> AsyncIterator[AudioChunk]:
        """校验同步做，这样未知供应商在调用点就炸，而不是等在第一次迭代。"""
        self._resolve(voice_ref.provider)
        return self._tts(text_stream, voice_ref)

    async def _tts(
        self, text_stream: AsyncIterator[str], voice_ref: VoiceRef
    ) -> AsyncIterator[AudioChunk]:
        splitter = SentenceSplitter()
        async for text in text_stream:
            for sentence in splitter.feed(text):
                async for chunk in self._one_sentence(sentence, voice_ref):
                    yield chunk
        for sentence in splitter.flush():
            async for chunk in self._one_sentence(sentence, voice_ref):
                yield chunk

    async def _one_sentence(self, sentence: str, voice_ref: VoiceRef) -> AsyncIterator[AudioChunk]:
        text = sentence.strip()
        if not text:
            return

        cached = self._lookup(voice_ref, text)
        if cached is not None:
            self.cache_hits += 1
            for chunk in cached:
                yield chunk
            return

        provider_name = self._current_provider("tts", voice_ref.provider)
        emitted = False
        collected: list[AudioChunk] = []
        while True:
            try:
                async for chunk in self._providers[provider_name].tts(_one_text(text), voice_ref):
                    emitted = True
                    if self._cacheable(text):
                        collected.append(chunk)
                    yield chunk
                self._note_success(provider_name, "tts")
                break
            except Exception as exc:  # noqa: BLE001 — 供应商实现不可控，网关负责收口
                # CancelledError 是 BaseException，不会落到这里：取消必须能穿透。
                outcome = self._note_failure(provider_name, "tts", exc)
                if emitted or outcome.retry_on is None or provider_name == outcome.retry_on:
                    raise _as_provider_error(exc, provider_name, "tts") from exc
                # 这一句还没吐字节，换一家重说一遍是听不出来的；已经吐了的绝不重来。
                log.info(
                    "voice retrying sentence on %s after %s failed", outcome.retry_on, provider_name
                )
                provider_name = outcome.retry_on
                emitted = False
                collected.clear()

        if collected and self._cacheable(text):
            self._store(
                cache_key(voice_ref, provider_name, text),
                tuple(collected),
            )

    async def precache(self, phrases: Iterable[str], voice_ref: VoiceRef) -> int:
        """预热固定短句（问候语）。返回写入缓存条数。

        走同一个 ``_one_sentence`` 路径，故障切换与缓存键规则就不会和实时路径分叉。
        """
        self._resolve(voice_ref.provider)
        written = 0
        for phrase in phrases:
            splitter = SentenceSplitter(max_chars=self._max_phrase_chars)
            for sentence in splitter.feed(phrase) + splitter.flush():
                text = sentence.strip()
                if not text or not self._cacheable(text):
                    continue
                key = cache_key(
                    voice_ref, self._current_provider("tts", voice_ref.provider), text
                )
                if key in self._cache:
                    continue
                if [chunk async for chunk in self._one_sentence(text, voice_ref)]:
                    written += 1
        return written

    # ---- ASR ----

    def asr(self, audio_stream: AsyncIterator[bytes], *, provider: str | None = None) -> AsyncIterator[Transcript]:
        name = provider or self._asr_provider or self._default_asr()
        self._resolve(name)
        return self._asr(audio_stream, name)

    async def _asr(
        self, audio_stream: AsyncIterator[bytes], provider_name: str
    ) -> AsyncIterator[Transcript]:
        """不重试在流的 ASR。

        音频流是一次性的：供应商已经读掉的帧没法重放，换一家接着读等于让它从句子
        中间开始识别。失败只记数、切下一次的供应商，本次直接报错。
        """
        name = self._current_provider("asr", provider_name)
        try:
            async for transcript in self._providers[name].asr(audio_stream):
                yield transcript
            self._note_success(name, "asr")
        except Exception as exc:  # noqa: BLE001
            # 记失败即可：切换只对下一次生效，return 值（retry_on）在 ASR 上不用。
            self._note_failure(name, "asr", exc)
            raise _as_provider_error(exc, name, "asr") from exc

    def _default_asr(self) -> str:
        for candidate in (self._primary, self._active.get("asr")):
            if candidate:
                return candidate
        if len(self._providers) == 1:
            return next(iter(self._providers))
        raise UnknownVoiceProvider(
            "无法确定 ASR 供应商：请给 VoiceGateway(asr_provider=...) 或 asr(..., provider=...)，"
            f"已注册：{', '.join(self.registered)}"
        )

    # ---- 内部 ----

    def _resolve(self, name: str) -> VoiceProvider:
        try:
            return self._providers[name]
        except KeyError:
            raise UnknownVoiceProvider(
                f"未注册的语音供应商 {name!r}；已注册：{', '.join(self.registered)}"
            ) from None

    def _current_provider(self, direction: str, requested: str) -> str:
        return self._active.get(direction) or requested

    def _fallback_for(self, direction: str, requested: str) -> str | None:
        """备用供应商。

        TTS 只用显式配置的 ``secondary``：悄悄换到另一个 TTS 供应商就会换音色，
        这是产品决定，不能由故障隐式决定。ASR 没有音色问题，可以回落到 ``primary``。
        """
        for candidate in (
            self._secondary,
            self._primary if direction == "asr" else None,
        ):
            if candidate and candidate != requested and candidate in self._providers:
                return candidate
        return None

    def _note_success(self, provider_name: str, direction: str) -> None:
        self._consecutive.pop(f"{direction}:{provider_name}", None)

    def _note_failure(self, provider_name: str, direction: str, exc: Exception) -> FailureOutcome:
        """记一次失败，返回这次该不该换人重来。

        两件事分开：**这一句**能不能换人重说（只要有备用就行），和**以后**是否固定
        走备用（连续失败到阈值）。混在一起的话，阈值配成 2 就要让用户听两次报错。
        """
        key = f"{direction}:{provider_name}"
        count = self._consecutive.get(key, 0) + 1
        self._consecutive[key] = count
        fallback = self._fallback_for(direction, provider_name)
        retry_on = fallback if fallback != provider_name else None

        if count < self._failure_threshold:
            log.warning(
                "voice provider %s failed (%s, %d/%d): %s",
                provider_name, direction, count, self._failure_threshold, exc,
            )
            return FailureOutcome(retry_on=retry_on, switched=False)

        if fallback is None:
            log.error(
                "voice provider %s failed %d times (%s) and no fallback is configured: %s",
                provider_name, count, direction, exc,
            )
            return FailureOutcome(retry_on=None, switched=False)

        if self._active.get(direction) == fallback:
            # 已经切过去了还在这里报失败，说明是那一句自己的问题，不重复记账。
            self._consecutive.pop(key, None)
            return FailureOutcome(retry_on=None, switched=False)

        self._active[direction] = fallback
        self._consecutive.pop(key, None)
        record = ProviderSwitch(
            provider_from=provider_name,
            provider_to=fallback,
            direction=direction,
            failures=count,
            reason=f"{type(exc).__name__}: {exc}",
        )
        self.switches.append(record)
        log.error(
            "voice provider switched %s -> %s (%s) after %d consecutive failures: %s",
            provider_name, fallback, direction, count, exc,
        )
        return FailureOutcome(retry_on=fallback, switched=True)

    def _cacheable(self, text: str) -> bool:
        return 0 < len(text) <= self._max_phrase_chars

    def _lookup(self, voice_ref: VoiceRef, text: str) -> tuple[AudioChunk, ...] | None:
        if not self._cacheable(text):
            return None
        provider_name = self._current_provider("tts", voice_ref.provider)
        return self._cache.get(cache_key(voice_ref, provider_name, text))

    def _store(self, key: tuple[str, str, str], chunks: tuple[AudioChunk, ...]) -> None:
        if key not in self._cache and len(self._cache) >= self._cache_capacity:
            # 简单 FIFO：短句缓存命中集中在问候语上，LRU 的额外记账不值当。
            oldest = next(iter(self._cache))
            self._cache.pop(oldest, None)
        self._cache[key] = chunks


def _as_provider_error(exc: Exception, provider_name: str, direction: str) -> VoiceProviderError:
    if isinstance(exc, VoiceProviderError):
        return exc
    return VoiceProviderError(
        f"{provider_name} {direction} failed: {exc}", provider=provider_name, direction=direction
    )


async def _one_text(text: str) -> AsyncIterator[str]:
    yield text
