"""流式 JSON 抽取与公式安全切块的单元测试（不碰 HTTP 与模型）。

核心不变量（硬要求的机器化）：
- 任意切块尺寸下，delta 拼接 == 原字段值；
- 公式段 `$…$` / `$$…$$` 永远整块出现在同一个 delta 里（不切在公式中间）；
- 转义（`\\n`、`\\uXXXX`）解码成整字符后才进事件。
"""

import json
import re

import pytest

from companion.service.photosolve_stream import MathSafeChunker, SolveStreamParser

MATH = "$1+1=2$"
MIXED = "先化简 $\\frac{1}{2}$ 得 $$x=3$$ 完毕"
DISPLAY = "$$\\int_0^1 x\\,dx=\\tfrac12$$"

UNESCAPED_DOLLAR = re.compile(r"(?<!\\)\$")


def feed_all(text: str, size: int) -> list[str]:
    chunker = MathSafeChunker()
    out = [chunker.feed(text[i:i + size]) for i in range(0, len(text), size)]
    out.append(chunker.flush())
    return [p for p in out if p]


@pytest.mark.parametrize("text", [MATH, MIXED, DISPLAY, "$$", "a \\$ b", "普通文本", ""])
@pytest.mark.parametrize("size", [1, 2, 3, 5, 7, 11, 1000])
def test_reassembly_is_lossless(text, size):
    assert "".join(feed_all(text, size)) == text


@pytest.mark.parametrize("text", [MATH, MIXED, DISPLAY])
@pytest.mark.parametrize("size", [1, 2, 3, 5, 7, 11])
def test_math_spans_are_never_split(text, size):
    """每个发出的片段里，未转义的 `$` 必成对——公式不可能被切在半开状态。"""
    for piece in feed_all(text, size):
        assert len(UNESCAPED_DOLLAR.findall(piece)) % 2 == 0, piece


def test_single_formula_emits_as_one_piece():
    assert feed_all(MATH, 1) == [MATH]


def test_escaped_dollar_does_not_open_math():
    # `\$` 是普通字符：两侧文本可以各自成块，不能被扣进"公式"。
    pieces = feed_all("a \\$ b", 1)
    assert "".join(pieces) == "a \\$ b"
    assert all(len(UNESCAPED_DOLLAR.findall(p)) % 2 == 0 for p in pieces)


# ---- 解析器：端到端事件序列 ----

PAYLOAD = {
    "questionFound": True,
    "questions": [
        {"index": 1, "text": "1+1=?", "latex": "", "thinking": "先看题",
         "steps": [{"index": 1, "text": "相加 $1+1$", "latex": "$1+1=2$"},
                   {"index": 2, "text": "得 $2$", "latex": ""}],
         "finalAnswer": "2", "finalAnswerLatex": "$2$", "confidence": 0.99},
        {"index": 2, "text": "2+2=?", "steps": [], "finalAnswer": "4"},
    ],
}


def parse_all(raw: str, size: int) -> tuple[list[tuple[str, dict]], SolveStreamParser]:
    parser = SolveStreamParser()
    events: list[tuple[str, dict]] = []
    for i in range(0, len(raw), size):
        events.extend(parser.feed(raw[i:i + size]))
    return events, parser


@pytest.mark.parametrize("size", [1, 2, 3, 7, 13, 64, 10_000])
def test_parser_closes_root_at_every_chunk_size(size):
    import json
    raw = json.dumps(PAYLOAD, ensure_ascii=False)
    events, parser = parse_all(raw, size)
    assert parser.closed_root and not parser.stack


