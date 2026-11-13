"""回合追踪的纯逻辑：还原、去重、增量、超长、不同意时不留内容。不碰数据库。"""

import json

import pytest

from companion.agent.brain.trace_model import (
    CUT_MARK, HEAD_CHARS, MAX_MESSAGE_CHARS, TAIL_CHARS, LlmCall, build_trace, chunks, clip, read_trace,
    referenced_hashes, usage_of,
)

SYSTEM = "你是林澈。\n\n说话简短。\n\n不要说教。\n\n" + "\n\n".join(f"规则{i}：" + "x" * 80 for i in range(30))


def msg(role, content, **kw):
    return {"role": role, "content": content, **kw}


def call(seq, messages, output="", **kw):
    return LlmCall(seq=seq, input_messages=messages, output_text=output, **kw)


def roundtrip(calls, **kw):
    steps, blobs = build_trace(calls, keep_content=True, **kw)
    # 经过 JSON：真实存储就是 JSON，tuple/非字符串键之类的差异要在这里暴露
    return read_trace(json.loads(json.dumps(steps)), blobs), steps, blobs


def test_every_calls_input_is_restored_exactly_including_the_second_call_of_a_tool_loop():
    first = [msg("system", SYSTEM), msg("human", "周五面试")]
    asked = msg("ai", "", tool_calls=[{"id": "c1", "name": "add_event"}])
    second = first + [asked, msg("tool", "已添加", tool_call_id="c1", name="add_event")]
    got, steps, _ = roundtrip([call(0, first, tool_calls=[{"id": "c1", "name": "add_event", "args": {"t": "面试"}}]),
                               call(1, second, output="好的，记下了")])
    assert [m["content"] for m in got[0]["input"]] == [m["content"] for m in first]
    assert [(m["role"], m["content"]) for m in got[1]["input"]] == [(m["role"], m["content"]) for m in second]
    assert got[1]["input"][3]["tool_call_id"] == "c1" and got[1]["input"][3]["name"] == "add_event"
    assert got[1]["input"][2]["tool_calls"] == [{"id": "c1", "name": "add_event"}]
    assert got[1]["output"] == "好的，记下了"
    assert "base" in steps[0] and "append" in steps[1] and "base" not in steps[1]      # 第二次只存追加的部分


def test_the_second_call_stores_only_what_was_appended():
    first = [msg("system", SYSTEM), msg("human", "q")]
    second = first + [msg("ai", "a"), msg("tool", "t", tool_call_id="c")]
    _, steps, _ = roundtrip([call(0, first), call(1, second)])
    assert len(steps[1]["append"]) == 2 and len(steps[0]["base"]) == 2


def test_when_the_history_was_rewritten_between_calls_a_fresh_base_is_stored_not_a_wrong_append():
    first = [msg("system", SYSTEM), msg("human", "原来的话")]
    rewritten = [msg("system", SYSTEM), msg("human", "被中间件改写后的话"), msg("ai", "x")]
    got, steps, _ = roundtrip([call(0, first), call(1, rewritten)])
    assert "base" in steps[1]
    assert [m["content"] for m in got[1]["input"]] == [m["content"] for m in rewritten]


def test_identical_text_is_stored_once_across_calls_and_across_turns():
    a = [msg("system", SYSTEM), msg("human", "第一句")]
    b = [msg("system", SYSTEM + "\n\n【记得的】新增一条记忆"), msg("human", "第二句")]
    _, _, blobs_a = roundtrip([call(0, a)])
    _, _, blobs_b = roundtrip([call(0, b)])
    shared = set(blobs_a) & set(blobs_b)
    only_new = set(blobs_b) - set(blobs_a)
    assert len(shared) >= 30                             # 角色卡和规则的几十个段落全是同一份
    assert {blobs_b[h] for h in only_new} == {"【记得的】新增一条记忆", "第二句"}      # 只有变化的才是新增


def test_dedup_saves_most_of_the_bytes_over_a_realistic_conversation():
    history, turns, total_naive, stored = [], 25, 0, {}
    for i in range(turns):
        history += [msg("human", f"用户第{i}句，" + "话" * 60)]
        inputs = [msg("system", SYSTEM)] + history
        total_naive += sum(len(m["content"]) for m in inputs)
        _, _, blobs = roundtrip([call(0, inputs, output="回答" * 30)])
        stored.update(blobs)
        history += [msg("ai", f"助手第{i}句，" + "答" * 60)]
    kept = sum(len(v) for v in stored.values())
    assert kept < total_naive * 0.15, f"naive={total_naive} kept={kept}"


