"""Resume output tracks: zh / en / bilingual. Product UI stays Chinese."""

from __future__ import annotations

import re

TRACK_ZH = "zh-CN"
TRACK_EN = "en-US"
TRACK_BILINGUAL = "zh-en"

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def is_english_locale(locale: str) -> bool:
    return normalize_track(locale) == TRACK_EN


def is_bilingual_track(locale: str) -> bool:
    return normalize_track(locale) == TRACK_BILINGUAL


def needs_i18n_prepare(locale: str | None) -> bool:
    """True when localize/prepare_tracks should fill the other language pack.

    Preview and elevate must not block on this: English copy is written from the
    source profile (plus overlay if already translated).
    """
    track = normalize_track(locale)
    return track in {TRACK_EN, TRACK_BILINGUAL}


def normalize_locale(locale: str | None) -> str:
    """Back-compat alias: monolingual locales only (zh-CN | en-US)."""
    track = normalize_track(locale)
    return TRACK_EN if track == TRACK_EN else TRACK_ZH


def normalize_track(locale: str | None) -> str:
    raw = (locale or TRACK_ZH).strip().lower().replace("_", "-")
    if raw in {"zh-en", "bilingual", "both", "zh-en-us"}:
        return TRACK_BILINGUAL
    if raw.startswith("en"):
        return TRACK_EN
    return TRACK_ZH


def template_id_for_locale(locale: str) -> str:
    track = normalize_track(locale)
    if track == TRACK_BILINGUAL:
        return "zh-en-bilingual"
    if track == TRACK_EN:
        return "en-two-page"
    return "zh-one-page"


def other_monolingual(source_locale: str) -> str:
    return TRACK_EN if normalize_track(source_locale) == TRACK_ZH else TRACK_ZH


def detect_source_locale(text: str) -> str:
    """CJK ratio over letters + CJK; ≥ 0.15 → Chinese source."""
    cleaned = "".join(ch for ch in text if ch.isalpha() or _CJK_RE.match(ch))
    if not cleaned:
        return TRACK_ZH
    cjk = len(_CJK_RE.findall(cleaned))
    if cjk / len(cleaned) >= 0.15:
        return TRACK_ZH
    return TRACK_EN
