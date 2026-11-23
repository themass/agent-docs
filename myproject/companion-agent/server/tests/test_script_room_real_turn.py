"""``mode: real_turn`` 的离线回归：envelope 走真实 topic、v2 门禁、附件并入同一条消息。

不连 LiveKit、不连库、不调模型——房间用一对互相路由的 ``MemoryRtcAdapter`` 假装，
回合层用 ``test_platform_brain`` 那套假 submit/假 control。

这覆盖的不是「模型看得懂图」（那要真模型，见 ``cases/voice/image_reply.yaml`` 的实跑记录），
而是**接线**：一旦下面任何一条坏掉，实跑会以一种很难读的方式红——

1. ``control.hello`` 谈不成 v2：``speech.seg`` 会被 ``publish`` 安静丢弃，只多几条 unsent 计数；
2. ``control.input`` 的 ``kind`` / ``upload_ids`` / ``client_msg_id`` 键名写错：图静默不进槽，
   回合变成纯文本，关键词断言红得像「模型没看懂」；
3. 发文字早于附件进槽：同样的假红（这条由 ``SLOT_SETTLE`` 那段压住，见 real_turn 的注释）。
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from companion.agent.protocol import TOPIC_IN, decode
from companion.agent.protocol.catalog import TOPIC_CTL, TOPIC_CUE
from companion.devtools.script_room.case_schema import load_case
from companion.devtools.script_room.real_turn import (
    RealTurnError,
    _data_handler,
    keyword_hits,
    negative_control_problems,
    run_real_turn,
    vacuous_family_members,
)
from companion.devtools.script_room.rtc import MemoryRtcAdapter
from companion.service.turn.queue import Disposition

TURN = "01TURNSCRIPTAAAAAAAAAAAA"


# --------------------------------------------------------------------- 替身


class _PairedAdapter(MemoryRtcAdapter):
    """``MemoryRtcAdapter`` + 把它 publish 的东西路由给对端。

    只加路由，不改记录语义（``published`` 照旧），所以断言仍然能直接看「谁发出了什么」。
    ``peer_kind`` 是**自己**在对方眼里的参与者类型：用户侧必须是 STANDARD，否则
    ``ProtocolBridge`` 的身份白名单会把它的输入整条丢掉。
    """

    def __init__(self, *, name: str, kind: str) -> None:
        super().__init__()
        self.name = name
        self.kind = kind
        self.peer: "_PairedAdapter | None" = None

    async def connect(self, url: str, token: str) -> None:
        await super().connect(url, token)
        if self.peer is not None:
            self.peer.simulate_remote_join()   # 对端要看见「有人进房了」

    async def publish_data(self, topic: str, payload: bytes) -> None:
        await super().publish_data(topic, payload)
        if self.peer is not None:
            await self.peer.simulate_data(payload, topic=topic,
                                          publisher_identity=f"{self.name}-1",
                                          publisher_kind=self.kind)

    async def send_text(self, topic: str, text: str) -> None:
        await super().send_text(topic, text)
        if self.peer is not None:
            await self.peer.simulate_text(text, participant_identity=f"{self.name}-1")


class _Control:
    """只实现 ``PlatformBrain`` 用到的事件流部分（同 tests/test_platform_brain.py）。"""

    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict]] = []

    def add(self, name: str, **data) -> None:
        self.events.append((f"{len(self.events) + 1}-0", name, data))

    async def tail_event_id(self, *, session_id: int) -> str:
        return self.events[-1][0] if self.events else "0-0"

    async def wait_events(self, *, session_id: int, after_id: str, block_ms: int):
        after = int(after_id.split("-")[0])
        found = [e for e in self.events if int(e[0].split("-")[0]) > after]
        if not found:
            await asyncio.sleep(0.01)
        return found

    async def send_cancel(self, *, turn_id: str) -> None:
        return None


class _Submit:
    """假 submit：记 kwargs，并按脚本往事件流里放回合事件（模拟 TurnRunner）。

    ``attachments`` 那一项是本文件的**承重断言**：端侧那条带图消息在图这一路是
    ``control.input``、在文字这一路是 ``lk.chat``，只有在这里才合成一条消息。
    """

    def __init__(self, control: _Control, *, reply_lines: tuple[str, ...]) -> None:
        self.control = control
        self.reply_lines = reply_lines
        self.calls: list[dict] = []

    async def submit(self, **kw):
        self.calls.append(kw)
        # 真实 PlatformBrain 传的键是 client_message_id（恒为 None），消息 id 由 submit 侧生成
        self.control.add("turn.started", turn_id=TURN, user_message_ids=[11])
        for line in self.reply_lines:
            self.control.add("message.delta", turn_id=TURN, raw_delta=line)
        self.control.add("message.done", turn_id=TURN, assistant_message_id=12)
        return SimpleNamespace(status="accepted", disposition=Disposition.STARTED,
                               message_id=11, turn_id=TURN, reason=None)


class _Platform:
    def __init__(self, *, reply_lines: tuple[str, ...]) -> None:
        control = _Control()
        submit = _Submit(control, reply_lines=reply_lines)
        self._control = control
        self._submit = submit
        self.chat = SimpleNamespace(
            control=control,
            submit=submit,
            sessions=SimpleNamespace(create=self._create_session),
            messages=SimpleNamespace(list_before=self._list_before),
        )
        self.uploads = SimpleNamespace(accept=self._accept)
        self._next_session = 41
        self.upload: SimpleNamespace | None = None
        self.reply_lines = reply_lines

    async def _create_session(self, **kwargs):
        self._next_session += 1
        self.session_kwargs = kwargs
        return SimpleNamespace(id=self._next_session)

    async def _accept(self, *, owner_id: int, data: bytes):
        self.upload = SimpleNamespace(id="01UPLSCRIPT0000000000000",
                                      object_key=f"companion-qa/uploads/{owner_id}/x.jpg",
                                      size=len(data))
        return self.upload

    async def _list_before(self, **kwargs):
        return [SimpleNamespace(role="assistant", content="".join(self.reply_lines))]


def _case():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "cases" / "voice"
    return load_case(root / "image_reply.yaml")


def _pair() -> tuple[_PairedAdapter, _PairedAdapter]:
    agent = _PairedAdapter(name="agent", kind="AGENT")
    user = _PairedAdapter(name="user", kind="STANDARD")
    agent.peer, user.peer = user, agent
    return agent, user


# --------------------------------------------------------------------- 用例


async def test_image_reply_case_declares_a_real_turn():
    """case 的形状先钉住：模式、fixture、关键词族——族要是被删空，实跑就没断言了。"""
    case = _case()
    assert case.id == "image_reply"
    assert case.mode == "real_turn"
    assert case.real_turn is not None
    assert case.real_turn.fixture == "shapes"
    assert case.real_turn.text == "照片里有什么？"
    assert len(case.real_turn.keyword_family) >= 4


async def test_real_turn_merges_the_attachment_into_the_same_message():
    """承重用例：图经 ``control.input`` 进槽，并被并入**提交这一条文字**的那次 submit。"""
    reply = ("照片里左边是一个红色的圆，右边是一个蓝色的方框。",)
    platform = _Platform(reply_lines=reply)
    agent_rtc, user_rtc = _pair()

    result = await run_real_turn(
        case=_case(), url="mem://room", agent_token="tok-a", user_token="tok-u",
        owner_id=91001, platform=platform, agent_rtc=agent_rtc, user_rtc=user_rtc,
        room="script-image_reply-x", wait_timeout_sec=5.0)

    assert len(platform._submit.calls) == 1, "一条带图消息只能提交一次"
    call = platform._submit.calls[0]
    assert call["attachments"] == [{"upload_id": "01UPLSCRIPT0000000000000", "kind": "image"}]
    assert call["text"] == "照片里有什么？"
    assert call["kind"] == "chat" and call["role"] == "user"
    assert result.timeline.count("speech.seg") >= 1
    assert result.timeline[-1] == "speech.end"
    assert result.seg_texts == list(reply)
    assert keyword_hits(_case().real_turn.keyword_family, result.seg_texts)


async def test_real_turn_wires_the_three_channels_on_their_real_topics():
    """三条通道的 topic 逐一钉住：hello 走 cmp.ctl、附件走 cmp.in、文字走 lk.chat。

    topic 写错是**静默**故障：LiveKit 照发，``ProtocolBridge`` 按 topic 白名单不收，
    于是「客户端发了、服务端当没看见」，两端日志都干净。
    """
    platform = _Platform(reply_lines=("看到一张图。",))
    agent_rtc, user_rtc = _pair()

    await run_real_turn(case=_case(), url="mem://room", agent_token="tok-a", user_token="tok-u",
                        owner_id=91002, platform=platform, agent_rtc=agent_rtc, user_rtc=user_rtc,
                        room="script-image_reply-y", wait_timeout_sec=5.0)

    user_data = [i for i in user_rtc.published if i[0] == "data"]
    topics_in = {i[1] for i in user_data}
    assert TOPIC_CTL in topics_in and TOPIC_IN in topics_in

    kinds = []
    for _, _topic, payload in user_data:
        env, _status = decode(payload)
        assert env is not None, "用户侧发出的每条 data 都必须是合法 v2 信封"
        kinds.append(env.t)
    assert "control.hello" in kinds and "control.input" in kinds

    # 文字：lk.chat 文本流，不是 cmp.in 上的信封
    assert any(i[0] == "text" and i[2] == "照片里有什么？" for i in user_rtc.published)

    # 出向 speech.seg 走 cmp.cue（与 protocol_bridge.speech_seg 的 topic 一致）
    segs = [i for i in agent_rtc.published if i[0] == "data" and i[1] == TOPIC_CUE]
    assert segs, "agent 没有从 cmp.cue 发出任何信封"


async def test_real_turn_fails_loudly_when_the_attachment_never_reaches_the_slot():
    """附件没进槽就**必须**报错，不能放一个纯文本回合出去让关键词断言红得莫名其妙。"""
    platform = _Platform(reply_lines=("纯文本回复。",))
    agent_rtc, user_rtc = _pair()

    # 让 cmp.in 上的信封只被记录、不路由给 agent：等价于「control.input 没送达」。
    # cmp.ctl 上的 hello 必须照常路由，否则红的是门禁而不是这一步。
    async def _drop(topic: str, payload: bytes) -> None:
        if topic == TOPIC_IN:
            await MemoryRtcAdapter.publish_data(user_rtc, topic, payload)   # 只记录，不路由
            return
        await _PairedAdapter.publish_data(user_rtc, topic, payload)

    user_rtc.publish_data = _drop

    with pytest.raises(RuntimeError, match="control.input"):
        await run_real_turn(case=_case(), url="mem://room", agent_token="tok-a",
                            user_token="tok-u", owner_id=91003, platform=platform,
                            agent_rtc=agent_rtc, user_rtc=user_rtc,
                            room="script-image_reply-z", wait_timeout_sec=2.0)
    assert platform._submit.calls == [], "附件没进槽就不该把文字提交出去"


async def test_real_turn_without_image_sends_no_attachment_and_submits_none():
    """负对照（``with_image=False``）离线版：不发 attachments 事件，submit 也必须收 None。

    这条是 ``--no-image`` 那条实跑的**机制**钉子。实跑负责证「真模型没图就不命中」，
    这条负责证那条路径的形状没坏：如果哪天有人把 ``with_image`` 的分支写歪
    （比如还是照发 attachments、只是不等槽），实跑可能还是绿的，因为图还是进了模型。
    所以这里同时钉三件事：cmp.in 上一帧没发、槽一次没收、submit 的 attachments 是 None。
    """
    # 刻意用「没图时模型真会说的那种」回答：不含任何关键词族成员。
    platform = _Platform(reply_lines=("我这边没有收到你的照片哦。",))
    agent_rtc, user_rtc = _pair()

    result = await run_real_turn(
        case=_case(), url="mem://room", agent_token="tok-a", user_token="tok-u",
        owner_id=91004, platform=platform, agent_rtc=agent_rtc, user_rtc=user_rtc,
        room="script-image_reply-neg", wait_timeout_sec=5.0, with_image=False)

    # 1. 输入侧：一条 control.input 都没发（只有 cmp.ctl 上的 hello）。
    topics = {i[1] for i in user_rtc.published if i[0] == "data"}
    assert topics == {TOPIC_CTL}, f"负对照不该往 cmp.in 发任何东西，实际 topic={topics}"
    # 2. 落库侧：submit 真的没带附件（不是「没等到所以是空列表」，而是 None）。
    assert len(platform._submit.calls) == 1
    assert platform._submit.calls[0]["attachments"] is None
    assert result.submit_attachments == [None]
    assert result.upload_id == "", "负对照连图都不该上传"
    # 3. 断言语料本身：这一族的词在这句里一个都不该出现——这正是实跑 0 命中的原因。
    assert keyword_hits(_case().real_turn.keyword_family, result.seg_texts) == []


# --------------------------------------------------------------------- 负对照的断言本身（审查 minor #8）


def test_negative_control_requires_that_submit_was_actually_called():
    """负对照必须同时满足「submit 被调过」——空列表 ``[]`` 光看 ``not any`` 是满足的。

    原来的两条（零命中 + 没收到附件）在 ``submit_attachments == []`` 时**都成立**，
    于是一条压根没走到 submit 的空回合也能把负对照判成 PASS。这正是评审点名的那个洞：
    间接由「seg 为空即 raise」兜住，但那只是运气，不是断言。
    """
    problems = negative_control_problems(hits=["红"], submit_attachments=[None], seg_texts=["红的。"])
    assert problems, "有命中必须判失败"

    problems = negative_control_problems(hits=[], submit_attachments=[], seg_texts=["没图。"])
    assert problems, "submit 一次都没被调用 → 这条负对照没有证据力，必须判失败"

    # 两条都真满足才算通过
    assert negative_control_problems(hits=[], submit_attachments=[None], seg_texts=["没图。"]) == []

    # 没有语料的零命中是空转：断言必须有话可断
    assert any("speech.seg" in p for p in
               negative_control_problems(hits=[], submit_attachments=[None], seg_texts=[]))


def test_data_handler_records_errors_on_the_real_room_path_and_still_raises():
    """``_data_handler`` 必须**同时**记账与抛出：真房路径只靠「不包 try」是假的响亮。

    真房里处理器跑在 ``create_task`` 里，异常经 ``_on_data_task_done`` 降级成一条 warning
    （rtc.py），永远到不了 ``run_real_turn``；离线路径才直接冒。所以「收进 errors」这一份
    是两条路径上唯一都成立的响亮——而抛出是给离线路径留的。两者都要钉住。
    """
    errors: list[BaseException] = []
    boom = RuntimeError("bridge regression")

    class _Bridge:
        async def on_data(self, payload, *, topic, publisher_identity, publisher_kind):
            raise boom

    handler = _data_handler(_Bridge(), errors)

    import pytest

    with pytest.raises(RuntimeError, match="bridge regression"):
        asyncio.run(handler(b"{}", TOPIC_IN, "user-1", "STANDARD"))

    assert errors == [boom], "异常必须被收进 errors，否则真房路径无声无息"


def test_data_handler_does_not_record_a_cancellation_as_a_bridge_failure():
    """取消不是 bridge 的回归：``close()`` 会 cancel 这些 task，记账会把正常收尾判成失败。

    ``rtc.py:223`` 那条旧路对 ``task.cancelled()`` 是不告警的；``_data_handler`` 原来
    ``except BaseException`` 连 ``CancelledError`` 一起收，两条路径因此不对称——
    一次正常的收尾让整跑红在「bridge 的回归，不是模型的问题」上。
    """
    errors: list[BaseException] = []

    class _Bridge:
        async def on_data(self, payload, *, topic, publisher_identity, publisher_kind):
            raise asyncio.CancelledError()

    handler = _data_handler(_Bridge(), errors)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(handler(b"{}", TOPIC_IN, "user-1", "STANDARD"))

    assert errors == [], "取消不该被记账"


async def test_real_turn_needs_a_real_bucket_instead_of_dying_on_none():
    """``--no-image`` 之外若对象存储降级（``platform.uploads is None``），要报「需要真桶」。

    原来这里直接 ``platform.uploads.accept(...)`` → ``AttributeError: 'NoneType' object has
    no attribute 'accept'``，读起来像 bug，实际是环境缺 TOS 配置——这条 case 的意义就在
    于走真实上传，所以缺桶该当场说清，而不是抛一个指向代码的假错。
    """
    platform = _Platform(reply_lines=("看到图。",))
    platform.uploads = None            # build_platform 的 TOS 自检失败就是这个样子
    agent_rtc, user_rtc = _pair()

    with pytest.raises(RealTurnError, match="桶|TOS"):
        await run_real_turn(case=_case(), url="mem://room", agent_token="tok-a",
                            user_token="tok-u", owner_id=91005, platform=platform,
                            agent_rtc=agent_rtc, user_rtc=user_rtc,
                            room="script-image_reply-tos", wait_timeout_sec=5.0)


# --------------------------------------------------------------------- 关键词族的形状


def test_no_image_flag_is_refused_on_a_push_mode_case():
    """``--no-image`` 用在 push 模式的 case 上必须当场报错，不能静默无效。

    开关注册在共享的 ``run`` 子命令上，只有 ``_run_real_turn`` 读它。push 模式压根没有
    附件路径，带上它跑完还是正向绿灯——跑的人以为做了一次负对照。
    """
    from tools.script_room import ensure_no_image_matches_mode

    ensure_no_image_matches_mode("real_turn", True)        # 合法组合：不报错

    with pytest.raises(SystemExit, match="no-image"):
        ensure_no_image_matches_mode("push", True)


async def test_cleanup_deletes_via_objects_not_uploads():
    """清理守卫必须查**真正调用的那个对象**（``objects``），不是 ``uploads``。

    原来 ``if key and platform.uploads is not None: … platform.objects.delete(key)``：
    对象存储降级时两个一起 None 所以侥幸没事，但 ``uploads`` 在、``objects`` 缺的组合会
    拿到 ``AttributeError: 'NoneType' object has no attribute 'delete'``——清理失败还
    会盖住跑测结果。三种情况都得有明确措辞：删了 / 没东西可删 / 桶不可用。
    """
    from tools.script_room import cleanup_fixture_object

    deleted: list[str] = []

    class _Objects:
        async def delete(self, *, key: str) -> None:
            deleted.append(key)

    class _Platform:
        objects = _Objects()

    assert "deleted" in await cleanup_fixture_object(_Platform(), "companion-qa/uploads/x.jpg")
    assert deleted == ["companion-qa/uploads/x.jpg"]

    # 负对照：没上传，别拿空 key 去删
    assert "无需删除" in await cleanup_fixture_object(_Platform(), "")
    assert deleted == ["companion-qa/uploads/x.jpg"]

    # 桶不可用：返回一句 warn，不抛（清理失败不能盖住跑测结果）
    class _NoBucket:
        objects = None

    msg = await cleanup_fixture_object(_NoBucket(), "companion-qa/uploads/y.jpg")
    assert "对象存储不可用" in msg


async def test_cleanup_failure_is_a_warning_not_an_exception():
    from tools.script_room import cleanup_fixture_object

    class _Broken:
        async def delete(self, *, key: str) -> None:
            raise RuntimeError("tos 503")

    class _Platform:
        objects = _Broken()

    assert "cleanup 失败" in await cleanup_fixture_object(_Platform(), "k")


# --------------------------------------------------------------------- 断言函数本身
    """关键词族里不许有泛词，也不许有提问句里本来就有的词。

    泛词加进族里，断言当场空转：模型看不到图时的标准回答就是在说「照片 / 发过来 /
    看看里面有什么」。这条测试就是 ``--no-image`` 的便宜替身——它跑在任何机器上，
    代价是**弱于**实跑：只挡泛词复述这一种退化，不证伪「命中 ⇔ 图进了模型」。
    """
    case = _case()
    assert case.real_turn is not None
    family = case.real_turn.keyword_family
    assert vacuous_family_members(family, text=case.real_turn.text) == []

    # 闸本身确实在咬人（不咬人的闸等于没有）
    assert vacuous_family_members(family + ("照片",), text=case.real_turn.text) == ["照片"]
    assert vacuous_family_members(family + ("photo",), text=case.real_turn.text) == ["photo"]
    # 复述提问句的词也算泛词：命中只说明模型把问题念了一遍
    assert vacuous_family_members(("照片",), text=case.real_turn.text) == ["照片"]


# --------------------------------------------------------------------- 断言函数本身


def test_keyword_hits_matches_across_sentences_and_case():
    family = ("圆", "红", "circle", "red")
    # 要素只出现在第二句：逐句判会漏，拼接后判才算命中
    assert keyword_hits(family, ["我看到两个图形。", "左边是红色的圆。"]) == ["圆", "红"]
    # 英文回复也算命中（族里中英都给了，不该逼模型用中文说话）
    assert keyword_hits(family, ["There is a RED circle."]) == ["circle", "red"]
    assert keyword_hits(family, ["一张风景照。"]) == []


# --------------------------------------------------------------------- import 边界


def test_entrypoint_no_longer_re_exports_text_topic():
    """``entrypoint`` 不再再导出 ``TEXT_TOPIC``——那是 livekit.agents 泄漏的入口。

    全仓零读者，留着只邀请人写 ``from ...entrypoint import TEXT_TOPIC``，而那会把本模块
    模块级的音频探针（``from livekit import rtc`` + ``from livekit.agents.voice.io``）
    整块拖进剧本房的模块图。值的本尊在 ``api.livekit.topics``。
    """
    import importlib

    topics = importlib.import_module("companion.api.livekit.topics")
    entry = importlib.import_module("companion.api.livekit.entrypoint")

    assert topics.TEXT_TOPIC == "lk.chat"
    assert not hasattr(entry, "TEXT_TOPIC"), (
        "entrypoint 又再导出了 TEXT_TOPIC：从那里 import 会把 livekit.agents 拖进剧本房")


def test_real_turn_imports_without_livekit_agents():
    """``real_turn`` 的「离线」宣称必须是**真**的：挡住 ``livekit.agents`` 还能 import。

    为什么值得单独一条：``real_turn`` 的 docstring 承诺不 import livekit /
    livekit.agents，而**没有任何静态闸能守住它**（``.importlinter`` 那 6 条契约一条都不
    覆盖 ``companion.devtools``）。它当初就是这么坏的——``from
    companion.api.livekit.entrypoint import TEXT_TOPIC`` 经模块级音频探针把
    ``livekit.agents`` 整块拖了进来，于是这套「离线」测试也得装 ``--extra livekit``
    才跑得动，而这恰好掩盖了它本来能离线跑这件事。

    跑在子进程里而不是本进程：``livekit.agents`` 早已被本测试会话的其它 import 载入了，
    在进程内加 blocker 只会测到「Python 的模块缓存」。子进程是唯一干净的观测点。

    ``livekit`` 核心**不**挡——它经 ``rtc.py``（``MemoryRtcAdapter`` 的家）合法进来。
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    server_root = Path(__file__).resolve().parents[1]
    probe = """
import sys, importlib.abc

class BlockLivekitAgents(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == "livekit.agents" or name.startswith("livekit.agents."):
            raise ImportError("livekit.agents is not allowed here: " + name)
        return None

sys.meta_path.insert(0, BlockLivekitAgents())
import companion.devtools.script_room.real_turn
import companion.devtools.script_room.rtc
print("OFFLINE-OK")
"""
    env = {**os.environ, "PYTHONPATH": str(server_root / "src")}
    proc = subprocess.run([sys.executable, "-c", probe], cwd=str(server_root), env=env,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, (
        f"real_turn 在没有 livekit.agents 的环境里 import 失败——它已经不是离线路了：\n"
        f"{proc.stdout}\n{proc.stderr}")
    assert "OFFLINE-OK" in proc.stdout, proc.stdout + proc.stderr

