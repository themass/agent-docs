"""Coach feedback: bilingual rule-based default, optional LLM."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alignment import AlignmentScore


@dataclass(frozen=True)
class CoachMessage:
    """Bilingual coach output; ja/es reserved for future UI locales."""

    zh: str
    en: str

    def get(self, locale: str) -> str:
        """Pick primary line for locale prefix."""
        if locale.startswith("ja"):
            return self.en  # ponytail: ja templates in v2
        if locale.startswith("es"):
            return self.en
        if locale.startswith("en"):
            return self.en
        return self.zh

    def to_dict(self) -> dict[str, str]:
        return {"zh": self.zh, "en": self.en}


def _rule_based_coach(reference: str, score: AlignmentScore) -> CoachMessage:
    """Generate bilingual feedback without LLM."""
    problems = [i for i in score.issues if i.type in {"missing", "wrong", "extra"}]
    if not problems and score.overall >= 0.9:
        return CoachMessage(
            zh="很棒，这句很顺！可以下一句了。",
            en="Great job — sounds natural. Next line!",
        )

    if not problems and score.overall >= 0.75:
        return CoachMessage(
            zh="不错，再清晰一点会更自然，要不再练一遍？",
            en="Good — a bit more clarity would help. Once more?",
        )

    top = problems[0]
    if top.type == "missing":
        return CoachMessage(
            zh=f"差一点点，「{top.word}」没听到，轻轻补上再试一次。",
            en=f"Almost — don't skip «{top.word}». Try again.",
        )
    if top.type == "wrong":
        return CoachMessage(
            zh=f"注意「{top.expected}」，现在更像「{top.spoken}」，放慢再读。",
            en=f"Watch «{top.expected}» — it sounded like «{top.spoken}».",
        )
    if top.type == "extra":
        return CoachMessage(
            zh=f"多说了「{top.word}」，对照原句收一下。",
            en=f"You added «{top.word}» — trim it to match the line.",
        )
    return CoachMessage(
        zh="再听一遍示范，跟着节奏读。",
        en="Listen once more, then shadow the line.",
    )


def _llm_coach(
    reference: str,
    transcript: str,
    score: AlignmentScore,
) -> CoachMessage | None:
    """Call OpenAI-compatible API (DashScope / Doubao); return None on failure."""
    api_key = (
        os.environ.get("SAYAGAIN_LLM_API_KEY")
        or os.environ.get("DASHSCOPE_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if not api_key:
        return None

    base = os.environ.get("SAYAGAIN_LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    base = base.rstrip("/")
    model = os.environ.get("SAYAGAIN_LLM_MODEL", "qwen-plus")

    issues_payload = [
        {"type": i.type, "word": i.word, "expected": i.expected, "spoken": i.spoken}
        for i in score.issues
        if i.type != "ok"
    ]

    system = (
        "你是英语口语教练。只能根据对齐结果提建议，不要编造错误。"
        "返回 JSON：{\"zh\":\"...\",\"en\":\"...\"}，各最多两句话，口语化，无 markdown。"
    )
    user = json.dumps(
        {
            "reference": reference,
            "user_said": transcript,
            "scores": {
                "overall": score.overall,
                "completeness": score.completeness,
                "accuracy": score.accuracy,
            },
            "issues": issues_payload,
        },
        ensure_ascii=False,
    )

    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": 180,
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        raw = data["choices"][0]["message"]["content"].strip()
        parsed = json.loads(raw)
        zh = str(parsed.get("zh", "")).strip()
        en = str(parsed.get("en", "")).strip()
        if zh and en:
            return CoachMessage(zh=zh, en=en)
        return None
    except (urllib.error.URLError, KeyError, json.JSONDecodeError, TimeoutError, TypeError):
        return None


def coach(
    reference: str,
    transcript: str,
    score: AlignmentScore,
    *,
    use_llm: bool = True,
) -> CoachMessage:
    """Produce bilingual coach message for one shadowing attempt."""
    if use_llm:
        llm_msg = _llm_coach(reference, transcript, score)
        if llm_msg:
            return llm_msg
    return _rule_based_coach(reference, score)