@pytest.mark.parametrize("size", [1, 3, 17])
def test_parser_deltas_rebuild_field_values(size):
    import json
    events, _ = parse_all(json.dumps(PAYLOAD, ensure_ascii=False), size)
    rebuilt: dict[tuple, str] = {}
    for name, data in events:
        if name == "step_delta":
            key = ("step", data["questionIndex"], data["stepIndex"], data["field"])
        elif name in ("thinking_delta", "question_text_delta"):
            key = (name, data["questionIndex"])
        else:
            continue
        rebuilt[key] = rebuilt.get(key, "") + data["text"]
    q0, q1 = PAYLOAD["questions"][0], PAYLOAD["questions"][1]
    assert rebuilt[("thinking_delta", 0)] == "先看题"
    assert rebuilt[("question_text_delta", 0)] == "1+1=?"
    assert rebuilt[("step", 0, 0, "text")] == "相加 $1+1$"
    assert rebuilt[("step", 0, 0, "latex")] == "$1+1=2$"
    assert rebuilt[("step", 0, 1, "text")] == "得 $2$"
    # 第二题没有 thinking/latex：不能冒出空事件
    assert ("thinking_delta", 1) not in rebuilt


def test_parser_sequence_shape_and_fences():
    """事件顺序 + ```json 围栏前后缀都被吃下；done 之前 answer 已发。"""
    import json
    raw = "```json\n" + json.dumps(PAYLOAD, ensure_ascii=False) + "\n```"
    events, parser = parse_all(raw, 4)
    assert parser.closed_root
    names = [n for n, _ in events]
    assert names[0] == "meta"
    assert names.index("step_start") < names.index("step_delta") < names.index("step_end")
    # 每题一个 answer；每题的 steps 数量对得上
    assert names.count("answer") == 2
    assert [d for n, d in events if n == "step_start"] == [
        {"questionIndex": 0, "stepIndex": 0}, {"questionIndex": 0, "stepIndex": 1}]
    ends = [d for n, d in events if n == "step_end"]
    assert ends[0]["step"] == {"index": 1, "text": "相加 $1+1$", "latex": "$1+1=2$"}
    answers = [d for n, d in events if n == "answer"]
    assert answers[0] == {"questionIndex": 0, "finalAnswer": "2", "finalAnswerLatex": "$2$"}
    assert answers[1] == {"questionIndex": 1, "finalAnswer": "4", "finalAnswerLatex": ""}
    assert names[-1] != "done"  # done 由 service 在全量校验后发，parser 只到 answer


def test_parser_meta_question_found_false():
    events, parser = parse_all('{"questionFound": false, "questions": []}', 3)
    assert events == [("meta", {"questionFound": False})]
    assert parser.closed_root


def test_parser_escapes_decode_to_characters():
    # 手写 JSON 源串（不经 json.dumps——它会再转义一层）：直接考解析器对
    # \"、\n、\uXXXX 的解码：解码成整字符后才进 delta。
    raw = ('{"questionFound": true, "questions": [{"index": 1, '
           '"text": "含\\"引号\\"和\\n换行与\\u6c49字", "steps": [], "finalAnswer": "ok"}]}')
    events, _ = parse_all(raw, 1)
    texts = [d["text"] for n, d in events if n == "question_text_delta"]
    assert "".join(texts) == '含"引号"和\n换行与汉字'


def test_parser_rejects_control_char_and_bad_escape():
    for raw in ['{"questionFound": true, "questions": [{"index": 1, "text": "a\x01b"',
                '{"questionFound": true, "questions": [{"index": 1, "text": "a\\qb"']:
        parser = SolveStreamParser()
        with pytest.raises(ValueError):
            parser.feed(raw)


def test_parser_marks_invalid_step_not_valid():
    """结构坏掉的 step 不中断流：step_end 带 valid:false，让客户端丢弃这个块。"""
    raw = ('{"questionFound": true, "questions": [{"index": 1, "text": "q", '
           '"steps": [{"index": 0, "text": "x"}], "finalAnswer": "a"}]}')
    events, parser = parse_all(raw, 5)
    end = next(d for n, d in events if n == "step_end")
    assert end["valid"] is False and parser.closed_root
