"""从事实记忆和近期对话归纳画像（提示词与解析；不调模型、不碰存储）。

输入是两样：该用户在该角色下的事实记忆（带本次渲染的短编号 F1、F2……），和最近的用户发言。
模型引用来源时只能写这些短编号；解析时逐个校验，**不在本次列表里的编号一律丢弃**，
所以模型编造不出一个能指到真实记忆的 id。

提示词里有 JSON 示例的大括号，不能用 ``str.format``；只做占位符替换。
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import datetime

from companion.persona.model import DYNAMIC, STATIC, ProfileDraft, ProfileEntry, clean_draft

MAX_FACTS = 40
MAX_UTTERANCES = 12
MAX_UTTERANCE_CHARS = 200
MAX_DRAFTS = 12

EXTRACTION_PROMPT = """\
你在为一个陪伴型 AI 角色整理「它对这位用户的了解」。根据下面的【事实记忆】和【近期发言】，
更新对这位用户的画像。只输出 JSON，不要解释。

规则：
1. 每条画像是 {"topic": 话题, "memo": 一两句话, "section": "static" 或 "dynamic",
   "inference": true 或 false, "confidence": 0 到 1, "sources": ["F1", ...]}。
2. static = 长期稳定的（称呼、职业、家人、禁忌、重要的人、长期爱好）；
   dynamic = 近期在做的事（最近的项目、近况），会过期。
3. inference = false 只用于用户明确说过的内容；你归纳、猜测出来的（性格、心情、关系好坏）必须写 true，
   且 confidence 不要超过 0.6。
4. sources 只能写【事实记忆】里出现的编号；纯来自近期发言、没有对应事实的，sources 写 []。
5. topic 用简短名词（不超过 12 个字）。同一话题只写一条。已有画像里的话题，只有信息真的变了才重写。
6. 不要写：身份证号、银行卡、密码、住址、病情、性取向、宗教、政治倾向，哪怕用户说过。
7. 不要把角色（AI）说的话当成用户的情况。没有值得更新的，输出 {"entries": []}。

输出格式：{"entries": [ ... ]}

【已有画像】
{{existing}}

【事实记忆】
{{facts}}

【近期发言】
{{utterances}}
"""


def render_prompt(*, existing: Sequence[ProfileEntry], fact_lines: Sequence[tuple[str, str]],
                  utterances: Sequence[str]) -> str:
    """``fact_lines``：[(短编号, 事实文本)]，编号由调用方按本次列表顺序生成。"""
    current = [e for e in existing if e.current]
    existing_text = "\n".join(f"- {e.topic}：{e.memo}" + ("（推测）" if e.is_inference else "")
                              for e in current) or "（暂无）"
    facts_text = "\n".join(f"{ref}. {text}" for ref, text in fact_lines[:MAX_FACTS]) or "（暂无）"
    said = [u.strip()[:MAX_UTTERANCE_CHARS] for u in utterances if u.strip()][-MAX_UTTERANCES:]
    utter_text = "\n".join(f"- {u}" for u in said) or "（暂无）"
    return (EXTRACTION_PROMPT.replace("{{existing}}", existing_text)
            .replace("{{facts}}", facts_text).replace("{{utterances}}", utter_text))


def _json_object(raw: str) -> dict | None:
    """模型常把 JSON 包在 ```json 里或前后加一句话：取第一个完整的对象。"""
    if not raw:
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start:i + 1])
                except ValueError:
                    return None
                return obj if isinstance(obj, dict) else None
    return None


def parse_drafts(raw: str, *, fact_ids: dict[str, str], now: datetime | None = None) -> list[ProfileDraft]:
    """``fact_ids``：短编号 → 真实事实 id。解析失败或没有合格条目返回空列表，不抛错。"""
    data = _json_object(raw)
    entries = data.get("entries") if data else None
    if not isinstance(entries, list):
        return []
    out: list[ProfileDraft] = []
    for item in entries[:MAX_DRAFTS]:
        if not isinstance(item, dict):
            continue
        inference = bool(item.get("inference", False))
        try:
            confidence = float(item.get("confidence", 0.8))
        except (TypeError, ValueError):
            confidence = 0.8
        if inference:
            confidence = min(confidence, 0.6)      # 推断的置信度封顶，不管模型怎么写
        sources = item.get("sources")
        refs = [str(s).strip() for s in sources] if isinstance(sources, list) else []
        real = tuple(fact_ids[r] for r in refs if r in fact_ids)   # 不在本次列表里的编号丢弃
        draft = clean_draft(ProfileDraft(
            topic=str(item.get("topic") or ""), memo=str(item.get("memo") or ""),
            section=DYNAMIC if item.get("section") == DYNAMIC else STATIC,
            is_inference=inference, confidence=confidence, source_fact_ids=real, mentioned_at=now))
        if draft is not None:
            out.append(draft)
    return out
