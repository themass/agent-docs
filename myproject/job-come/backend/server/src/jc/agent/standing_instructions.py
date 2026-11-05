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
_NO_SMALL_TALK = "不要自我介绍，不要寒暄，不要复述任务。用户已经在和你对话，直接回答或直接动手。"

#: Skills whose job is to be a person across the table. The interviewer greets, says who they are
#: and asks for a self-introduction (its own skill text says so); a shared rule forbidding exactly
#: that, in the same prompt, cancels it.
_SKILLS_THAT_GREET: frozenset[str] = frozenset({"coach-mock"})

_CONDUCT_RULES: tuple[str, ...] = (
    "档案索引不是完整经历。先用 jc_profile_get 的 section/field_path 按需读取；"
    "分页未读完不能断言没有证据。"
    "修改文案前核对 constraints；头像任务只读 contact，不读取无关经历。",
    "用户否认某项表述时，提议将原表述和正确说法保存到 constraints.retracted_claims，"
    "指定 scope=profile 或 experience/project 及 entity_id；必须由用户确认，不凭模型推测新增约束。",
    _NO_SMALL_TALK,
    "不要调用 ask_clarification。需要澄清就在回复里直接问，一次只问一个最关键的问题。",
    "改档案只能通过 jc_profile_patch 生成确认卡片。用户确认且工具返回 applied 之后才能说已保存。",
)

def _section(title: str, body: str) -> str:
    return f"## {title}\n{body.strip()}"


@lru_cache(maxsize=64)
def _methodology(skill_id: str, role_family: str | None) -> str:
    """The skill's contract and methodology for this run, memoised on its two inputs.

    The text is a pure function of `(skill_id, role_family)`, so two users in the same family share
    one composition. Bounded at 64 entries, comfortably above `skills x families`.

    A failure is swallowed into "" for the same reason the capture in `JCProductRulesMiddleware`
    is: a missing family fragment must degrade the prompt, not take the conversation down. A skill
    that does not exist is not swallowed here: `require_skill` raises, and the roles check at boot
    makes that unreachable for a declared role.
    """
    from jc.domain.role_families import get_playbook
    from jc.skills.composer import compose_turn_methodology

    playbook = get_playbook(role_family) if role_family else None
    return compose_turn_methodology(skill_id=skill_id, playbook=playbook).strip()


def build_standing_block(
    *, skill_id: str | None, role_family: str | None, reply_language: str
) -> str:
    """Render this run's standing instructions: language, the skill's task, conduct, methodology.

    Every skill gets the same layers. The task framing is the skill's own `references/framing.md`
    when it has one; the methodology is the skill's contract and fragments (see
    `jc.skills.composer.compose_turn_methodology`). A skill is only ever given its own text: an
    interview turn never receives resume rewriting rules, because it does not declare them.
    """
    from jc.skills.loader import require_skill

    parts: list[str] = [_section("回复语言", reply_language)]

    if skill_id:
        framing = require_skill(skill_id).reference("framing")
        if framing:
            parts.append(_section("本会话任务", framing))

    rules = [
        rule for rule in _CONDUCT_RULES
        if not (rule == _NO_SMALL_TALK and skill_id in _SKILLS_THAT_GREET)
    ]
    parts.append(_section("行为约束", "\n".join(f"- {rule}" for rule in rules)))

    if skill_id:
        methodology = _methodology(skill_id, role_family)
        if methodology:
            parts.append(_section("技能与方法（本会话适用）", methodology))

    return "\n\n".join(parts)
