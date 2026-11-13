"""陪伴角色卡必须带 tagline。

客户端的角色选择页靠它画介绍；没有它客户端只能自己写死一份，两边很快就对不上
（真机上看到过：客户端写“温和、会记事的倾听者”，角色卡的性格是“直接、务实”）。
"""

import pytest

from companion.service.roles.files import CharacterSource
from companion.api.http.routers.characters import summarize
from companion.paths import CHARACTERS_DIR

SOURCE = CharacterSource(CHARACTERS_DIR)
CARD_IDS = sorted(p.name.removesuffix(".v2.json") for p in CHARACTERS_DIR.glob("*.v2.json"))


def test_there_are_cards_to_check():
    assert {"linche", "sudai"} <= set(CARD_IDS)


@pytest.mark.parametrize("card_id", CARD_IDS)
def test_every_card_has_a_short_tagline(card_id):
    tagline = summarize(card_id, SOURCE.load(card_id)).tagline
    assert tagline, f"{card_id}: tagline 为空，客户端会没有介绍可显示"
    assert 8 <= len(tagline) <= 30, f"{card_id}: tagline 应是一句话（8–30 字），实际 {len(tagline)}"


def test_client_fallback_text_matches_the_server_cards():
    # 客户端 AgentChatEntry.DefaultAgentRoles 里的离线兜底文案。改任何一边都要同步。
    client = {
        "linche": "直接务实的成长教练，帮你把想法落成行动",
        "sudai": "懂团队心理的组织心理学家，帮你看清说不清的事",
    }
    for card_id, text in client.items():
        assert summarize(card_id, SOURCE.load(card_id)).tagline == text
