import json

import pytest

from companion.adapters.memory.fake import InMemoryMemoryPort
from companion.app.memory.extraction import MemoryExtractor
from companion.ports.memory import MemoryKind
from companion.app.memory.extraction import MAX_ITEMS_PER_TURN, build_extraction_prompt, is_forbidden_content, parse_candidates


class RecordingLLM:
    """记录提示词，按脚本返回；脚本可以是异常，用来验证失败不外溢。"""

    def __init__(self, response):
        self.response = response
        self.prompts: list[str] = []

    async def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def dump(*entries):
    return json.dumps(list(entries), ensure_ascii=False)


# --- parse_candidates ----------------------------------------------------------


def test_parse_valid_json_keeps_fields_and_source():
    raw = dump(
        {"content": "用户住在杭州", "kind": "FACT"},
        {"content": "用户喜欢安静的音乐", "kind": "PREFERENCE"},
        {"content": "用户上周换了工作", "kind": "EVENT"},
    )
    items = parse_candidates(raw, source_character_id="xiaowu", source_message_id="m-7")
    assert [i.kind for i in items] == [
        MemoryKind.FACT,
        MemoryKind.PREFERENCE,
        MemoryKind.EVENT,
    ]
    assert all(i.source_character_id == "xiaowu" for i in items)
    assert all(i.source_message_id == "m-7" for i in items)
    assert len({i.id for i in items}) == 3


def test_parse_accepts_fenced_payload_with_chatter():
    raw = '好的，结果如下：\n```json\n[{"content": "用户是设计师"}]\n```\n希望有帮助。'
    items = parse_candidates(raw)
    assert [i.content for i in items] == ["用户是设计师"]
    assert items[0].kind is MemoryKind.FACT  # 缺 kind 时归为 FACT


def test_parse_accepts_wrapped_object_and_aliases():
    raw = json.dumps(
        {"memories": [{"memory": "用户爱喝美式", "type": "偏好"}, "用户养了两只猫"]},
        ensure_ascii=False,
    )  # type 不是我们的字段名；kind 缺失 → FACT；裸字符串也收
    items = parse_candidates(raw)
    assert [i.content for i in items] == ["用户爱喝美式", "用户养了两只猫"]
    assert [i.kind for i in items] == [MemoryKind.FACT, MemoryKind.FACT]


def test_parse_drops_malformed_entries_not_the_batch():
    raw = dump(
        {"content": "用户是左撇子"},
        {"kind": "FACT"},                      # 没有 content
        {"content": 42},                        # content 不是字符串
        {"content": "   "},                     # 空白
        {"content": "x"},                       # 太短
        ["不是对象"],
        None,
        {"content": "用户是左撇子"},            # 重复
        {"content": "用户会说日语"},
    )
    items = parse_candidates(raw)
    assert [i.content for i in items] == ["用户是左撇子", "用户会说日语"]


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "not json at all", "{}", "[]", '{"memories": null}', None],
)
def test_parse_returns_empty_on_unusable_payload(raw):
    assert parse_candidates(raw) == []


def test_parse_truncates_overlong_content():
    items = parse_candidates(dump({"content": "用户" + "很" * 500}))
    assert len(items) == 1
    assert len(items[0].content) <= 200


def test_parse_caps_item_count():
    names = "甲乙丙丁戊己庚辛壬癸子丑寅卯"
    raw = dump(*({"content": f"用户喜欢{ch}"} for ch in names))
    assert len(parse_candidates(raw)) == MAX_ITEMS_PER_TURN


# --- 禁止类别 ------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "用户的身份证号是 110101199003071234",
        "用户的银行卡是 6222 0212 3456 7890",
        "用户说密码是 hunter2",
        "用户收到了验证码 8891",
        "用户住在朝阳区建国路 88 号 3 单元 501",
        "用户被确诊为抑郁症",
        "用户长期服用降压药",
        "用户家地址是幸福小区 12 栋",
    ],
)
def test_forbidden_categories_are_rejected(text):
    assert is_forbidden_content(text) is True
    assert parse_candidates(dump({"content": text})) == []


