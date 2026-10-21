"""The dictation split: does it keep every word, and does it put bullets in free slots."""

from __future__ import annotations

import pytest

from jc.schemas.intake import IntakeSplitRequest
from jc.schemas.profile_payload import ProfileExperience, ProfilePayload
from jc.services.intake_dictation import split_dictation
from jc.services.intake_service import IntakeService
from jc.services.profile_intake import highlight_slot_ids, parse_highlight_target

_PARAGRAPH = (
    "我在某某科技负责订单中心的重构。原来的系统是单体，QPS 到 3000 就开始超时。"
    "我带了 4 个人拆成了 6 个服务，P99 从 800ms 降到 120ms。后来又做了灰度发布的能力。"
)


def _content(text: str) -> str:
    """Everything that is not punctuation or whitespace — the part a split may not lose."""
    drop = set(" \t\n　，。、；：！？（）()[]【】·—–-_/\\,.;:!?\"'`*•①②③④⑤⑥⑦⑧⑨⑩")
    return "".join(ch for ch in text if ch not in drop)


def test_a_split_never_loses_or_invents_content() -> None:
    """The invariant that makes this safe to run by default on the user's own words."""
    joined = "".join(split_dictation(_PARAGRAPH))
    assert _content(joined) == _content(_PARAGRAPH)


def test_each_sentence_becomes_its_own_point() -> None:
    segments = split_dictation(_PARAGRAPH)
    assert len(segments) == 4
    assert segments[0].startswith("我在某某科技")
    assert "P99 从 800ms 降到 120ms" in segments[2]


def test_a_decimal_is_not_read_as_a_list_marker() -> None:
    """`1.5 倍` must stay a figure. Stripping `1.` here would delete the number."""
    assert split_dictation("1.5 倍的吞吐提升") == ("1.5 倍的吞吐提升",)


def test_a_users_own_list_markers_are_the_boundaries() -> None:
    segments = split_dictation("- 带了 4 个人\n- 拆了 6 个服务\n2. 做了灰度发布")
    assert segments == ("带了 4 个人", "拆了 6 个服务", "做了灰度发布")


def test_a_short_trailing_sentence_stays_with_the_point_it_belongs_to() -> None:
    """「效果不错。」 is not a bullet; as its own line it would read as filler."""
    segments = split_dictation(
        "我带了 4 个人把订单中心拆成了 6 个服务，P99 从 800ms 降到 120ms。效果不错。"
    )
    assert len(segments) == 1
    assert segments[0].endswith("效果不错。")


def test_one_sentence_comes_back_as_one_segment_not_as_nothing() -> None:
    """Callers treat "nothing to split" as the ordinary case, so it must not be empty."""
    assert split_dictation("负责订单中心的重构") == ("负责订单中心的重构",)
    assert split_dictation("   ") == ()


def test_a_long_dictation_is_capped_without_dropping_the_tail() -> None:
    """A cap that discarded segments would break the preservation invariant."""
    text = "".join(f"第 {i} 件事是把某个服务的延迟降下来了。" for i in range(1, 13))
    segments = split_dictation(text)
    assert len(segments) == 8
    assert _content("".join(segments)) == _content(text)
    assert "第 12 件事" in segments[-1]


def test_commas_do_not_split_one_thought_into_fragments() -> None:
    text = "负责订单中心，顺便把发布流程也接了过来，整体耗时下降了一半"
    assert split_dictation(text) == (text,)


def test_slot_ids_round_trip() -> None:
    """The plan's question id and the split's target path come from one rule."""
    question_id, path = highlight_slot_ids(1, 2)
    assert question_id == "role.1.highlight.2"
    assert parse_highlight_target(path) == (1, 2)
    assert parse_highlight_target("contact.name") is None
    assert parse_highlight_target("experiences[0].scope") is None


class _StubProfiles:
    """Stands in for `ProfileService.get`: the split is read-only, so nothing else is used."""

    def __init__(self, payload: ProfilePayload) -> None:
        self._payload = payload

    async def get(self, profile_id: str, *, actor: object):  # noqa: ANN401 - test stub
        class _Resp:
            payload = self._payload
            version = 3

        return _Resp()


def _service(payload: ProfilePayload) -> IntakeService:
    service = IntakeService.__new__(IntakeService)
    service._profiles = _StubProfiles(payload)  # type: ignore[attr-defined]
    return service


def _profile_with_one_highlight() -> ProfilePayload:
    return ProfilePayload(
        experiences=[
            ProfileExperience(
                id="exp1",
                company="某某科技",
                title="后端技术专家",
                start_date="2021-03",
                highlights=["负责订单中心的稳定性"],
            )
        ]
    )


@pytest.mark.asyncio
async def test_split_assigns_consecutive_free_slots_and_never_displaces_a_bullet() -> None:
    """The question targets the first unfilled slot, so the following ones are free.

    Reusing slot 1 for all segments would overwrite the same bullet four times and the
    user would see one point survive out of four.
    """
    payload = _profile_with_one_highlight()
    res = await _service(payload).split_answer(
        "prof_1",
        actor=object(),
        body=IntakeSplitRequest(
            question_id="role.0.highlight.1",
            target_path="experiences[0].highlights[1]",
            answer=_PARAGRAPH,
        ),
    )
    assert res.split
    assert [s.target_path for s in res.segments] == [
        "experiences[0].highlights[1]",
        "experiences[0].highlights[2]",
        "experiences[0].highlights[3]",
        "experiences[0].highlights[4]",
    ]
    assert payload.experiences[0].highlights == ["负责订单中心的稳定性"], "preview must not write"


@pytest.mark.asyncio
async def test_every_segment_carries_a_label_the_user_can_check() -> None:
    """A confirmation reading `experiences[0].highlights[2]` is not a confirmation."""
    res = await _service(_profile_with_one_highlight()).split_answer(
        "prof_1",
        actor=object(),
        body=IntakeSplitRequest(
            question_id="role.0.highlight.1",
            target_path="experiences[0].highlights[1]",
            answer=_PARAGRAPH,
        ),
    )
    assert [s.question_id for s in res.segments] == [
        "role.0.highlight.1",
        "role.0.highlight.2",
        "role.0.highlight.3",
        "role.0.highlight.4",
    ], "each segment must answer the slot it fills, or the plan re-asks for it"
    labels = [s.label for s in res.segments]
    assert labels[0] == "某某科技 · 后端技术专家 · 第 2 条成果"
    assert all("experiences[" not in label for label in labels)


@pytest.mark.asyncio
async def test_a_single_field_question_is_never_fanned_out() -> None:
    """A name is one field. Splitting it would produce segments with nowhere to land."""
    res = await _service(_profile_with_one_highlight()).split_answer(
        "prof_1",
        actor=object(),
        body=IntakeSplitRequest(
            question_id="identity.name",
            target_path="contact.name",
            answer="张三。联系我：z@example.com。随时可以聊。",
        ),
    )
    assert not res.split
    assert len(res.segments) == 1
    assert res.segments[0].target_path == "contact.name"


@pytest.mark.asyncio
async def test_one_point_reports_no_split_so_the_ui_stays_quiet() -> None:
    res = await _service(_profile_with_one_highlight()).split_answer(
        "prof_1",
        actor=object(),
        body=IntakeSplitRequest(
            question_id="role.0.highlight.1",
            target_path="experiences[0].highlights[1]",
            answer="把订单中心的 P99 从 800ms 降到了 120ms",
        ),
    )
    assert not res.split
    assert len(res.segments) == 1
