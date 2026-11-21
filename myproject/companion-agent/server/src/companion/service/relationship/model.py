"""关系状态：「你们到了哪一步」——与画像（她**知道**你什么）分开的维度。

设计见 docs/relationship-state-design.md。三条规则决定形状：

- **只增不改**：warmth 只加不减。关系不会因为一次没聊就归零，但**有效温度**随空闲天数
  在**读时**衰减（连续函数，没有后台 sweep）——久不联系回到「熟悉」而不是「陌生人」。
- **阶段读时算**：阈值画在有效温度上，不落库。落库就要每次衰减后回写，读时算永远一致。
- **确定性算术**：不调模型判断「他们多熟」。可解释、可测试、不烧 token；
  推断关系的是模型，这里只数来回、记时间。

消费点只有两个：提示词里的一小段（怎么说）与主动闸门（该不该打扰）。
它不写进画像或记忆，不进「我记住的」页面。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# ---- 累积（after_turn 每个成功回合加一点）----

_BASE_DELTA = 0.5            # 一次正常来回
_LENGTH_DIVISOR = 400.0      # 说得越多越暖：400 字顶格
_LENGTH_BONUS_CAP = 0.5      # 字数加成封顶
_DELTA_CAP = 2.0             # 单回合上限：一句话不该把关系推进一步以上


def delta_for(user_text: str) -> float:
    """这一回合该加多少温度。纯函数：同样的话永远加同样的分。"""
    bonus = min(_LENGTH_BONUS_CAP, max(0, len(user_text)) / _LENGTH_DIVISOR)
    return min(_DELTA_CAP, _BASE_DELTA + bonus)


# ---- 衰减（读时算）----

# 前 3 天不衰减；之后每天 -5%，最低保留 30%。
_NO_DECAY_DAYS = 3
_DAILY_DECAY = 0.05
_DECAY_FLOOR = 0.3


def decay_factor(days_idle: float) -> float:
    if days_idle <= _NO_DECAY_DAYS:
        return 1.0
    return max(_DECAY_FLOOR, 1.0 - _DAILY_DECAY * (days_idle - _NO_DECAY_DAYS))


# ---- 阶段（阈值画在有效温度上；先验起点，不是调优目标）----

STAGE_STRANGER = "stranger"          # 刚认识
STAGE_ACQUAINTANCE = "acquaintance"  # 有几次来回了
STAGE_FAMILIAR = "familiar"          # 会自然开起玩笑
STAGE_CLOSE = "close"                # 关系稳了，会惦记
STAGE_INTIMATE = "intimate"          # 很熟了

# (上限, 阶段)：effective < 上限 才算这一档。
_STAGE_TABLE = (
    (3.0, STAGE_STRANGER),
    (10.0, STAGE_ACQUAINTANCE),
    (25.0, STAGE_FAMILIAR),
    (50.0, STAGE_CLOSE),
)
# 主动闸门用「满档」温度把系数从 1.5 线性拉回 1.0。
SATURATION = 50.0


def stage_of(effective: float) -> str:
    for ceiling, name in _STAGE_TABLE:
        if effective < ceiling:
            return name
    return STAGE_INTIMATE


# ---- 存储里的一行 ----


@dataclass(frozen=True)
class Relationship:
    owner_id: int
    role_id: str
    warmth: float
    interactions: int
    last_active_at: datetime | None


def effective_warmth(rel: Relationship, *, now: datetime) -> float:
    """衰减后的温度。没有互动记录就是 0（陌生人）。"""
    if rel.last_active_at is None:
        return 0.0
    last = rel.last_active_at.replace(tzinfo=None) if rel.last_active_at.tzinfo else rel.last_active_at
    now_n = now.replace(tzinfo=None) if now.tzinfo else now
    days_idle = max(0.0, (now_n - last).total_seconds() / 86400.0)
    return rel.warmth * decay_factor(days_idle)


def snapshot(rel: Relationship, *, now: datetime) -> "RelationshipSnapshot":
    return RelationshipSnapshot(stage=stage_of(effective_warmth(rel, now=now)),
                                interactions=rel.interactions,
                                last_active_at=rel.last_active_at)


@dataclass(frozen=True)
class RelationshipSnapshot:
    """读时算好的形状：阶段 + 互动数 + 最近活跃。提示词与闸门都只认这个。"""
    stage: str
    interactions: int
    last_active_at: datetime | None


# ---- 提示词渲染（≤200 字的一段，见设计 §5.1）----

_STAGE_LINES = {
    STAGE_STRANGER: "你们刚认识，还不太熟。说话保持礼貌和距离感，不要假设了解对方的生活，"
                    "不要开玩笑或套近乎，可以自然地多问两句来了解对方。",
    STAGE_ACQUAINTANCE: "你们已经聊过几次，有点印象了。可以轻松一点，但不要假设你了解对方的全部生活，"
                        "偶尔自然地提起他说过的事。",
    STAGE_FAMILIAR: "你们比较熟了。可以自然地开玩笑、接他的梗，记得他说过的小细节，"
                    "但不要假设你了解他的全部生活。",
    STAGE_CLOSE: "你们关系很稳，彼此惦记。可以主动关心他的近况，语气亲昵一点，"
                 "记得他说过的琐事并自然地提起。",
    STAGE_INTIMATE: "你们非常熟了，无话不谈。可以很随意、很亲昵，直接表达关心，"
                    "不用客套，也不用解释你们的关系。",
}

_RELATIONSHIP_HEADER = "你和他的关系"


def render_relationship_block(snapshot: RelationshipSnapshot, *, now: datetime) -> str:
    """渲染进提示词的一小段。没有互动记录 → 空串（这一轮没有这段）。"""
    if snapshot.interactions <= 0 and snapshot.last_active_at is None:
        return ""
    lines = [f"{_RELATIONSHIP_HEADER}：{_STAGE_LINES[snapshot.stage]}"]
    if snapshot.last_active_at is not None:
        last = snapshot.last_active_at.replace(tzinfo=None) if snapshot.last_active_at.tzinfo \
            else snapshot.last_active_at
        now_n = now.replace(tzinfo=None) if now.tzinfo else now
        days = (now_n - last).days
        if days <= 0:
            when = "就在不久前"
        elif days == 1:
            when = "一天前"
        else:
            when = f"{days} 天前"
        lines.append(f"你们聊过 {snapshot.interactions} 次，最近一次是{when}。")
    return "\n".join(lines)
