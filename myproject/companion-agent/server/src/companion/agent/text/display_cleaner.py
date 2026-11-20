"""展示文本清洗：把模型输出里的 cue 协议片段剥成 say，供落库与文字气泡使用。

**为什么需要**（2026-11-20 用户报「文字消息里看到 say 字样」）：cue 片段只在语音
朗读那一跳被 ``TurnPipeline`` 剥掉，落库与推给文字端的却是原始模型输出——
``{"say":…,"cues":[…]}`` 原文进了气泡与历史；下一次文字回合的模型在线程历史里
看到自己写过协议 JSON，于是照抄。清洗放在回合落库/发布这一层（生产者侧），
语音回读走 ``message.delta`` 的 ``raw_delta`` 原文，cues 提取不受影响。

与 ``CueJsonGuard`` 的分工：守卫是**断句器前面**的一层，服务朗读——它把片段整段
交给下游、非片段正文攒给断句器按句切；这里的输出是**给用户看的气泡流**，
非片段正文必须当帧透传（聊天是流式的），片段则当场剥成 say。花括号配平与
「疑似片段前缀」的判定复用 json_guard，两处语义不会漂。

不认识的 ``{`` 形状（``{"port": 8081}``、markdown 代码块）原样保留；疑似片段但
坏掉/没闭合的**丢弃**，绝不回落成原文——与语音路径「畸形片段绝不朗读」同判。
"""

from __future__ import annotations

from companion.agent.protocol.fragment import try_parse_fragment
# 同包复用：花括号配平（跳过字符串与转义）是正确性关键，两处一份实现。
from companion.agent.text.json_guard import _safe_fragment, _scan_close, looks_like_fragment_start


class DisplayTextCleaner:
    """流式清洗：feed 返回此刻可以给用户看的文本；协议片段整段不进输出。"""

    def __init__(self, *, max_pending_chars: int = 4000) -> None:
        self._max_pending = max_pending_chars
        self._pending: str | None = None   # None = 不在片段缓存里
        self._discarding = False           # 超限后丢弃本轮余下内容，flush 复位
        self.fragments = 0                 # 成功剥出的片段数（回合收尾记日志用）
        self.dropped = 0                   # 坏片段被丢弃的个数

    def feed(self, chunk: str) -> str:
        if self._discarding:
            return ""
        out: list[str] = []
        buf = chunk
        while buf:
            if self._pending is None:
                brace = buf.find("{")
                if brace < 0:
                    out.append(buf)
                    break
                out.append(buf[:brace])
                rest = buf[brace:]
                if not looks_like_fragment_start(rest):
                    # 这个 `{` 是普通正文（配置、代码示例）：只吐 `{` 本身，
                    # 从下一位继续扫——同一块里后面的真片段还要认。
                    out.append("{")
                    buf = rest[1:]
                    continue
                self._pending = ""
                buf = rest
                continue
            probe = self._pending + buf
            end = _scan_close(probe)
            if end is None:
                if not looks_like_fragment_start(probe):
                    # 进来后才露馅（如 `{"port"`）：整段原样放行。
                    dumped, self._pending = probe, None
                    out.append(dumped)
                    break
                self._pending = probe
                if len(self._pending) > self._max_pending:
                    self._pending = None
                    self._discarding = True
                break
            complete, self._pending = probe[:end], None
            frag = try_parse_fragment(complete) if _safe_fragment(complete) else None
            if frag is None:
                self.dropped += 1
            else:
                self.fragments += 1
                out.append(frag.say)
            buf = probe[end:]         # 闭合后的尾巴（正文或下一段片段）继续走循环
        return "".join(out)

    def flush(self) -> str:
        """收尾：未闭合的片段直接丢弃，绝不把半截 `{"say":"` 还给用户。"""
        if self._pending is not None:
            self.dropped += 1
        self._pending = None
        self._discarding = False
        return ""
