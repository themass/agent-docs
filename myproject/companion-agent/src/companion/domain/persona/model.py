"""用户画像：角色对「这个人」的理解（docs/her-research 建议 1）。

和事实记忆分开：事实是一条条「用户说过什么」，画像是归纳出来的「他是什么样的人」，会随时间修订。
三条规则决定它的形状：

- **按「用户 + 角色」隔离**，和记忆一致：和林澈聊出来的画像，苏黛看不到。
- **推断和事实分开**：模型猜出来的（性格、心情）默认是推断，不当事实陈述；用户明确说过的才是事实。
  每条画像都带来源指针（``source_fact_ids``），用户删掉某条记忆时能顺着指针把画像一起清掉。
- **只增不改**：新信息不覆盖旧条目，而是让旧条目标为「已被取代」（``superseded_by``），保留证据链，可回滚。

画像分两段始终注入提示词（不靠检索命中）：static（称呼、职业、禁忌、重要的人）和 dynamic（近期在做的事）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import datetime

STATIC = "static"
DYNAMIC = "dynamic"
SECTIONS = (STATIC, DYNAMIC)

MAX_TOPIC_CHARS = 16
MAX_MEMO_CHARS = 120
MAX_SOURCES = 8
MAX_ENTRIES_PER_SECTION = 20

# 这些话题不进画像：敏感信息即使用户说过，也不做归纳留存（和记忆抽取的禁止清单同一精神）。
FORBIDDEN_TOPICS = frozenset({"身份证", "银行卡", "密码", "验证码", "住址", "病历", "性取向", "宗教", "政治倾向"})
_TOPIC_OK = re.compile(r"^[一-鿿A-Za-z0-9 _/·\-]{1,%d}$" % MAX_TOPIC_CHARS)


@dataclass(frozen=True)
class ProfileEntry:
    id: int
    topic: str                        # 话题：称呼 / 职业 / 家人 / 近况 ……
    memo: str                         # 一两句话的归纳
    section: str                      # static | dynamic
    is_inference: bool                # True = 模型推断，未经用户确认
    confidence: float
    source_fact_ids: tuple[str, ...]  # 由哪些事实记忆归纳而来（审计与联动删除用）
    mentioned_at: datetime | None     # 用户提到的时间
    happened_at: datetime | None      # 事情发生的时间（可空）
    superseded_by: int | None = None  # 被哪条取代；None = 当前有效
    suppressed: bool = False          # 用户说了「别再提」：保留记录但不注入、不再生成同话题

    @property
    def current(self) -> bool:
        return self.superseded_by is None and not self.suppressed


@dataclass(frozen=True)
class ProfileDraft:
    """抽取阶段的产物，还没落库。"""

    topic: str
    memo: str
    section: str = STATIC
    is_inference: bool = False
    confidence: float = 0.8
    source_fact_ids: tuple[str, ...] = ()
    mentioned_at: datetime | None = None
    happened_at: datetime | None = None


def normalize_topic(raw: object) -> str | None:
    topic = re.sub(r"\s+", " ", str(raw or "")).strip()
    if not topic or not _TOPIC_OK.match(topic):
        return None
    if any(word in topic for word in FORBIDDEN_TOPICS):
        return None
    return topic


def clean_draft(draft: ProfileDraft) -> ProfileDraft | None:
    """收紧一条草稿；不合格返回 None（调用方丢弃，不抛错）。"""
    topic = normalize_topic(draft.topic)
    memo = re.sub(r"\s+", " ", draft.memo or "").strip()
    if topic is None or len(memo) < 2 or any(word in memo for word in FORBIDDEN_TOPICS):
        return None
    section = draft.section if draft.section in SECTIONS else STATIC
    return replace(draft, topic=topic, memo=memo[:MAX_MEMO_CHARS], section=section,
                   confidence=min(1.0, max(0.0, draft.confidence)),
                   source_fact_ids=tuple(dict.fromkeys(draft.source_fact_ids))[:MAX_SOURCES])


# ---- 合并 ----

APPEND, UPDATE, ABORT = "append", "update", "abort"


@dataclass(frozen=True)
class MergeAction:
    kind: str                         # append | update | abort
    draft: ProfileDraft
    replaces: int | None = None       # update 时：被取代的旧条目 id
    reason: str = ""


def plan_merge(existing: list[ProfileEntry], draft: ProfileDraft) -> MergeAction:
    """决定一条草稿怎么并入现有画像。纯规则，不调模型。

    - 同话题被用户「别再提」压住了 → 放弃（尊重用户，不换个说法再生成）；
    - 同话题已有当前条目：备忘相同 → 放弃；推断不能覆盖用户明说的事实 → 放弃；否则取代旧条目；
    - 没有同话题条目 → 追加（该段已满时放弃，宁缺毋滥）。
    """
    same = [e for e in existing if e.topic == draft.topic]
    if any(e.suppressed for e in same):
        return MergeAction(ABORT, draft, reason="suppressed")
    current = [e for e in same if e.superseded_by is None]
    if current:
        old = current[0]
        if old.memo == draft.memo:
            return MergeAction(ABORT, draft, reason="unchanged")
        if draft.is_inference and not old.is_inference:
            return MergeAction(ABORT, draft, reason="inference_must_not_override_fact")
        return MergeAction(UPDATE, draft, replaces=old.id)
    in_section = [e for e in existing if e.current and e.section == draft.section]
    if len(in_section) >= MAX_ENTRIES_PER_SECTION:
        return MergeAction(ABORT, draft, reason="section_full")
    return MergeAction(APPEND, draft)


# ---- 渲染 ----

SECTION_TITLES = {STATIC: "关于他（长期）", DYNAMIC: "他最近的情况"}
INFERENCE_MARK = "（推测，不确定）"


def render_profile(entries: list[ProfileEntry], *, budget_chars: int) -> str:
    """渲染进提示词。推测的条目标明「推测」，让模型用试探的口气而不是当事实说。
    超预算时先丢 dynamic（会过期），再丢低置信度的推断，最后才动用户明说的 static。"""
    live = [e for e in entries if e.current]
    if not live or budget_chars <= 0:
        return ""

    def line(e: ProfileEntry) -> str:
        return f"- {e.topic}：{e.memo}{INFERENCE_MARK if e.is_inference else ''}"

    def build(items: list[ProfileEntry]) -> str:
        blocks: list[str] = []
        for section in SECTIONS:
            lines = [line(e) for e in items if e.section == section]
            if lines:
                blocks.append(f"{SECTION_TITLES[section]}：\n" + "\n".join(lines))
        return "\n\n".join(blocks)

    # 丢弃优先级：低置信度推断 → dynamic → 其余推断 → static 事实（按置信度由低到高，同分较旧的先丢）
    def drop_rank(e: ProfileEntry) -> tuple[int, float]:
        tier = 0 if (e.is_inference and e.confidence < 0.6) else 1 if e.section == DYNAMIC else \
            2 if e.is_inference else 3
        return (tier, e.confidence)

    keep = sorted(live, key=lambda e: (e.section != STATIC, -e.confidence, e.id))
    text = build(keep)
    for victim in sorted(keep, key=drop_rank):
        if len(text) <= budget_chars:
            break
        keep = [e for e in keep if e.id != victim.id]
        text = build(keep)
    return text if len(text) <= budget_chars else ""
