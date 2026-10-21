"""DeerFlow harness config: does it load, and does a role get its real contract."""

from pathlib import Path

import pytest
import yaml

_CONFIG = Path(__file__).resolve().parents[1] / ".." / "agent" / "deerflow" / "config.yaml"


@pytest.fixture
def harness_env(monkeypatch) -> None:
    monkeypatch.setenv("JC_LLM_API_BASE", "https://example.invalid/v1")
    monkeypatch.setenv("JC_LLM_API_KEY", "test-key")
    monkeypatch.setenv("JC_SUMMARIZATION_TRIGGER_TOKENS", "32000")
    monkeypatch.setenv("JC_SUMMARIZATION_KEEP_MESSAGES", "6")
    # Mirrors what jc.adapters.deerflow_harness_client._configure_deerflow_paths
    # always sets before DeerFlow loads this config — these four $VAR
    # placeholders in config.yaml (pii_redaction / token_budget) are not
    # optional at load time even when the feature itself is off.
    monkeypatch.setenv("JC_PII_REDACTION_ENABLED", "false")
    monkeypatch.setenv("JC_PII_REDACTION_TOKEN_SECRET", "jc-pii-redaction-disabled-placeholder")
    monkeypatch.setenv("JC_TOKEN_BUDGET_ENABLED", "true")
    monkeypatch.setenv("JC_TOKEN_BUDGET_MAX_TOKENS", "150000")


def test_deerflow_config_loads(harness_env) -> None:
    from deerflow.config.app_config import AppConfig

    cfg = AppConfig.from_file(str(_CONFIG))
    assert cfg.sandbox is not None
    assert cfg.subagents.max_total_per_run >= 1


def test_no_role_carries_a_second_hand_written_contract() -> None:
    """A declared role points at its skill; it does not restate it.

    The checked-in `system_prompt` used to be a three-line English summary of a 101-line
    skill contract. Nothing failed when the two disagreed, which is exactly why this is
    asserted on the source file rather than only on the composed result.
    """
    raw = yaml.safe_load(_CONFIG.read_text(encoding="utf-8"))
    custom = raw["subagents"]["custom_agents"]
    assert custom
    for name, spec in custom.items():
        prompt = str(spec["system_prompt"]).strip()
        assert prompt.startswith("skill:"), f"{name} restates its role instead of pointing at it"
        assert "\n" not in prompt, f"{name} has prose in a field that should be a pointer"


def test_a_role_prompt_is_composed_from_its_skill_at_boot(harness_env, tmp_path) -> None:
    from deerflow.config.app_config import AppConfig

    from jc.adapters.deerflow_harness_client import resolve_subagent_prompts_in_config
    from jc.skills.composer import compose_role_baseline

    resolved = resolve_subagent_prompts_in_config(_CONFIG, dest=tmp_path / "config.runtime.yaml")
    cfg = AppConfig.from_file(str(resolved))
    writer = cfg.subagents.custom_agents["resume-writer"]
    assert writer.system_prompt == compose_role_baseline("resume-writer")
    # The honesty rule lives in the skill body, so reaching it proves the body arrived
    # rather than a summary of it.
    assert "不编造" in writer.system_prompt or "never invent" in writer.system_prompt.lower()
    assert not writer.system_prompt.startswith("skill:")


def _pointed_at(skill_id: str, tmp_path: Path) -> Path:
    raw = yaml.safe_load(_CONFIG.read_text(encoding="utf-8"))
    raw["subagents"]["custom_agents"]["resume-writer"]["system_prompt"] = f"skill:{skill_id}"
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def test_an_unknown_skill_pointer_fails_loudly(harness_env, tmp_path) -> None:
    """Falling back to the literal string would run a role with its own id as its prompt."""
    from jc.adapters.deerflow_harness_client import resolve_subagent_prompts_in_config

    with pytest.raises(LookupError):
        resolve_subagent_prompts_in_config(
            _pointed_at("does-not-exist", tmp_path), dest=tmp_path / "out.yaml"
        )


def test_a_skill_that_composes_to_nothing_fails_loudly(harness_env, tmp_path, monkeypatch) -> None:
    """An empty contract is the same failure as a missing one, and just as silent.

    `require_skill` catches the missing case. A package that exists but whose SKILL.md is
    empty — a bad merge, a truncated write — would pass it and hand the role an empty
    system prompt, which reads as a working config.
    """
    from jc.adapters.deerflow_harness_client import resolve_subagent_prompts_in_config
    from jc.skills import composer

    monkeypatch.setattr(composer, "compose_role_baseline", lambda skill_id: "   ")
    with pytest.raises(RuntimeError, match="composed to nothing"):
        resolve_subagent_prompts_in_config(
            _pointed_at("resume-writer", tmp_path), dest=tmp_path / "out.yaml"
        )
