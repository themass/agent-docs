"""增量 JSON 抽取 + 公式安全切块：把模型流出的解题 JSON 边流边拆成事件。

为什么要有这一层：solve 的模型输出是一个大 JSON 对象（SYSTEM_PROMPT 规定的形状），
SSE 却要按 question/step 粒度发增量。两条硬约束决定了这里的形状：

1. **步骤/公式边界是硬要求**——客户端 LaTeX 渲染不能切在公式中间。
   MathSafeChunker 把 `$…$` / `$$…$$` 整段扣住、到闭合才发出；step_end 再带
   整段校验后的内容供客户端对账。答案（finalAnswer）不做字段级增量，随 question
   闭合整块发出，天然满足同一条约束。
2. JSON 字符串值不能按原始字节切：`\\n`、`\\uXXXX`、`\\\\` 这些转义必须解码成
   整字符才能进事件，否则客户端拿到半截转义。解析器逐字符解码后再切块。

解析器只认 SolveResult 的键面；白名单外的键与值被静默消费（最终裁决交给
pydantic 的 extra="ignore"）。结构错误（控制字符、非法转义、非法标量）立即
抛 ValueError——调用方映射成既有的 50001，绝不把半截结构当好数据。
根对象闭合后 closed_root=True，其后的尾随内容（``` 围栏的尾巴）不再解析；
根对象开始前的内容（围栏头）同样被跳过——与全量端点接受的 ```json 围栏一致。

事件是 (name, data) 元组：帧编码在 api 层做（import-linter：service 不得依赖 api）。
"""

from __future__ import annotations

_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f",
            "n": "\n", "r": "\r", "t": "\t"}

# 需要在容器闭合时整段回看的字段（step_end 的整步校验、answer 的整块发出）。
_BUFFERED = {
    "question": ("finalAnswer", "finalAnswerLatex"),
    "step": ("text", "latex"),
}

# 发字段级增量的 (容器 kind, 字段名) → 事件名。latex 与 text 共用 step_delta，
# 用 field 区分：客户端两个字段渲染在不同位置，切块各自独立。
_SINKS = {
    ("question", "thinking"): "thinking_delta",
    ("question", "text"): "question_text_delta",
    ("step", "text"): "step_delta",
    ("step", "latex"): "step_delta",
}


class MathSafeChunker:
    """把解码后的字符串增量重切成「永不切进公式」的片段。

    状态：0 普通文本 / 1 行内 `$…$` / 2 展示 `$$…$$`。`$` 要看到下一个字符才能
    判定（行内还是展示、开还是闭），判不定的尾巴留在缓冲里；公式一旦开始，
    整段扣到闭合才发。字段闭合时 flush 整段收尾——那时整串已解码完，客户端
    拿到的是完整值，切哪都安全。

    绝对下标（`_base`/`_start`）是必须的：逐 token 喂时公式经常跨 feed 闭合，
    早先按「本次 feed 的局部下标」记账的版本在逐字符喂时把定界符吞掉了——
    单测里逐字符切 `得 $2$ 完了` 抓到过。缓冲 `_buf` 在公式态下永远从定界符
    起留存，`_scan` 记住已扫过的位置（公式内部不会发东西，重扫无副作用）。
    """

    def __init__(self) -> None:
        self._buf = ""       # 未发出的原文（公式态下从定界符起）
        self._base = 0       # _buf[0] 在整条逻辑串上的绝对下标
        self._start = 0      # 进行中公式定界符的绝对下标
        self._scan = 0       # 公式态：已扫到的绝对下标（下次从这里续扫）
        self._state = 0

    def feed(self, decoded: str) -> str:
        text = self._buf + decoded
        base = self._base
        out: list[str] = []
        n = len(text)
        i = self._scan - base if self._state else 0
        while i < n:
            if self._state == 0:
                c = text[i]
                if c == "\\":
                    if i + 1 >= n:
                        break  # 反斜杠悬在块尾：`\$` 不启动公式，得看下一个字符
                    out.append(text[i:i + 2])
                    i += 2
                    continue
                if c == "$":
                    if i + 1 >= n:
                        break  # `$` 还是 `$$`、开还是闭，得看下一个字符
                    if text[i + 1] == "$":
                        self._state, self._start, i = 2, base + i, i + 2
                    else:
                        self._state, self._start, i = 1, base + i, i + 1
                    continue
                out.append(c)
                i += 1
                continue
            c = text[i]
            if c == "\\":
                if i + 1 >= n:
                    break
                i += 2  # `\$` 这类成对构造：不是闭合符
                continue
            if c == "$":
                if self._state == 1:
                    out.append(text[self._start - base:i + 1])
                    self._state, i = 0, i + 1
                    continue
                if i + 1 >= n:
                    break  # 块尾的 `$`：闭合还是 `$$` 的一部分，得看下一个字符
                if text[i + 1] == "$":
                    out.append(text[self._start - base:i + 2])
                    self._state, i = 0, i + 2
                    continue
                i += 1  # 展示公式里的孤 `$`：普通字符
                continue
            i += 1
        if self._state:
            self._scan = base + i
            self._buf = text[self._start - base:]
            self._base = self._start
        else:
            self._scan = 0
            self._buf = text[i:]
            self._base = base + i
        return "".join(out)

    def flush(self) -> str:
        out, self._buf = self._buf, ""
        self._base = 0
        self._start = 0
        self._scan = 0
        self._state = 0
        return out


