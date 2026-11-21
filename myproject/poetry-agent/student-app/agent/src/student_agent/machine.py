"""The five-step machine, agent side. The program decides what is allowed; a model never does.

Order: 读 read, 到 arrive, 见 meet, 回 return, 诵 recite. The agent cannot move a learner: it may only
*suggest* a step in ``next``, and the front end's own state machine decides whether to follow.
"""
from __future__ import annotations

STEPS = ("read", "arrive", "meet", "return", "recite")

# Which actions may be answered in which step. ``decline`` is always allowed; ``faq`` is the internal
# action a free-text question is routed to when it matches a prepared answer.
ALLOWED: dict[str, frozenset[str]] = {
    "read": frozenset(),  # collect the learner's question; never explain before they have read
    "arrive": frozenset({"open_layer", "basis", "rephrase"}),
    "meet": frozenset({"basis", "rephrase"}),
    "return": frozenset({"hint", "rephrase", "basis"}),
    "recite": frozenset({"recite_prompt", "rephrase", "ask_why", "evaluate_retell"}),
}


def allowed(step: str, action: str) -> bool:
    if action == "decline":
        return True
    if action == "faq":
        return step != "read"
    return action in ALLOWED.get(step, frozenset())


def suggest(step: str, action: str, missing_points: int = 0) -> str:
    """A suggestion only. The only place a step is ever proposed."""
    if action == "evaluate_retell" and missing_points:
        return "suggest_step:return"
    return "no_action"
