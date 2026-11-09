"""回合后记忆提取。

一次回合结束后异步跑：把「用户说了什么 + 角色回了什么」压成候选记忆，过一遍
禁止清单，再写进 ``MemoryPort``。

两个刻意的边界：

- **不自己调模型**。模型调用是构造时注入的 ``async (prompt) -> str``，上层用
  ``memory_extract`` 场景接 LiteLLM；这里只负责提示词、解析与过滤。
- **只从用户的话里提取**。角色（尤其 DeerFlow 生成的故事）说出来的东西是内容，
  不是用户事实；助手回复只作为消歧用的上下文。

提取永远不抛给上层：异步任务炸掉不该影响通话，失败只记日志、本轮不写记忆。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from companion.ports.memory import MemoryItem, MemoryKind, coerce_kind

logger = logging.getLogger(__name__)

LLMCall = Callable[[str], Awaitable[str]]

# 单条记忆的长度上限。太短是语气词，太长是把整段对话抄进来。
MIN_CONTENT_CHARS = 2
MAX_CONTENT_CHARS = 200
# 一次提取最多收几条，防模型刷屏。
MAX_ITEMS_PER_TURN = 8

KIND_SPEC = "FACT(稳定事实) | PREFERENCE(偏好) | EVENT(发生过的重要事件)"

SYSTEM_PROMPT = """你是记忆抽取器。从「用户」说的话里挑出值得长期记住的信息。

只输出 JSON 数组，不要解释、不要 markdown 代码块。每项是一个对象，
字段 content（一句话，以用户为主语的陈述）与 kind。

kind 取值：<<KINDS>>

