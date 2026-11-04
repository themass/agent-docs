"""Every run's system layer carries its skill's own contract, and only that skill's.

This is the rule ADR-006 section 3 states. It was broken: a session's contract (the SKILL.md body)
never reached the model, because the composer exempted the default skill on the strength of an
identity that did not exist. These tests fail if any skill's body stops reaching the layer.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from jc.agent.roles import roles
from jc.agent.standing_instructions import build_standing_block
from jc.deerflow_middleware import JCProductRulesMiddleware
from jc.skills.composer import compose_skill_prompt
from jc.skills.loader import all_skill_ids, require_skill


def _first_line(body: str) -> str:
    return next(line.strip() for line in body.splitlines() if line.strip())


@pytest.mark.parametrize("skill_id", all_skill_ids())
def test_every_skill_contract_reaches_the_standing_layer(skill_id):
    layer = build_standing_block(skill_id=skill_id, role_family="backend", reply_language="zh-CN")
    assert _first_line(require_skill(skill_id).body) in layer


@pytest.mark.parametrize("skill_id", all_skill_ids())
def test_a_single_call_prompt_is_the_skill_contract_plus_its_fragments(skill_id):
    prompt = compose_skill_prompt(skill_id)
    assert _first_line(require_skill(skill_id).body) in prompt
    for topic in require_skill(skill_id).always_loaded:
        assert require_skill(skill_id).reference(topic) in prompt


def test_a_skill_never_receives_another_skills_contract():
    interview = build_standing_block(
        skill_id="coach-mock", role_family=None, reply_language="zh-CN"
    )
    for other in ("resume-coach", "profile-interview"):
        assert _first_line(require_skill(other).body) not in interview


def test_the_interview_skill_gets_no_resume_methodology():
    interview = build_standing_block(
        skill_id="coach-mock", role_family="backend", reply_language="zh-CN"
    )
    assert "简历优化 Agent" not in interview
    assert "简历改写" not in interview


def test_the_system_message_is_jc_owned_and_names_no_file_or_shell_tool(monkeypatch):
    """DeerFlow's template describes file, shell and upload tools JC does not offer. A run that
    carries that text tries to call them, so the template must not reach the model."""
    class Request(SimpleNamespace):
        def override(self, **changes):
            return Request(**{**vars(self), **changes})

    seen = {}

    def handler(req):
        seen["text"] = req.system_message.content

    template = "DEERFLOW TEMPLATE read_file /mnt/user-data"
    request = Request(system_message=SimpleNamespace(content=template), runtime=None)
    JCProductRulesMiddleware().wrap_model_call(request, handler)
    text = seen["text"]
    assert "DEERFLOW TEMPLATE" not in text
    for forbidden in ("read_file", "/mnt/", "write_file", "bash"):
        assert forbidden not in text, forbidden
    assert "--- BEGIN USER INPUT ---" in text


def test_the_middleware_adds_the_layer_to_the_system_message_and_keeps_the_base(monkeypatch):
    seen = {}

    class Request(SimpleNamespace):
        def override(self, **changes):
            return Request(**{**vars(self), **changes})

    base = "DeerFlow base system prompt."
    request = Request(system_message=SimpleNamespace(content=base), runtime=None)
    middleware = JCProductRulesMiddleware()

    def handler(req):
        seen["content"] = req.system_message.content
        return "ok"

    assert middleware.wrap_model_call(request, handler) == "ok"
    assert seen["content"].startswith("你是舟卡的智能体")
    assert "<jc_context>" in seen["content"]


def test_the_middleware_does_not_write_its_layer_into_history():
    """The layer is per call. A checkpoint keeps what the user and the model said, nothing more."""
    from langchain.agents.middleware import AgentMiddleware

    for hook in ("before_agent", "abefore_agent"):
        assert getattr(JCProductRulesMiddleware, hook) is getattr(AgentMiddleware, hook), hook


def test_the_default_role_is_the_one_whose_contract_leads_a_new_session():
    default = next(r for r in roles().values() if r.default)
    assert default.skill_ids[0] == default.id