class SolveStreamParser:
    """流式读取 SolveResult 形状的 JSON；feed() 返回要发的事件列表。

    客户端按 questionIndex/stepIndex（数组下标，0 起）累积，以 step_end 与
    done 对账：
    - meta：questionFound 落地时发一次，让客户端尽早决定继续渲染还是收尾
    - thinking_delta / question_text_delta：题内字段的增量（{questionIndex, text}）
    - step_start {questionIndex, stepIndex}
    - step_delta {questionIndex, stepIndex, field: text|latex, text}
    - step_end {questionIndex, stepIndex, step:{index,text,latex}}；结构不合法时
      改带 valid:false——客户端据此丢弃这个块，但不中断流（最终成败由 done/error 裁决）
    - answer {questionIndex, finalAnswer, finalAnswerLatex}：question 闭合时整块发出

    注意 step 的展示序号用 step.index（模型给的 1 起），对账用 stepIndex（位置）。
    """

    def __init__(self) -> None:
        self.stack: list[dict] = []
        self.started = False
        self.closed_root = False
        self._string: dict | None = None
        self._escape = False
        self._literal = ""

    # ---- 主循环 ----

    def feed(self, text: str) -> list[tuple[str, dict]]:
        events: list[tuple[str, dict]] = []
        for ch in text:
            if self.closed_root:
                break
            if self._string is not None:
                events.extend(self._string_char(ch))
            elif self._literal:
                if ch in " \t\r\n,}]":
                    events.extend(self._end_literal())
                    events.extend(self._structural(ch))
                else:
                    self._literal += ch
            else:
                events.extend(self._structural(ch))
        return events

    # ---- 结构层 ----

    def _structural(self, ch: str) -> list[tuple[str, dict]]:
        if not self.started:
            # 第一个 `{` 之前的一切都被跳过（```json 围栏头、模型的前置废话）。
            # 全量端点本来就吃围栏，这里必须同样吃：否则同一个输出流式红、全量绿。
            if ch == "{":
                self.stack.append(self._frame("root"))
                self.started = True
            return []
        if ch in " \t\r\n":
            return []
        if ch == "{":
            return self._open_obj()
        if ch == "[":
            self._open_arr()
            return []
        if ch in "}]":
            return self._close()
        if ch == '"':
            self._begin_string()
            return []
        if ch == ":":
            if self.stack:
                self.stack[-1]["expect"] = "value"
            return []
        if ch == ",":
            if self.stack:
                self.stack[-1]["expect"] = "key"
            return []
        if ch in '-0123456789tfn':
            self._literal = ch
            return []
        raise ValueError(f"unexpected character {ch!r} in model output")

    def _frame(self, kind: str, **extra) -> dict:
        frame = {"kind": kind, "is_list": kind in ("questions", "steps"),
                 "key": None, "expect": "key", "index": 0,
                 "buffers": {}, "values": {}}
        frame.update(extra)
        return frame

    def _open_obj(self) -> list[tuple[str, dict]]:
        parent = self.stack[-1] if self.stack else None
        events: list[tuple[str, dict]] = []
        if parent is not None and parent["kind"] == "questions":
            frame = self._frame("question", qi=parent["index"])
        elif parent is not None and parent["kind"] == "steps":
            frame = self._frame("step", qi=parent["qi"], si=parent["index"])
            events.append(("step_start", {"questionIndex": frame["qi"],
                                          "stepIndex": frame["si"]}))
        else:
            frame = self._frame("other")
        self.stack.append(frame)
        return events

    def _open_arr(self) -> None:
        parent = self.stack[-1] if self.stack else None
        if parent is not None and parent["kind"] == "root" and parent["key"] == "questions":
            self.stack.append(self._frame("questions"))
        elif parent is not None and parent["kind"] == "question" and parent["key"] == "steps":
            self.stack.append(self._frame("steps", qi=parent["qi"]))
        else:
            self.stack.append(self._frame("other"))

    def _close(self) -> list[tuple[str, dict]]:
        frame = self.stack.pop()
        events: list[tuple[str, dict]] = []
        if frame["kind"] == "root":
            self.closed_root = True
            return events
        if frame["kind"] == "step":
            step = {"index": frame["values"].get("index"),
                    "text": "".join(frame["buffers"].get("text", [])),
                    "latex": "".join(frame["buffers"].get("latex", []))}
            index = step["index"]
            ok = (isinstance(index, int) and not isinstance(index, bool) and index >= 1
                  and step["text"].strip() and len(step["text"]) <= 20000
                  and len(step["latex"]) <= 20000)
            data = {"questionIndex": frame["qi"], "stepIndex": frame["si"]}
            if ok:
                data["step"] = step
            else:
                data["valid"] = False
            events.append(("step_end", data))
        elif frame["kind"] == "question":
            final = "".join(frame["buffers"].get("finalAnswer", []))
            if final:
                events.append(("answer", {
                    "questionIndex": frame["qi"],
                    "finalAnswer": final,
                    "finalAnswerLatex": "".join(frame["buffers"].get("finalAnswerLatex", [])),
                }))
        self._value_done()
        return events

    def _value_done(self) -> None:
        top = self.stack[-1] if self.stack else None
        if top is None:
            return
        if top["is_list"]:
            top["index"] += 1
        else:
            top["key"] = None

    # ---- 字符串层（逐字符解码转义）----

    def _begin_string(self) -> None:
        top = self.stack[-1] if self.stack else None
        if top is None:
            raise ValueError("string outside root object")
        if not top["is_list"] and top["expect"] == "key":
            self._string = {"role": "key", "owner": top}
            return
        event = _SINKS.get((top["kind"], top["key"]))
        base: dict | None = None
        if event is not None:
            base = {"questionIndex": top.get("qi", 0)}
            if top["kind"] == "step":
                base["stepIndex"] = top["si"]
                base["field"] = top["key"]
        self._string = {"role": "value", "owner": top, "event": event,
                        "base": base, "chunker": MathSafeChunker()}

    def _string_char(self, ch: str) -> list[tuple[str, dict]]:
        ctx = self._string
        if ctx.get("unicode") is not None:
            ctx["unicode"] += ch
            if len(ctx["unicode"]) < 4:
                return []
            try:
                code = int(ctx["unicode"], 16)
            except ValueError:
                raise ValueError("invalid \\u escape in string") from None
            ctx["unicode"] = None
            return self._emit_decoded(chr(code))
        if self._escape:
            self._escape = False
            if ch in _ESCAPES:
                return self._emit_decoded(_ESCAPES[ch])
            if ch == "u":
                ctx["unicode"] = ""
                return []
            raise ValueError("invalid escape in string")
        if ch == "\\":
            self._escape = True
            return []
        if ch == '"':
            self._string = None
            return self._end_string(ctx)
        if ord(ch) < 0x20:
            raise ValueError("control character in string")
        return self._emit_decoded(ch)

    def _emit_decoded(self, ch: str) -> list[tuple[str, dict]]:
        ctx = self._string
        owner = ctx["owner"]
        if ctx["role"] == "key":
            owner.setdefault("keybuf", []).append(ch)
            return []
        key = owner.get("key")
        if key in _BUFFERED.get(owner["kind"], ()):
            owner["buffers"].setdefault(key, []).append(ch)
        if ctx["event"] is None:
            return []
        piece = ctx["chunker"].feed(ch)
        if not piece:
            return []
        data = dict(ctx["base"])
        data["text"] = piece
        return [(ctx["event"], data)]

    def _end_string(self, ctx: dict) -> list[tuple[str, dict]]:
        if ctx["role"] == "key":
            owner = ctx["owner"]
            owner["key"] = "".join(owner.pop("keybuf", []))
            return []
        events: list[tuple[str, dict]] = []
        if ctx["event"] is not None:
            rest = ctx["chunker"].flush()
            if rest:
                data = dict(ctx["base"])
                data["text"] = rest
                events.append((ctx["event"], data))
        self._value_done()
        return events

    # ---- 标量层 ----

    def _end_literal(self) -> list[tuple[str, dict]]:
        raw = self._literal
        self._literal = ""
        if raw in ("true", "false"):
            value: object = raw == "true"
        elif raw == "null":
            value = None
        else:
            try:
                value = int(raw)
            except ValueError:
                try:
                    value = float(raw)
                except ValueError:
                    raise ValueError(f"invalid literal {raw!r}") from None
        events: list[tuple[str, dict]] = []
        top = self.stack[-1] if self.stack else None
        if top is not None:
            key = top.get("key")
            if top["kind"] == "root" and key == "questionFound" and isinstance(value, bool):
                events.append(("meta", {"questionFound": value}))
            elif top["kind"] in ("question", "step") and key:
                top["values"][key] = value
        self._value_done()
        return events