@pytest.mark.parametrize(
    "text",
    ["用户养了一只猫", "用户喜欢下雨天", "用户是杭州人", "用户想学吉他"],
)
def test_ordinary_facts_are_kept(text):
    assert is_forbidden_content(text) is False
    assert len(parse_candidates(dump({"content": text}))) == 1


def test_prompt_lists_forbidden_categories_and_the_turn():
    prompt = build_extraction_prompt("我昨天去看了一场演出。", "听起来很棒！")
    assert "身份证" in prompt
    assert "银行卡" in prompt
    assert "密码" in prompt
    assert "精确住址" in prompt
    assert "诊断" in prompt
    assert "我昨天去看了一场演出。" in prompt
    assert "听起来很棒！" in prompt


# --- extractor 端到端 ----------------------------------------------------------


async def test_extractor_calls_llm_once_and_writes_through_port():
    llm = RecordingLLM(dump({"content": "用户每周三去攀岩", "kind": "EVENT"}))
    port = InMemoryMemoryPort()
    extractor = MemoryExtractor(port, llm)

    written = await extractor.extract(
        user_id="u1",
        character_id="xiaowu",
        message_id="m-42",
        user_message="我每周三都去攀岩。",
        assistant_reply="那你一定很厉害。",
    )

    assert len(llm.prompts) == 1
    assert "我每周三都去攀岩。" in llm.prompts[0]
    assert [i.content for i in written] == ["用户每周三去攀岩"]
    assert written[0].source_character_id == "xiaowu"
    assert written[0].source_message_id == "m-42"

    stored = await port.list_for_user("u1")
    assert [i.content for i in stored] == ["用户每周三去攀岩"]
    assert stored[0].id == written[0].id


async def test_extractor_writes_nothing_when_all_candidates_forbidden():
    llm = RecordingLLM(dump({"content": "用户的密码是 abc123"}))
    port = InMemoryMemoryPort()
    await MemoryExtractor(port, llm).extract(
        user_id="u1", character_id="c", message_id="m", user_message="我的密码是 abc123"
    )
    assert port.raw_count("u1") == 0


async def test_extractor_survives_llm_failure():
    port = InMemoryMemoryPort()
    extractor = MemoryExtractor(port, RecordingLLM(RuntimeError("gateway down")))
    assert (
        await extractor.extract(
            user_id="u1", character_id="c", message_id="m", user_message="你好"
        )
        == []
    )
    assert port.raw_count("u1") == 0


async def test_extractor_skips_empty_user_message_without_calling_llm():
    llm = RecordingLLM(dump({"content": "用户说过你好"}))
    extractor = MemoryExtractor(InMemoryMemoryPort(), llm)
    assert (
        await extractor.extract(
            user_id="u1", character_id="c", message_id="m", user_message="   "
        )
        == []
    )
    assert llm.prompts == []


async def test_extractor_keeps_user_isolation():
    llm = RecordingLLM(dump({"content": "用户爱看科幻"}))
    port = InMemoryMemoryPort()
    extractor = MemoryExtractor(port, llm)
    await extractor.extract(
        user_id="u1", character_id="c", message_id="m", user_message="我爱看科幻"
    )
    assert port.raw_count("u2") == 0
    assert len(await port.list_for_user("u1")) == 1


async def test_schedule_runs_in_background_and_drains():
    llm = RecordingLLM(dump({"content": "用户喜欢黑色"}))
    port = InMemoryMemoryPort()
    extractor = MemoryExtractor(port, llm)

    extractor.schedule(
        user_id="u1",
        character_id="afei",
        message_id="m-9",
        user_message="我喜欢黑色。",
        assistant_reply="记下了。",
    )
    await extractor.drain()

    stored = await port.list_for_user("u1")
    assert [i.content for i in stored] == ["用户喜欢黑色"]
    assert stored[0].source_character_id == "afei"


async def test_schedule_does_not_leak_exceptions():
    extractor = MemoryExtractor(InMemoryMemoryPort(), RecordingLLM(ValueError("bad")))
    extractor.schedule(
        user_id="u1", character_id="c", message_id="m", user_message="你好呀"
    )
    await extractor.drain()  # 不抛即通过
