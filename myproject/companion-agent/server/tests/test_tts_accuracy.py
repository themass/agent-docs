"""字错率：归一化、编辑距离、整批检查。"""

import pytest

from companion.app.voice.tts_accuracy import cer, check_rows, edit_distance, normalize, summarize, TurnCheck


def test_punctuation_width_case_and_emoji_do_not_count_as_errors():
    assert normalize("你好，World！😘 ABC") == normalize("你好world ａｂｃ")
    assert cer("先歇一会儿，我在。", "先歇一会儿我在").rate == 0.0


@pytest.mark.parametrize("a,b,d", [("", "", 0), ("abc", "", 3), ("", "abc", 3), ("kitten", "sitting", 3), ("你好", "你们好", 1)])
def test_edit_distance(a, b, d):
    assert edit_distance(a, b) == d


def test_a_wrong_character_is_one_error_in_the_reference_length():
    c = cer("今天天气很好", "今天天汽很好")
    assert (c.edits, c.length) == (1, 6) and round(c.rate, 3) == 0.167


def test_empty_reference_is_zero_only_if_nothing_was_heard():
    assert cer("，。", "").rate == 0.0 and cer("，。", "嗯").rate == 1.0


def test_summary_reports_mean_p90_and_worst_cases():
    checks = [TurnCheck(f"T{i}", "x", "y", c, False) for i, c in enumerate([0.0, 0.0, 0.1, 0.5])]
    s = summarize(checks, worst_n=2)
    assert s.count == 4 and round(s.mean_cer, 3) == 0.15 and s.p90_cer == 0.5
    assert [w.turn_id for w in s.worst] == ["T3", "T2"]
    assert summarize([]).count == 0


async def test_check_rows_skips_rows_without_audio_and_survives_bad_rows():
    rows = [{"turn_id": "A", "audio_out_key": "a.wav", "tts_text": ["你好。"], "interrupted": False},
            {"turn_id": "B", "audio_out_key": None, "tts_text": ["没有音频"]},
            {"turn_id": "C", "audio_out_key": "c.wav", "tts_text": ["会失败"]},
            {"turn_id": "D", "audio_out_key": "d.wav", "tts_text": ["被打断的整句"], "interrupted": True}]

    async def fetch(key):
        if key == "c.wav":
            raise RuntimeError("404")
        return key.encode()

    async def transcribe(data):
        return {"a.wav": "你好", "d.wav": "被打断"}[data.decode()]

    out = await check_rows(rows, fetch=fetch, transcribe=transcribe)
    assert [c.turn_id for c in out] == ["A", "D"]
    assert out[0].cer == 0.0 and out[1].interrupted and out[1].cer > 0     # 被打断的单独标出，调用方可以排除