def test_without_consent_there_is_no_text_at_all_only_metrics_and_tool_names():
    steps, blobs = build_trace([call(0, [msg("system", SYSTEM), msg("human", "周五面试")], output="好的",
                                    reasoning_text="想一想", input_tokens=50, output_tokens=6, total_ms=400,
                                    tool_calls=[{"id": "c1", "name": "add_event", "args": {"title": "周五面试"}}])],
                               keep_content=False)
    assert blobs == {}
    s = steps[0]
    assert (s["in"], s["out"], s["ms"]) == (50, 6, 400)
    assert s["tools"] == [{"id": "c1", "name": "add_event"}]            # 工具名在，参数（带用户的话）不在
    assert not {"base", "append", "o", "th"} & set(s)
    assert "周五面试" not in json.dumps(steps, ensure_ascii=False)


def test_with_consent_tool_arguments_are_kept():
    steps, _ = build_trace([call(0, [msg("human", "x")], tool_calls=[{"id": "c", "name": "n", "args": {"a": 1}}])], keep_content=True)
    assert steps[0]["tools"] == [{"id": "c", "name": "n", "args": {"a": 1}}]


def test_an_oversized_message_keeps_head_and_tail_and_records_the_original_length():
    big = "头" * HEAD_CHARS + "中" * 50_000 + "尾" * TAIL_CHARS
    got, steps, blobs = roundtrip([call(0, [msg("human", big)])])
    text = got[0]["input"][0]["content"]
    assert text.startswith("头" * 100) and text.endswith("尾" * 100) and "中间省略" in text
    assert got[0]["input"][0]["truncated_from"] == len(big)
    assert len(text) < MAX_MESSAGE_CHARS + 100


def test_clip_leaves_a_message_at_the_limit_alone():
    assert clip("a" * MAX_MESSAGE_CHARS) == ("a" * MAX_MESSAGE_CHARS, None)
    assert clip("a" * (MAX_MESSAGE_CHARS + 1))[1] == MAX_MESSAGE_CHARS + 1


def test_chunking_is_stable_a_changed_paragraph_does_not_change_its_neighbours_hashes():
    base = "甲段\n\n乙段\n\n丙段"
    edited = "甲段\n\n乙段改了\n\n丙段"
    _, _, b1 = roundtrip([call(0, [msg("system", base)])])
    _, _, b2 = roundtrip([call(0, [msg("system", edited)])])
    assert set(b1) & set(b2) == {h for h, v in b1.items() if v in ("甲段", "丙段")}
    assert chunks("a\n\n\n\nb") == ["a", "", "b"]                 # 连续空行也能原样还原
    got, _, _ = roundtrip([call(0, [msg("system", "a\n\n\n\nb")])])
    assert got[0]["input"][0]["content"] == "a\n\n\n\nb"


def test_a_missing_blob_is_visible_not_silently_empty():
    steps, blobs = build_trace([call(0, [msg("human", "你好")], output="在")], keep_content=True)
    blobs.clear()
    got = read_trace(steps, blobs)
    assert "缺失文本块" in got[0]["input"][0]["content"] and "缺失文本块" in got[0]["output"]


def test_usage_adds_up_across_calls_and_attempts():
    steps, _ = build_trace([call(0, [msg("human", "a")], input_tokens=100, output_tokens=5, total_ms=400,
                                 tool_calls=[{"id": "c", "name": "n"}]),
                            call(1, [msg("human", "a")], input_tokens=140, output_tokens=20, cached_tokens=100, total_ms=900)],
                           keep_content=False)
    assert usage_of(steps) == {"calls": 2, "input_tokens": 240, "output_tokens": 25, "cached_tokens": 100,
                               "llm_ms": 1300, "tool_calls": 1}


def test_referenced_hashes_cover_inputs_outputs_and_reasoning():
    steps, blobs = build_trace([call(0, [msg("system", "S"), msg("human", "H")], output="O", reasoning_text="T")], keep_content=True)
    assert referenced_hashes(steps) == set(blobs)


def test_the_attempt_number_is_recorded_so_a_restarted_turn_can_be_told_apart():
    steps, _ = build_trace([call(0, [msg("human", "a")])], keep_content=False, attempt=1)
    assert steps[0]["a"] == 1


def test_a_step_without_content_never_shows_the_previous_steps_input():
    """读取的坑：没有正文的步骤沿用了上一步攒下的输入，会把别的步骤的输入当成它的。"""
    with_text, blobs = build_trace([call(0, [msg("system", "S"), msg("human", "第一次尝试的话")])], keep_content=True)
    without, _ = build_trace([call(0, [msg("human", "不该出现")])], keep_content=False, attempt=1)
    got = read_trace(with_text + without, blobs)
    assert [m["content"] for m in got[0]["input"]] == ["S", "第一次尝试的话"]
    assert got[1]["input"] == []
