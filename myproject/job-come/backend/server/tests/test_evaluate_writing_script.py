"""The writing evaluator's own judgement, tested without a model.

`scripts/evaluate_writing.py` is the only thing that will ever assert the pipeline's
writing promises, and it only runs where the gateway is reachable — which is not CI. A
harness that silently always passes is worse than no harness, so its decision functions
are unit-tested here with hand-built drafts standing in for model output.

What is *not* tested here is the live path itself; that is the script's whole purpose and
needs real credentials.
"""

import importlib.util
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
_SCRIPT = _SCRIPTS_DIR / "evaluate_writing.py"


def _load():
    name = "jc_evaluate_writing"
    # Loading by path, unlike `python scripts/evaluate_writing.py`, does not put the
    # script's own directory on `sys.path`. `evaluate_writing.py` needs that to resolve
    # its first import, `from lib.bootstrap import ensure_project_env`.
    scripts_dir_str = str(_SCRIPTS_DIR)
    if scripts_dir_str not in sys.path:
        sys.path.insert(0, scripts_dir_str)
    spec = importlib.util.spec_from_file_location(name, _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # `@dataclass` resolves annotations through `sys.modules[cls.__module__]`, so a
    # script loaded by path must be registered before it is executed.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ew = _load()


def test_the_script_exists_where_the_docs_say_it_does() -> None:
    assert _SCRIPT.is_file()


def test_identical_drafts_are_reported_as_indistinguishable() -> None:
    """The failure this catches: the angle control not reaching the output at all."""
    bullets = ["主导订单服务拆分，发布耗时从 40 分钟降到 6 分钟"]
    assert ew._pairwise_sameness(bullets, bullets) == 1.0
    assert 1.0 > ew._SAMENESS_CEILING


def test_a_genuinely_reangled_draft_is_not_reported_as_the_same() -> None:
    """Same facts, different lead. This must sit below the ceiling or every correct run
    fails and the script gets switched off."""
    scope = [
        "主导覆盖 6 条业务线、日均 1200 万单的订单主链路拆分",
        "搭建全链路压测平台，覆盖 12 条核心交易链路",
    ]
    outcome = [
        "将订单发布耗时从 40 分钟压缩到 6 分钟，迁移期间零线上事故",
        "压测平台上线后，大促前容量问题提前暴露，故障率下降",
    ]
    score = ew._pairwise_sameness(scope, outcome)
    assert score < ew._SAMENESS_CEILING, score


def test_sameness_is_zero_when_an_arm_produced_nothing() -> None:
    assert ew._pairwise_sameness([], ["主导订单服务拆分"]) == 0.0


def test_bullets_are_collected_from_experiences_and_projects() -> None:
    sections = {
        "experience_blocks": [{"bullets": ["A", "B"]}],
        "project_blocks": [{"bullets": ["C"]}],
        "education_blocks": [{"bullets": ["ignored"]}],
    }
    assert ew._bullets(sections) == ["A", "B", "C"]


def test_the_planted_bullet_changes_only_the_verb() -> None:
    """If the probe changed anything else, a reviewer failure would not isolate the
    ownership rule."""
    source = "参与统一配置中心的建设，负责客户端 SDK 接入"
    planted = ew.inflate_ownership(source)
    assert planted == "主导统一配置中心的建设，负责客户端 SDK 接入"
    assert planted[2:] == source[2:]


def test_a_mid_sentence_participation_verb_is_still_inflated() -> None:
    assert ew.inflate_ownership("作为核心成员参与推送链路改造") == (
        "作为核心成员主导推送链路改造"
    )


def test_a_line_with_no_weak_verb_still_yields_an_ownership_claim() -> None:
    """The probe must produce a known-bad bullet regardless of the sample's wording,
    otherwise the reviewer gate goes unchecked on some profiles."""
    assert ew.inflate_ownership("推送链路改造").startswith("主导")


def test_angle_arms_are_valid_presets_and_within_the_product_cap() -> None:
    """A typo here would silently fall back to the role default, and the script would
    compare two identical configurations and report the product as broken."""
    from jc.services.framing_presets import MAX_EMPHASES, get_preset, resolve_emphases

    for arm in ew._ANGLE_ARMS:
        assert len(arm) <= MAX_EMPHASES, arm
        for preset_id in arm:
            assert get_preset(preset_id) is not None, preset_id
        assert resolve_emphases(list(arm), role_family="backend") == list(arm)


def test_angle_arms_are_pairwise_distinct() -> None:
    """Two arms with the same selection would make the variance comparison vacuous."""
    assert len({tuple(a) for a in ew._ANGLE_ARMS}) == len(ew._ANGLE_ARMS)
