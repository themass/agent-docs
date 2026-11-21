"""维护用户档案的提示词与解析（不调模型、不碰存储）。

输入三样：现有档案（可能是空）、该用户在该角色下的事实记忆（带本次渲染的短编号 F1、F2……）、
从上次维护以来累积的近期用户发言。输出契约是 JSON：``{"changed": true, "markdown": …}``
或 ``{"changed": false}``。

提示词写法遵循几条本项目抽取类任务共用的纪律（见 persona/extraction.py）：
- 提示词里有 JSON 示例的大括号，**不能用 ``str.format``**，只做 ``{{placeholder}}`` 占位符替换；
- 规则编号列出、可逐条核对；引用来源只能写本次给定的短编号，解析时逐个校验，
  不在本次列表里的编号丢弃——模型编造不出一个能指到真实记忆的 id；
- 解析是宽容的：模型常把 JSON 包在 ```json 里或前后加一句解释，取第一个完整对象；
  不合格的输出按「本批没有更新」处理（保留旧档案），而不是让任务失败。
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

MAX_FACTS = 40
MAX_UTTERANCES = 12
MAX_UTTERANCE_CHARS = 200
MAX_DOC_CHARS = 1600   # 和 model.MAX_DOC_CHARS 一致：写库端同一把尺

# 敏感信息即使出现在材料里也不进档案（和画像/记忆的禁止清单同一精神）
FORBIDDEN_WORDS = ("身份证", "银行卡", "密码", "验证码", "住址", "病历", "性取向", "宗教", "政治倾向")

DOC_TEMPLATE = """## 基本情况
## 近况
## 相处方式"""

MAINTAIN_PROMPT = """\
你在为陪伴型 AI 角色「{{role}}」维护「她眼里的这位用户」档案。档案是一篇中文 Markdown，
会整篇放进角色的系统提示词，是她长期了解用户的底稿；它会在多批对话之间被反复修订，
所以稳定、克制、可修订比面面俱到重要。

只输出一个 JSON 对象，不要输出解释：
- 档案有值得更新的改动：{"changed": true, "markdown": "……完整档案……"}
- 本批没有值得改的（没有新事实、没有真变化）：{"changed": false}

规则：
1. markdown 是**修订后的完整档案**，不是补丁或差异。章节结构沿用下面【现有档案】的章节；
   没有现有档案时按这个骨架来（{{template}}），可随内容增减章节，但章节名要短、稳定。
2. 每一条内容都必须有依据：来自【事实记忆】（引用其编号）或【近期发言】里用户亲口说的话。
   用户没说、也无法从已给材料推出的，不写。
3. 区分事实与推断：用户明说的可以直接写；你归纳、猜测的（性格、心情、关系走向）只能写试探的
   口气，并在句末标「（推测）」。不要把推测写成确定事实。
4. 不要把角色（AI）说的话当成用户的情况；用户转述别人的话时，写的是用户的话，不是那个人的事实。
5. 【近况】只写**现在还在发生**的事：新近况替换旧近况，不累积过期条目。
6. 不写这些，哪怕用户说过：身份证号、银行卡、密码、验证码、住址、病情、性取向、宗教、政治倾向。
7. 档案总长不超过 1400 字。同一信息换个说法不算更新；没新内容就 changed=false。
   来源编号（F1、F2……）只是给你引用用的：档案正文里**不要出现**这些编号。
8. 用户提到过的称呼、职业、家人、重要的人、禁忌这类长期信息写进「基本情况」，宁少勿滥。

【现有档案】
{{doc}}

【事实记忆】
{{facts}}

【近期发言】（从上次维护以来，用户说的原话）
{{utterances}}
"""


def render_prompt(*, role_name: str, doc: str, fact_lines: Sequence[tuple[str, str]],
                  utterances: Sequence[str]) -> str:
    """``fact_lines``：[(短编号, 事实文本)]，编号由调用方按本次列表顺序生成。"""
    doc_text = doc.strip() or "（还没有档案，这是第一份）"
    facts_text = "\n".join(f"{ref}. {text}" for ref, text in fact_lines[:MAX_FACTS]) or "（暂无）"
    said = [u.strip()[:MAX_UTTERANCE_CHARS] for u in utterances if u.strip()][-MAX_UTTERANCES:]
    utter_text = "\n".join(f"- {u}" for u in said) or "（暂无）"
    return (MAINTAIN_PROMPT.replace("{{role}}", role_name)
            .replace("{{template}}", DOC_TEMPLATE)
            .replace("{{doc}}", doc_text)
            .replace("{{facts}}", facts_text)
            .replace("{{utterances}}", utter_text))


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


def _clean_markdown(raw: str) -> str:
    """去掉整篇档案外的 ```markdown 围栏与首尾空白；章节标题行保留。"""
    text = raw.strip()
    text = re.sub(r"^```(?:markdown|md)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_doc(raw: str) -> str | None:
    """解析维护结果。返回 None = 本批不更新（无变化、输出不合格、超长、含敏感词）。

    不合格按「没有更新」处理而不是抛错：档案是旁路数据，一次坏输出最多让这一批
    白跑（下一批还会再来），不该让任务重试队列被毒化。
    """
    data = _json_object(raw)
    if data is None or data.get("changed") is not True:
        return None
    md = data.get("markdown")
    if not isinstance(md, str):
        return None
    md = _clean_markdown(md)
    if not md or len(md) > MAX_DOC_CHARS:
        return None
    if any(word in md for word in FORBIDDEN_WORDS):
        return None
    # 档案里出现短编号（F1、F2……）说明模型把来源编号抄进了正文：不合格（宁缺毋滥）
    if re.search(r"F\d{1,2}", md):
        return None
    return md