规则：
- 只看用户说的话；助手回复仅用于消歧，它的内容不算用户信息。
- 只记稳定、以后还有用的：身份、长期偏好、重要经历与计划。
- 不记：一次性的寒暄、情绪、提问、助手告诉用户的东西。
- 没有值得记的就输出 []。
- 每项只表达一个事实，content 用简体中文，第二人称视角改写成「用户……」。
- 禁止记录（命中任一条直接丢弃）：<<FORBIDDEN>>
"""

# 禁止清单：设计文档第 4.2 节，v2 起不变。命中即整条丢弃，不做打码。
# 关键词是启发式：宁可漏掉一条健康信息，也不要让它落库。
FORBIDDEN_CATEGORIES: tuple[str, ...] = (
    "身份证号、护照号、社保号等证件号码",
    "银行卡号、信用卡号、支付账号",
    "密码、PIN、验证码、密钥、令牌",
    "精确住址（门牌号、楼栋、房间号）",
    "医疗诊断、病历、处方、用药与检查结果",
)

# 关键词按类别分组，便于以后单独放宽某一类。全部大小写不敏感。
_FORBIDDEN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "credential": (
        "身份证", "护照号", "社保号", "证件号", "银行卡", "信用卡", "卡号",
        "密码", "口令", "验证码", "pin码", "cvv", "password", "passwd",
        "passcode", "secret key", "api key", "access token", "私钥",
    ),
    "address": (
        "家庭住址", "详细地址", "精确地址", "收货地址", "门牌", "小区",
        "栋", "单元", "室号", "street address", "home address",
    ),
    "medical": (
        "诊断", "确诊", "病历", "处方", "用药", "服药", "服用", "化疗", "手术",
        "化验单", "检查结果", "病危", "抑郁症", "焦虑症", "精神分裂",
        "癌", "肿瘤", "hiv", "diagnosis", "prescription",
    ),
}

# 证件号/卡号/长数字串。18 位身份证允许末位 X。
_FORBIDDEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?<!\d)\d{15}(?!\d)"),           # 老式身份证
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),     # 18 位身份证
    re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)"),  # 卡号，允许分隔符
)

# 门牌式地址：数字 + 号/栋/室/楼/单元。宽一点，地址宁可错杀。
# 排除「第3号」这类序号，它不以门牌出现。
_ADDRESS_PATTERN = re.compile(
    r"(?<!第)\d+\s*(号|栋|幢|单元|室|楼|层|巷|弄|路|街|道)|"
    r"\d+\s*(st|nd|rd|th)\s+(street|st|avenue|ave|road|rd)\b",
    re.IGNORECASE,
)


def is_forbidden_content(text: str) -> bool:
    """命中禁止清单就返回 True。只看文本本身，不看 kind。"""
    if not text:
        return True
    lowered = text.casefold()
    for keywords in _FORBIDDEN_KEYWORDS.values():
        if any(kw in lowered for kw in keywords):
            return True
    if any(p.search(text) for p in _FORBIDDEN_PATTERNS):
        return True
    return bool(_ADDRESS_PATTERN.search(text))


def build_extraction_prompt(user_message: str, assistant_reply: str) -> str:
    """拼提取提示词。助手回复截断，它只是上下文，不值得占 token。"""
    reply = assistant_reply.strip()
    if len(reply) > MAX_CONTENT_CHARS:
        reply = reply[:MAX_CONTENT_CHARS] + "…"
    # 不用 str.format：提示词里有 JSON 花括号，会被当成占位符。
    system = SYSTEM_PROMPT.replace("<<KINDS>>", KIND_SPEC).replace(
        "<<FORBIDDEN>>", "；".join(FORBIDDEN_CATEGORIES)
    )
    return system + (
        "\n\n---\n"
        f"用户：{user_message.strip()}\n"
        f"助手：{reply or '（无）'}\n"
        "---\n"
    )


_CODE_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _load_payload(raw_json: str) -> list[Any]:
    """尽最大努力把模型输出变成 list；拿不到就返回空。

    模型常见的三种走偏：包了代码块、包了一层 {"memories": [...]}、前后带解释文字。
    """
    if not raw_json:
        return []
    text = raw_json.strip()
    fenced = _CODE_FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()

    parsed: Any = None
    for candidate in (text, _slice_json(text)):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            break
        except (json.JSONDecodeError, ValueError):
            continue

    if parsed is None:
        return []
    if isinstance(parsed, dict):
        for key in ("memories", "items", "results", "data"):
            value = parsed.get(key)
            if isinstance(value, list):
                return value
        return []
    if isinstance(parsed, list):
        return parsed
    return []


def _slice_json(text: str) -> str | None:
    """抠出第一个平衡的数组/对象，容忍解释性前后缀。"""
    start = next((i for i, ch in enumerate(text) if ch in "[{"), None)
    if start is None:
        return None
    opener = text[start]
    closer = "]" if opener == "[" else "}"
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_candidates(
    raw_json: str,
    *,
    source_character_id: str = "",
    source_message_id: str = "",
) -> list[MemoryItem]:
    """把模型输出解析成 MemoryItem 列表。

    宽容优先：坏条目单条丢弃，不因为一条脏数据丢掉整轮。会做四件事：
    截断超长内容、过滤禁止类别、丢弃空/重复内容、把认不出的 kind 归为 FACT。
    """
    items: list[MemoryItem] = []
    seen: set[str] = set()
    for entry in _load_payload(raw_json):
        if isinstance(entry, str):
            entry = {"content": entry}
        if not isinstance(entry, dict):
            continue
        content = entry.get("content") or entry.get("memory") or entry.get("text")
        if not isinstance(content, str):
            continue
        # 超长内容截断而不是丢弃：前半段通常已经是完整事实。
        content = " ".join(content.split())[:MAX_CONTENT_CHARS].strip()
        if len(content) < MIN_CONTENT_CHARS:
            continue
        if is_forbidden_content(content):
            continue
        key = content.casefold()
        if key in seen:
            continue
        seen.add(key)
        items.append(
            MemoryItem(
                id=f"mem-{uuid.uuid4().hex}",
                content=content,
                kind=coerce_kind(entry.get("kind")) or MemoryKind.FACT,
                source_character_id=source_character_id,
                source_message_id=source_message_id,
            )
        )
        if len(items) >= MAX_ITEMS_PER_TURN:
            break
    return items


class MemoryExtractor:
    """回合后提取器：一次 LLM 调用 + 一次批量写入。

    ``llm`` 是 ``async (prompt) -> str``，返回模型原文；上层按
    ``memory_extract`` 场景接 LiteLLM，测试传 fake。
    """

    def __init__(self, port: Any, llm: LLMCall) -> None:
        self._port = port
        self._llm = llm
        self._tasks: set[asyncio.Task[None]] = set()

    async def extract(
        self,
        *,
        user_id: str,
        character_id: str,
        message_id: str,
        user_message: str,
        assistant_reply: str = "",
    ) -> list[MemoryItem]:
        """提取并写入，返回写入后的条目。异常在此吞掉，只记日志。"""
        if not user_message.strip():
            return []
        prompt = build_extraction_prompt(user_message, assistant_reply)
        try:
            raw = await self._llm(prompt)
        except Exception:  # noqa: BLE001 - 提取失败不能影响通话
            logger.warning("memory extraction LLM failed", exc_info=True)
            return []

        candidates = parse_candidates(
            raw,
            source_character_id=character_id,
            source_message_id=message_id,
        )
        if not candidates:
            return []
        try:
            return list(await self._port.add(user_id, candidates))
        except Exception:  # noqa: BLE001 - 写入失败同样不上升
            logger.warning("memory extraction write failed", exc_info=True)
            return []

    def schedule(
        self,
        *,
        user_id: str,
        character_id: str,
        message_id: str,
        user_message: str,
        assistant_reply: str = "",
    ) -> asyncio.Task[None]:
        """把提取丢到后台跑，回合本身不等待。

        任务引用留在实例上，避免被 GC 提前回收；完成的自动摘掉。
        """

        async def run() -> None:
            await self.extract(
                user_id=user_id,
                character_id=character_id,
                message_id=message_id,
                user_message=user_message,
                assistant_reply=assistant_reply,
            )

        task = asyncio.create_task(run(), name=f"memory-extract:{user_id}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def drain(self) -> None:
        """等待在飞任务结束；test 与优雅关闭用。"""
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)


def search_terms(text: str) -> Sequence[str]:
    """检索用的粗分词：空白/标点切开，中文再补二元组。

    只为「我记住的」与召回服务，不追求语义质量；后端真实检索靠向量。
    """
    tokens = [t for t in re.split(r"[\s,，。.!！?？;；:：、/|]+", text.casefold()) if t]
    terms: list[str] = list(tokens)
    for token in tokens:
        if len(token) > 1 and _is_cjk(token):
            terms.extend(token[i : i + 2] for i in range(len(token) - 1))
    return terms


def _is_cjk(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)
