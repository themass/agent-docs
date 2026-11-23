"""``mode: real_turn`` 剧本房的房间侧编排：一张图 + 一句话，走到真模型。

与 push 模式的区别就是本模块存在的全部理由：``runner.run_script_room`` 把 YAML 里的
``expect_reply`` 当台词推给房间，全程**不调模型、也不碰 ``control.input`` 的附件槽**——
拿它跑「图片消息」，断言的其实是我们自己写进 YAML 的那句话（自证）。
real_turn 反过来：用户 participant 在房里依次发真实的 ``control.input(kind=attachments)``
与 ``lk.chat`` 文字，回合由生产那一条装配跑完，说的话由真模型看着图生成，
再用 case 里的关键词族回扣图内内容。

装配与 ``api/livekit/entrypoint.py`` 的语音房间同形（``BridgeOverRtc`` /
``SpeechPublisher`` / ``PendingAttachmentSlot`` + ``CompositeInputRelay`` /
``PlatformBrain`` + ``TurnPipeline``），差别只有两处，都是刻意的：

1. 不起 ``AgentSession`` / 语音栈：文字由我们自己从 ``lk.chat`` 读，STT/TTS/VAD 与
   框架的 ``last_user_message`` 抽取因此不在覆盖范围（那是真机窗口的事，见验收 notes）。
2. ``kind="chat"``、``role="user"``（语音房间是 voice）。陪伴页的图片消息本来就是文字回合。

本文件自己**既不 import livekit，也不 import livekit.agents**（``rtc.py`` 的模块级约定：
livekit 只许出现在那一个文件里）。房间读写一律经
:class:`~companion.devtools.script_room.rtc.RtcAdapter`；文本流的 topic 从
``api.livekit.topics`` 取——那是一个只有常量的纯模块，**不是** ``api.livekit.entrypoint``：
后者在模块级 import 音频探针（``from livekit import rtc`` +
``from livekit.agents.voice.io import AudioInput``），为了一个字符串就能把 livekit.agents
整块拖进模块图，那样这条离线路就名不副实了。

这条边界由 ``tests/test_script_room_real_turn.py`` 里的子进程探针钉住：把
``livekit.agents`` 挡住再 import 本模块，必须还能成功。（``livekit`` 核心仍会经
``rtc.py`` 间接进来——那是设计如此，离线的 ``MemoryRtcAdapter`` 就住在那个文件里。）
这么做的附带好处是整条编排能用 ``MemoryRtcAdapter`` 离线跑，不碰网络也能证明信封、
门禁与并入这段接线没坏。

覆盖边界要说清楚（别把这台机器上验过的当成全验了）：
- 这条 case 机器验的：envelope 走真实 topic 与 v2 门禁、附件经 ``control.input`` 进槽并被
  并入**同一条**用户消息、回合真的出 ``speech.seg``、seg 文本命中图内要素关键词。
- 不验（留给真机）：手机出站顺序本身、待发条 UI、收纳盒/长按渲染。见验收 notes 的 deferred 清单。
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from companion.agent.brain.port import TurnRequest
from companion.agent.protocol import SERVER_CAPS, encode, new_envelope
from companion.agent.protocol.catalog import TOPIC_CTL, TOPIC_IN
from companion.api.livekit.input_attachments import CompositeInputRelay, PendingAttachmentSlot
from companion.api.livekit.protocol_bridge import ProtocolBridge
from companion.api.livekit.speech_publisher import SpeechPublisher
from companion.api.livekit.topics import TEXT_TOPIC
from companion.devtools.script_room.bridge_over_rtc import BridgeOverRtc
from companion.devtools.script_room.case_schema import ScriptCase
from companion.devtools.script_room.rtc import RtcAdapter
from companion.service.turn.pipeline import TurnPipeline
from companion.service.turns.platform_brain import PlatformBrain

logger = logging.getLogger(__name__)

#: 陪伴角色卡（``agent/characters``）：用仓库里的真人设，不新造一份提示词。
#: linche 在 ``bootstrap.platform.BUILTIN_PERSONA_IDS`` 里，``default_prompts()`` 认它。
CHARACTER_ID = "linche"

#: 附件事件要真的落进槽，文字才发得出去。超过这个秒数就判定「``control.input`` 没进槽」
#: ——那是协议层的失败，必须当场报，而不是放一个纯文本回合出去、让关键词断言红得莫名其妙。
SLOT_SETTLE_TIMEOUT_SEC = 5.0


class RealTurnError(RuntimeError):
    """编排里任何一步「达不到就不该继续」的事实。报错信息一律指向缺失的东西。"""


# --------------------------------------------------------------------- fixture 图


def _shapes_jpeg() -> bytes:
    """内容已知的图：浅灰底 + 左边实心红圆 + 右边蓝色方框。

    为什么自己画、而不是放一张照片进仓库：

    * 内容由代码写死，``real_turn.any_of`` 那族关键词因此是**可证**的，
      不是照着某张照片事后补出来的；
    * 不往仓库塞二进制，也不依赖任何外链（外链哪天失效，case 就红得莫名其妙）；
    * 元素少、颜色纯正，模型对它的描述在多次运行之间稳定——关键词族兜得住改写，
      兜不住的是「模型根本没看到图」，而那正是这条 case 要抓的故障。

    刻意只放形状与颜色、不放文字：模型对图内 OCR 的措辞自由度太大，
    会把断言变成运气测试。
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (640, 480), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    draw.ellipse((60, 90, 300, 330), fill=(220, 30, 30))
    draw.rectangle((360, 120, 580, 340), outline=(20, 60, 200), width=18)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


