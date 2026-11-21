from __future__ import annotations

from student_agent.config import Settings


def test_missing_llm_variables_mean_script_mode_and_never_raise(tmp_path):
    s = Settings.from_env({}, env_file=tmp_path / "absent.env")
    assert s.mode == "script"
    assert not s.llm_configured


def test_partial_llm_configuration_is_still_script_mode(tmp_path):
    s = Settings.from_env({"POETRY_LLM_API_BASE": "http://gateway.invalid"}, env_file=tmp_path / "absent.env")
    assert s.mode == "script"


def test_full_configuration_enables_llm_and_override_forces_script(tmp_path):
    env = {"POETRY_LLM_API_BASE": "http://gateway.invalid", "POETRY_LLM_API_KEY": "k-test",
           "POETRY_LLM_MODEL_PRIMARY": "m-primary", "POETRY_LLM_MODEL_FALLBACK": "m-fallback"}
    assert Settings.from_env(env, env_file=tmp_path / "x").mode == "llm"
    assert Settings.from_env({**env, "STUDENT_AGENT_MODE": "script"}, env_file=tmp_path / "x").mode == "script"


def test_secrets_never_appear_in_repr_or_health(tmp_path):
    env = {"POETRY_LLM_API_BASE": "http://gateway.invalid", "POETRY_LLM_API_KEY": "sk-very-secret",
           "POETRY_LLM_MODEL_PRIMARY": "model-name-x"}
    s = Settings.from_env(env, env_file=tmp_path / "x")
    for text in (repr(s), str(s.health())):
        assert "sk-very-secret" not in text
        assert "gateway.invalid" not in text
        assert "model-name-x" not in text


def test_env_file_only_reads_known_keys(tmp_path):
    f = tmp_path / ".env"
    f.write_text("POETRY_LLM_API_KEY=abc\nUNRELATED_SECRET=zzz\n# comment\nSTUDENT_AGENT_PORT=9001\n", encoding="utf-8")
    s = Settings.from_env({}, env_file=f)
    assert s.llm_key == "abc"
    assert s.port == 9001


def test_default_llm_actions_are_the_b1_set(tmp_path):
    s = Settings.from_env({}, env_file=tmp_path / "x")
    assert s.llm_actions == frozenset({"rephrase", "hint"})
    assert s.llm_poet is False


# ---- the auth red line (B-6): fail closed instead of remembering a checklist line -------------------

def test_default_binding_is_loopback_and_allowed(tmp_path):
    s = Settings.from_env({}, env_file=tmp_path / "x")
    assert s.host == "127.0.0.1"
    assert s.binding_error() is None


def test_auth_none_refuses_any_non_loopback_bind():
    """auth=none only checks that a header exists; off loopback that is no auth at all."""
    for host in ("0.0.0.0", "::", "192.168.1.10", "agent.internal"):
        assert Settings(host=host, auth="none").binding_error(), host


def test_auth_java_allows_any_bind():
    assert Settings(host="0.0.0.0", auth="java").binding_error() is None


def test_binding_refusal_names_the_variable_to_fix():
    message = Settings(host="0.0.0.0", auth="none").binding_error() or ""
    assert "STUDENT_AGENT_AUTH=java" in message and "STUDENT_AGENT_HOST" in message


def test_host_comes_from_env(tmp_path):
    assert Settings.from_env({"STUDENT_AGENT_HOST": "0.0.0.0"}, env_file=tmp_path / "x").host == "0.0.0.0"
