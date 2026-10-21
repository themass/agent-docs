"""Instructions that are true for a whole session, rendered once at the system layer.

The problem this fixes
----------------------
Every turn's `HumanMessage` used to carry, ahead of the user's own words: the
reply-language rule, 「不要自我介绍，不要调用 ask_clarification」, a task header,
and (on the first turn) the entire role-family rewriting methodology. Two of
those were *already* being injected as system content by
`JCProductRulesMiddleware` — so the model received the language rule and the
no-self-introduction rule twice per turn, in two voices — and the user's actual
question was buried several thousand characters into a message that mostly
consisted of standing policy.

That shape is wrong for three independent reasons, and the token cost is only
the smallest of them:

1. A `HumanMessage` is supposed to be what the user said. Reading a trace to
   find out what someone asked meant hunting for 「用户原话：」 in the middle of
   a wall of instructions, which is what made the ledger unreadable.
2. Standing policy competes with the live question for the model's attention at
   the *same* position in the message. System content outranks user content by
   design; putting policy in the user turn gives up that ranking.
3. Repeating a rule verbatim每轮 and then, on later turns, replacing it with
   「方法已在本会话开头发送过」 means the model sees two different claims about
   where its methodology is. The system layer makes the methodology actually be
   where that sentence says it is.

What lives here and what does not
---------------------------------
Here: anything whose truth does not depend on this particular turn — the reply
language, the task framing, the role-family methodology.

Not here: the user's words, which field they clicked, and (on the first turn)
the profile digest. Those change turn to turn and belong in the turn.

Why the middleware composes this instead of receiving it
--------------------------------------------------------
The embedded agent is cached per process and shared across users
(`_CLIENT_CACHE`), so this text cannot be baked into the agent at build time.
It is composed per run from the two identifiers the run already carries in its
`authz_attributes` — the coach skill and the role family — which travel through
LangGraph's per-run `runtime.context` and therefore cannot be clobbered by a
concurrent turn for a different user (ADR-004). Composition is memoised on
those two ids, so the per-run cost is a dict lookup rather than a skill-file
read and a fragment assembly.
"""

from __future__ import annotations

from functools import lru_cache

#: Rules that previously sat at the top of every user turn as literal text.
#: `ask_clarification` is DeerFlow's generic "ask the user something" tool, which
#: in this product is wrong twice over: the sidebar already has the user's
#: attention, and the tool's prompt produces an English question in a Chinese UI.
_CONDUCT_RULES: tuple[str, ...] = (
    "档案索引不是完整经历。先用 jc_profile_get 的 section/field_path 按需读取；"
    "分页未读完不能断言没有证据。"
    "修改文案前核对 constraints；头像任务只读 contact，不读取无关经历。",
    "用户否认某项表述时，提议将原表述和正确说法保存到 constraints.retracted_claims，"
    "指定 scope=profile 或 experience/project 及 entity_id；必须由用户确认，不凭模型推测新增约束。",
    "不要自我介绍，不要寒暄，不要复述任务。用户已经在和你对话，直接回答或直接动手。",
    "不要调用 ask_clarification。需要澄清就在回复里直接问，一次只问一个最关键的问题。",
    "改档案只能通过 jc_profile_patch 生成确认卡片。用户确认且工具返回 applied 之后才能说已保存。",
)

_FRAMING: dict[str, str] = {
    "resume-coach": (
        "本会话的任务是简历优化：基于档案里已有的事实改写表达，不新增用户没说过的经历、"
        "数字或成果。意图明确时直接给出改写并调用 jc_profile_patch；缺关键事实先问。"
    ),
    "profile-interview": (
        "本会话的任务是建档访谈：这份档案还不足以生成简历，所以要把材料问出来，不是润色。"
        "一次只问一个问题；用户给出真实经历后用 jc_profile_patch 写进对应位置并由用户确认；"
        "材料够了就告诉他可以生成第一版。"
    ),
}


def _section(title: str, body: str) -> str:
    return f"## {title}\n{body.strip()}"


@lru_cache(maxsize=64)
def _methodology(skill_id: str, role_family: str | None) -> str:
    """The role-family rewriting methodology for this session.

    Memoised on `(skill_id, role_family)` rather than per session: the text is a
    pure function of those two, so two users in the same family share one
    composition. Bounded at 64 entries, comfortably above `skills × families`.

    Returns "" when the skill ships no fragments, so the caller can concatenate
    unconditionally. Failures are swallowed into "" for the same reason the
    capture in `JCProductRulesMiddleware` is: a missing skill file must degrade
    the prompt, not take the conversation down.
    """
    try:
        from jc.domain.role_families import get_playbook
        from jc.skills.composer import compose_coach_guidance

        return compose_coach_guidance(
            skill_id=skill_id, playbook=get_playbook(role_family)
        ).strip()
    except Exception:  # noqa: BLE001
        return ""


def build_standing_block(
    *, skill_id: str | None, role_family: str | None, reply_language: str
) -> str:
    """Render this session's standing instructions, or "" when none apply.

    Only the resume paths get framing and methodology. A mock-interview or
    apply-pipeline turn has its own task shape and must not be handed resume
    rewriting rules — returning just the conduct rules and the language for
    those is deliberate, not an oversight.
    """
    skill = skill_id or "resume-coach"
    parts: list[str] = [_section("回复语言", reply_language)]

    framing = _FRAMING.get(skill)
    if framing:
        parts.append(_section("本会话任务", framing))

    parts.append(_section("行为约束", "\n".join(f"- {rule}" for rule in _CONDUCT_RULES)))

    if skill in _FRAMING:
        methodology = _methodology(skill, role_family)
        if methodology:
            parts.append(_section("改写方法（本会话适用）", methodology))

    return "\n\n".join(parts)