_FIXTURES: dict[str, Callable[[], bytes]] = {"shapes": _shapes_jpeg}


def fixture_bytes(name: str) -> bytes:
    """按名字取 fixture 图的字节。名字表在这里，YAML 写错要立刻报错而不是静默跑错图。"""
    try:
        make = _FIXTURES[name]
    except KeyError:
        known = ", ".join(sorted(_FIXTURES))
        raise RealTurnError(f"未知 fixture {name!r}（可用：{known}）") from None
    return make()


# --------------------------------------------------------------------- 房间编排


@dataclass
class _TouchSession:
    """``CompositeInputRelay`` 要的 ``session`` 形状。

    它只服务 ``kind=touch`` 分支（``generate_reply(user_input=...)``）。剧本房不发触摸，
    留这个计数是为了「触摸分支被误触发」看得见——那意味着分流器把这条消息当成了别的东西，
    静默放过的话，测试照样绿。
    """

    generate_reply_calls: list[str] = field(default_factory=list)

    def generate_reply(self, *, user_input: str) -> None:
        self.generate_reply_calls.append(user_input)


@dataclass
class _RecordingSubmit:
    """包一层 ``platform.chat.submit``，只记下「这条消息最终带没带附件」。

    负对照（``with_image=False``）的承重证据就在这里：不是「我没发 attachments 事件」
    （那只是输入侧的事实），而是**这一条 submit 真的没收到任何附件**。
    没有这一条，负对照只能证明「模型没看图」（keyword 0 命中），证不到
    「附件那条路确实是断的、所以 0 命中不是因为图以别的方式混进来的」。
    """

    inner: Any
    attachments: list[Any] = field(default_factory=list)

    async def submit(self, **kw):
        self.attachments.append(kw.get("attachments"))
        return await self.inner.submit(**kw)


@dataclass(frozen=True)
class RealTurnResult:
    """一次 real_turn 跑完的事实。断言不在这里做——结论与证据分开，CLI 才打印得出来。"""

    #: 房间时间线里出现过的协议事件类型名（与 push 模式的 timeline 同形）。
    timeline: list[str]
    #: **成功发出 ``speech.seg``** 的句子的文本。
    #: 只有 ``publisher.say`` 返回了 ``(speech_id, seg)`` 的句子才在这里——也就是真的
    #: 有一条 ``speech.seg`` 抵达房间的那些。「说了这句话」与「这句上线了」因此是同一件事，
    #: 关键词断言不会落到一句从没上线的句子上。
    seg_texts: list[str]
    #: 回合落库的助手消息（证据；断言仍以 seg_texts 为准——那才是房间内时间线的事实）。
    stored_reply: str
    upload_id: str
    object_key: str
    session_id: int
    turn_id: str
    #: 本次提交真正带进 ``submit`` 的附件（``PlatformBrain._take_attachments`` 的产物）。
    #: 有图跑必须非空，负对照必须为 ``None``——两个方向都是断言的证据。
    submit_attachments: list[Any]


