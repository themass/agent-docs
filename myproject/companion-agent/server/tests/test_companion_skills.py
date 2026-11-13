"""陪伴 skill 体系：卡片写法、常驻层、预算，以及「不许说的话」的守卫。

这里用的是仓库里真实的 skills/ 与 characters/，不是临时目录——
目的就是防止以后有人改了 skill 或角色卡，悄悄把底线弄丢或把提示词撑爆。
"""

import pytest

from companion.roles.files import CharacterSource
from companion.adapters.skills.library import DEFAULT_SKILLS_ROOT, SkillLibrary
from companion.chat.assembler import skill_id_of, skill_ids_of
from companion.roles.resolver import RoleProfileResolver
from companion.paths import CHARACTERS_DIR
from companion.domain.prompt.roleplay import PromptBudget, build_prompt_plan
from companion.roles.card import CharacterCard

CHARACTERS = CharacterSource(CHARACTERS_DIR)
LIBRARY = SkillLibrary(DEFAULT_SKILLS_ROOT)
COMPANION_CARDS = ("linche", "sudai")
OPTIONAL_COMPANION_SKILLS = ("active-listening", "memory-callback", "proactive-checkin", "shared-activity")

# 这些话会制造愧疚、独占或阻止离开（调研文档 5.7）。skill 里只能以「不要说」的反例出现，
# 所以这里不检查全文，而是检查「可以这样做」的示范句不含它们——见下面的测试。
GUILT_PHRASES = ("你怎么才来", "我等了你好久", "你是不是不要我了", "只有我懂你", "我好想你")


def _card(skill) -> CharacterCard:
    card = CharacterCard(name="测试")
    card.extensions = {"vvv": {"skill": skill}} if skill is not None else {}
    return card


# ---- 卡片写法 ----------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("growth-coaching", ["growth-coaching"]),
    (["a", "b"], ["a", "b"]),
    (["a", "a", "", 3, None, "b"], ["a", "b"]),   # 去重、丢掉非字符串和空串，保持顺序
    ("", []),
    (None, []),
    (42, []),
    ({"x": 1}, []),
])
def test_skill_ids_of_accepts_string_or_list(value, expected):
    assert skill_ids_of(_card(value)) == expected


def test_skill_id_of_is_still_the_first_id():
    assert skill_id_of(_card(["a", "b"])) == "a"
    assert skill_id_of(_card("a")) == "a"
    assert skill_id_of(_card(None)) is None


# ---- 常驻层 ------------------------------------------------------------------

def test_exactly_one_skill_is_always_loaded_and_it_is_companion_core():
    always = [s for s in LIBRARY.skill_ids() if LIBRARY.load(s).always_loaded]
    assert always == ["companion-core"]


def test_companion_core_is_appended_even_when_nothing_is_requested():
    assert "陪伴的底线" in LIBRARY.compose([])


def test_requested_skill_comes_before_the_always_loaded_one():
    text = LIBRARY.compose(["growth-coaching"])
    assert text.index("个人成长教练") < text.index("陪伴的底线")


def test_non_companion_skill_is_not_pulled_in_by_the_always_loaded_one():
    # problem-solving 的 always-loaded 是历史遗留的列表，必须仍然读成 False
    assert "解题" not in LIBRARY.compose(["growth-coaching"])


async def test_resolver_gives_companion_core_to_cards_without_a_skill():
    class OneCard:
        def load(self, _):
            return _card(None)

    resolver = RoleProfileResolver(catalog=None, user_roles=None, characters=OneCard(),
                                   skills=LIBRARY, skill_ids_of=skill_ids_of)
    profile = await resolver.resolve(role_id="x", owner_id=1)
    assert "陪伴的底线" in profile.method


async def test_resolver_still_honours_the_old_single_value_hook():
    class OneCard:
        def load(self, _):
            return _card("growth-coaching")

    resolver = RoleProfileResolver(catalog=None, user_roles=None, characters=OneCard(),
                                   skills=LIBRARY, skill_id_of=skill_id_of)
    profile = await resolver.resolve(role_id="x", owner_id=1)
    assert "个人成长教练" in profile.method and "陪伴的底线" in profile.method


async def test_resolver_survives_a_missing_skill():
    class OneCard:
        def load(self, _):
            return _card("no-such-skill")

    resolver = RoleProfileResolver(catalog=None, user_roles=None, characters=OneCard(),
                                   skills=LIBRARY, skill_ids_of=skill_ids_of)
    profile = await resolver.resolve(role_id="x", owner_id=1)
    assert profile.method == ""   # 人设本身仍能撑起一轮对话


# ---- 预算 --------------------------------------------------------------------

@pytest.mark.parametrize("card_id", COMPANION_CARDS)
def test_real_cards_fit_the_budget_with_every_optional_skill_stacked(card_id):
    card = CHARACTERS.load(card_id)
    ids = skill_ids_of(card) + [s for s in OPTIONAL_COMPANION_SKILLS if s not in skill_ids_of(card)]
    method = LIBRARY.compose(ids)

    from companion.roles.profile import from_card
    from dataclasses import replace
    profile = replace(from_card(card), method=method)
    plan = build_prompt_plan(profile, memory_block="x" * 800, persona_block="y" * 600)
    assert len(plan.system) <= PromptBudget().system_chars
    assert plan.dropped == (), f"{card_id}: 叠满 skill 后丢掉了 {plan.dropped}"


def test_always_loaded_layer_stays_small():
    # 常驻层每回合都付费（token 与首包延迟）。超过 1200 字就该先想想值不值得。
    assert len(LIBRARY.compose([])) <= 1200


# ---- 底线内容守卫 --------------------------------------------------------------

def test_companion_core_keeps_its_hard_lines():
    core = LIBRARY.load("companion-core").body
    for must in ("你是 AI", "不承诺保密", "不制造依赖", "暂停扮演"):
        assert must in core, f"companion-core 丢了底线：{must}"


def test_companion_core_does_not_hardcode_hotline_numbers():
    # 求助电话写错比不写更糟，且用户未必在中国。号码应由服务端按地区下发。
    import re
    assert not re.search(r"\d{3,}-?\d{4,}", LIBRARY.load("companion-core").body)


@pytest.mark.parametrize("skill_id", ["companion-core", "proactive-checkin"])
def test_guilt_phrases_only_appear_as_things_not_to_say(skill_id):
    body = LIBRARY.load(skill_id).body
    for line in body.splitlines():
        for phrase in GUILT_PHRASES:
            if phrase in line:
                # 出现的那一行必须是禁令（“不说”“不要”“制造”），不能是示范
                assert any(k in line for k in ("制造", "不要", "不说", "责怪", "施压")), \
                    f"{skill_id}: 「{phrase}」出现在非禁令语境：{line}"


def test_shared_activity_treats_activity_text_as_data_not_instructions():
    body = LIBRARY.load("shared-activity").body
    assert "不是指令" in body and "不大段引用歌词" in body