async def _wait_until(pred: Callable[[], bool], *, timeout: float, what: str) -> None:
    """轮询等一个条件成立；到点不成立就报错，并说清在等**什么**。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return
        await asyncio.sleep(0.05)
    raise RealTurnError(f"等不到 {what}（{timeout:.0f}s 内）")


async def run_real_turn(
    *,
    case: ScriptCase,
    url: str,
    agent_token: str,
    user_token: str,
    owner_id: int,
    platform: Any,
    agent_rtc: RtcAdapter,
    user_rtc: RtcAdapter,
    room: str,
    wait_timeout_sec: float = 120.0,
    with_image: bool = True,
) -> RealTurnResult:
    """把一条带图消息端到端跑一遍，返回时间线与证据。

    ``platform`` 是 ``bootstrap.platform.build_platform`` 的产物（真大脑、真回合层、
    真上传服务）。两个 ``rtc`` 是**两条独立连接**：``agent_rtc`` 是房间里的 agent
    （token 顶层 ``kind=agent``），``user_rtc`` 扮演用户设备（普通 user token，它的 data
    在 agent 侧才被认成 ``STANDARD``——``ProtocolBridge`` 的身份白名单按 kind 过滤，
    两边都用 agent token 的话输入会被整条丢掉，一条日志都没有）。

    token / owner / platform 都摊开在参数里是故意的：谁连哪个房间、这条消息属于谁，
    是这条 case 最需要一眼看清的三件事。

    ``with_image=False`` 是**负对照**：装配、文字、模型、门禁全都不变，只有两件事变——
    不发 ``control.input(kind=attachments)``、也不等槽。同一个 ``run_real_turn`` 因此
    既能证「带图 → 命中」也能证「不带图 → 不命中」，「关键词命中 ⇔ 图到了模型」这才
    是可复现的，而不是某一次贴文。为什么必须同一条路径而不是另起一个精简版：
    只有共用装配，两条跑法之间的**唯一**差别才真的是「有没有那批图」，
    任何一边悄悄改了装配都会把对照关系弄脏。
    """
    real = case.real_turn
    if real is None:
        raise RealTurnError(f"case {case.id} 没有 real_turn 块，不能用 real_turn 跑")

    # ---- 1. 输入先备好：会话、fixture 图、上传 id。这几步都不碰房间，
    # 失败的话不该让另一端先看到半个回合。
    if with_image and platform.uploads is None:
        # build_platform 在对象存储自检失败时把 uploads 降级成 None（只关上传，不挡启动）。
        # 这条 case 的意义就在于走**真实上传**，所以缺桶要当场说清——直接往下走会得到
        # ``AttributeError: 'NoneType' object has no attribute 'accept'``，读起来像代码 bug，
        # 实际是环境缺 TOS_* 配置。
        raise RealTurnError("这条 case 需要真桶：platform.uploads 为 None"
                            "（TOS_* 未配置或自检失败，见 build_platform 的降级日志）")
    session = await platform.chat.sessions.create(
        owner_id=owner_id, role_id=CHARACTER_ID, name=f"script-{case.id}", locale="zh-CN")
    # 负对照连图都不上传：留着一个没人引用的对象，只是把桶弄脏。
    upload = (await platform.uploads.accept(owner_id=owner_id, data=fixture_bytes(real.fixture))
              if with_image else None)
    logger.info("real_turn room=%s session=%s upload=%s with_image=%s",
                room, session.id, upload and upload.id, with_image)

    # ---- 2. agent 侧接线必须在用户进房之前全挂好：客户端一连上就发 hello，
    # 晚挂一步就漏掉那一条（同 entrypoint 的注释）。
    bridge = BridgeOverRtc(agent_rtc, hello_timeout_sec=wait_timeout_sec)
    texts: asyncio.Queue[str] = asyncio.Queue()
    # data handler 的异常在真房路径上会被 create_task 降级成 warning（见 _data_handler），
    # 所以留一份收集器，由 run_real_turn 在末尾统一判。
    data_errors: list[BaseException] = []
    agent_rtc.set_data_handler(_data_handler(bridge.inner, data_errors))
    agent_rtc.set_text_handler(_text_handler(texts))
    speech = SpeechPublisher(bridge)  # type: ignore[arg-type]
    slot = PendingAttachmentSlot()
    touch = _TouchSession()
    relay = CompositeInputRelay(touch, slot)
    bridge.inner.on_input = relay

    recorder = _RecordingSubmit(platform.chat.submit)
    brain = PlatformBrain(submit=recorder, control=platform.chat.control,
                          pending_attachments=slot, role="user", kind="chat")
    pipeline = TurnPipeline(brain)

    # 两条连接都先建好，再等「房里有人」。反过来写（agent 先等远端、用户再连）在
    # 生产里没事——手机是独立进程，会在 agent 等待期间自己进来；但剧本房两条连接在
    # **同一个进程、同一个事件循环**里，agent 这样等就是把唯一的执行线程等死。
    # 接线安全性不受影响：handler 全在 connect 之前挂上（text handler 由 connect 补登记），
    # 而 LiveKit 只会把数据投给已连接的参与者。
    await agent_rtc.connect(url, agent_token)
    await user_rtc.connect(url, user_token)
    await agent_rtc.wait_for_remote_participant(timeout=wait_timeout_sec)

    # ---- 3. 用户侧：hello →（可选 attachments）→ 文字。
    await _send_hello(user_rtc)
    # v2 门禁（与 push 模式同一条 fail-closed 路径）：没谈成就在这里炸，
    # 而不是让 speech.seg 被 publish 安静丢弃、只剩一串 unsent 计数。
    await bridge.wait_for_hello()

    if with_image:
        assert upload is not None  # 上面 with_image 分支里必然建了
        client_msg_id = f"att-{int(time.time() * 1000)}-1"  # 端侧同款形状，别骗过幂等分支
        # 基线必须在**发之前**取：真房里数据是异步到达的，发完再取值恰好读到 0 只是运气；
        # 而离线替身房间（MemoryRtcAdapter）的路由是同步的，发完再取就已经读到 1 了，
        # 条件永远不成立。先取基线在两种房间里都正确。
        accepted_before = relay.accepted
        await _send_attachments(user_rtc, upload_id=upload.id, client_msg_id=client_msg_id)
        # 数据通道上的 attachments 与 lk.chat 上的文字是两条通道，服务端不保证到达顺序
        # （input_attachments 整段的设计前提）。端侧靠 Task 4 的「await 发布完成再发文字」压住
        # 这个窗口；这里等价地等**槽真的收了这批 id** 再发文字。relay.accepted 是
        # CompositeInputRelay 收下并校验通过的条数——不去 consume，消费必须留给回合本身。
        await _wait_until(lambda: relay.accepted > accepted_before,
                          timeout=SLOT_SETTLE_TIMEOUT_SEC,
                          what="control.input(kind=attachments) 落进暂存槽")

    # ---- 4. 文字进去，回合跑起来。
    await user_rtc.send_text(TEXT_TOPIC, real.text)
    text = await _next_text(texts, timeout=wait_timeout_sec)
    if text != real.text:
        raise RealTurnError(f"lk.chat 收到的文字不是发出去的那句：{text!r} != {real.text!r}")

    await speech.start_reply()
    turn_id = ""
    seg_texts: list[str] = []
    request = TurnRequest(user_id=str(owner_id), character_id=CHARACTER_ID, message=text,
                          session_id=session.id)
    async for output in pipeline.run(request):
        if pipeline.last_turn is not None and pipeline.last_turn.turn_id:
            turn_id = pipeline.last_turn.turn_id
        if not output.text:
            continue
        # §13 不变量 1：先声明 seg，再把它交给下游（生产里下游是 TTS）。
        # say 返回 None 表示这一句**没有**真正声明出去（未协商 / 空白 / 超段数上限），
        # 那就不能把它算进关键词断言的语料。
        declared = await speech.say(output.text, turn_id=turn_id)
        if declared is not None:
            seg_texts.append(output.text)
    await speech.finish()

    if data_errors:
        # 真房路径上这些异常只会变成 warning 日志（见 _data_handler），不查就等于静默吞掉。
        raise RealTurnError(
            f"入向 data 处理抛过 {len(data_errors)} 次：{data_errors[0]!r}"
            "——bridge 的回归，不是模型的问题")
    if touch.generate_reply_calls:
        raise RealTurnError(
            f"回合期间触摸分支被触发过：{touch.generate_reply_calls}——control.input 分流出错了")
    if not seg_texts:
        raise RealTurnError(
            f"回合跑完了但没有任何 speech.seg 真正发出（unsent={dict(bridge.inner.unsent)}）"
            "——未协商或超段数上限，关键词断言将没有语料")

    stored_reply = ""
    for message in await platform.chat.messages.list_before(
            owner_id=owner_id, session_id=session.id, before_id=None, limit=10):
        if message.role == "assistant":
            stored_reply = message.content
            break

    return RealTurnResult(timeline=list(bridge.types), seg_texts=seg_texts,
                          stored_reply=stored_reply,
                          upload_id=upload.id if upload is not None else "",
                          object_key=upload.object_key if upload is not None else "",
                          session_id=session.id, turn_id=turn_id,
                          submit_attachments=recorder.attachments)


def negative_control_problems(*, hits: Sequence[str], submit_attachments: Sequence[Any],
                              seg_texts: Sequence[str]) -> list[str]:
    """负对照（``--no-image``）的断言：返回**不成立**的条目，空列表才算通过。

    三条都要成立，缺任何一条这条负对照就没有证据力：

    1. 关键词族**零**命中——没图却命中，说明族里有泛词，或图以别的路径混进了模型。
    2. ``submit`` **被调用过**（``submit_attachments`` 非空）。这条是补的洞：
       ``submit_attachments == []`` 时「没收到附件」光看 ``not any`` 也成立，
       于是一个压根没走到 submit 的空回合能把负对照判成 PASS——绿灯证明的是「什么都没发生」。
    3. ``submit`` 收到的每一项都是空（``None`` 或空列表）。

    断言函数放模块里而不是留在 CLI 里，是为了让它能被离线测试直接跑（CLI 那条要真房真模型）。
    """
    problems: list[str] = []
    if hits:
        problems.append(f"没发附件却命中了 {list(hits)}——关键词族里有泛词，"
                        "或附件以别的路径混进了模型")
    if not submit_attachments:
        problems.append("submit 一次都没被调用——这条负对照没有任何证据力"
                        "（空列表同样满足「没收到附件」）")
    elif any(atts for atts in submit_attachments):
        problems.append(f"没发 attachments 事件，但 submit 收到了附件：{list(submit_attachments)!r}"
                        "——附件路径漏了东西")
    if not seg_texts:
        problems.append("没有任何 speech.seg 上线——关键词断言没有语料，零命中是空转")
    return problems


def keyword_hits(family: Sequence[str], seg_texts: Sequence[str]) -> list[str]:
    """回复里命中了关键词族的哪几个（保持族内顺序）。

    比对在**拼接后的整段回复**上做：一条回复常被断成多句，图内要素很可能只出现在其中一句，
    逐句判会漏。大小写不敏感——族里同时有中英文，模型回一句「There is a red circle」
    也该算命中，而不是逼它用中文说话。
    """
    joined = "".join(seg_texts).lower()
    return [k for k in family if k.lower() in joined]


#: 「没图也会说」的泛词。关键词族里出现这些词，断言当场变成空转：模型看不到图时的
#: 标准回答就是在说它们（实测：「我这边没有收到你的**照片**哦。你可以把**照片**发过来，
#: 我再帮你看看里面有什么。」——那一次 keyword_hits 为 0 全靠族里没有这些词）。
GENERIC_KEYWORDS = frozenset({
    "图", "图片", "图像", "照片", "相片", "照", "画", "画面",
    "看到", "收到", "描述", "内容", "里面", "什么", "这张", "这张图", "发", "发过来",
    "image", "photo", "picture", "see", "describe", "content", "show",
})


def vacuous_family_members(family: Sequence[str], *, text: str) -> list[str]:
    """关键词族里**不该有**的成员：泛词，或本来就出现在提问句里的词。

    两种空转都算：

    1. **泛词**（在 :data:`GENERIC_KEYWORDS` 里）——模型没图也会说，命中不代表看了图。
    2. **提问句里就有的词**——模型只要复述一遍问题就算命中，同样与图无关。

    为什么放在产品模块而不是测试文件里：族写在 ``cases/voice/image_reply.yaml``，
    校验函数住在 case 旁边，谁改族都能就近看到这条规矩；测试只是把它跑起来。

    **这条闸的边界要说清**：它挡得住「把族加宽成泛词」这一类退化，挡不住一个既不在
    黑名单里、也不在提问句里的新泛词。真正能证伪「命中 ⇔ 图到了模型」的只有
    ``--no-image`` 那一条实跑（同装配、不带图、必须 0 命中）；这个函数只是便宜的第二道。
    """
    lowered_text = text.lower()
    bad = []
    for kw in family:
        low = kw.lower()
        if low in GENERIC_KEYWORDS or low in lowered_text:
            bad.append(kw)
    return bad


def _data_handler(bridge: ProtocolBridge,
                  errors: list[BaseException]) -> Callable[[bytes, str, str, str], Any]:
    """入向 data 的处理器：把异常**收进** ``errors`` 再原样抛出。

    为什么要收：``on_data`` 自己永不抛（§14.1），但我们这条编排要的是「bridge 的回归
    当场红」。而两条房间路径对异常的处理**不一样**——

    * 离线（``MemoryRtcAdapter.simulate_data``）：直接 await，异常原样冒到测试上；
    * 真房（``LiveKitRtcAdapter._dispatch_data``）：处理器跑在 `create_task` 起的
      task 里，异常只会经过 ``_on_data_task_done`` 变成一条 warning 日志，
      **不会**冒到 ``run_real_turn``。

    只靠「不包 try」在真房里是假的响亮。所以这里收一份进 ``errors``（然后照旧抛出，
    让离线路径继续直接抛给测试），``run_real_turn`` 在回合末尾检查这个列表。
    """
    async def _on_data(payload: bytes, topic: str, publisher_identity: str,
                       publisher_kind: str) -> None:
        try:
            await bridge.on_data(payload, topic=topic, publisher_identity=publisher_identity,
                                 publisher_kind=publisher_kind)
        except asyncio.CancelledError:
            # 取消不是 bridge 的回归：``close()`` 会 cancel 这些 task（rtc.py 的
            # ``_on_data_task_done`` 对 ``task.cancelled()`` 也是同样的口径——不记账、
            # 不告警）。记进来的话，一次正常的收尾会把整跑判成失败。
            raise
        except BaseException as exc:  # noqa: BLE001 — 收一份再抛，见 docstring
            errors.append(exc)
            raise

    return _on_data


def _text_handler(queue: asyncio.Queue[str]) -> Callable[[Any, str], None]:
    """``lk.chat`` 文本流的入口，喂给 :meth:`RtcAdapter.set_text_handler`。

    LiveKit 的 text handler 是**同步**回调（``Room._handle_text_stream_opened`` 直接调），
    读流因此必须甩进 task；文本进本次运行专属的队列（不是模块级全局——同一进程里
    连跑两次 case 不能互相串消息）。
    """
    def _on_text(reader: Any, participant_identity: str) -> None:
        del participant_identity
        asyncio.get_running_loop().create_task(_drain_text(reader, queue))

    return _on_text


async def _drain_text(reader: Any, queue: asyncio.Queue[str]) -> None:
    try:
        text = await reader.read_all()
    except Exception as exc:  # noqa: BLE001 — 读失败由 _next_text 的超时表现，别抛进 void task
        logger.warning("lk.chat 文本流读取失败: %s", exc)
        return
    if text:
        await queue.put(text)


async def _next_text(queue: asyncio.Queue[str], *, timeout: float) -> str:
    try:
        return await asyncio.wait_for(queue.get(), timeout=timeout)
    except TimeoutError as exc:
        raise RealTurnError(f"{timeout:.0f}s 内没等到 lk.chat 文本") from exc


async def _send_hello(rtc: RtcAdapter) -> None:
    """发一条合法 ``control.hello``。

    能力集取服务端自报的那一份（``SERVER_CAPS``）：negotiate 按名字取交集，用这一份
    保证 ``speech.v1``（``speech.seg`` 挂在它下面）与 ``media.image`` 都谈成，
    出向的 seg 与入向的 ``control.input`` 两条路都通。
    """
    await rtc.publish_data(
        TOPIC_CTL,
        encode(new_envelope(
            "control.hello",
            args={
                "proto": {"min": 2, "max": 2},
                "caps": dict(SERVER_CAPS),
                "limits": {"max_payload_bytes": 4096},
                "client": {"app": "companion", "version": "script-real", "sdk": "script"},
            },
            seq=0, ep="ep-script-real", ident="h-script-real",
        )),
    )


async def _send_attachments(rtc: RtcAdapter, *, upload_id: str, client_msg_id: str) -> None:
    """端侧那条 ``control.input(kind=attachments)``。

    ``kind`` / ``upload_ids`` / ``client_msg_id`` 三个键名与 Android 侧逐字一致
    （``LiveKitCompanionTransport.sendAttachments``）——键名错一个字母，服务端就当
    没有这批图，一条错误都不报。
    """
    await rtc.publish_data(
        TOPIC_IN,
        encode(new_envelope(
            "control.input",
            args={"kind": "attachments", "upload_ids": [upload_id], "client_msg_id": client_msg_id},
            seq=0, ep="ep-script-real", ident="i-script-real",
        )),
    )


__all__ = ["CHARACTER_ID", "GENERIC_KEYWORDS", "RealTurnError", "RealTurnResult",
           "fixture_bytes", "keyword_hits", "negative_control_problems", "run_real_turn",
           "vacuous_family_members"]
