"""``control.input`` 的多 kind 分发与「等下一回合」的附件暂存槽（图片消息 P1）。

端侧发一条带图的消息是**两个动作**：先把 ``control.input`` (``kind=attachments``) 从数据通道
推过来，再用 ``lk.chat`` 发文字。两条消息走的是不同通道、不同队列，服务端看到它们的**顺序
不是可以保证的**——所以这里只能先收下，不能就地绑定。

做法就是一个 per-worker 的槽：``put`` 暂存 ``upload_ids``，下一回合 ``PlatformBrain.start_turn``
``consume`` 取走并交给 ``submit(attachments=…)``，之后走既有链路
（``meta.attachments → _attachment_ids → get_owned → 喂模型``）。**服务端不新读图接口**，
图片本身也不经过这里（上传早就是 ``POST /v1/uploads`` 的事）。

**为什么槽是 per-worker 而不是 per-room 表**：``RoomEntrypoint`` 一个房间起一个 worker，
一个 worker 一个 bridge、一个用户（见 ``protocol_bridge`` 的身份白名单）。所以实例变量
就是房间级的状态，不需要 Redis，也不需要额外的键。

**为什么必须只有一个实例**：写它的是数据通道，读它的是回合线程。入口对象把同一个槽喂给
``CompositeInputRelay`` 与 ``PlatformBrain``；两个实例的话，功能整体失效且一条错误都不报。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from companion.api.livekit.touch_input import (
    DEFAULT_COOLDOWN_S,
    DEFAULT_TOUCH_WARMUP_S,
    TouchInputRelay,
)
from companion.service.uploads.policy import MAX_MESSAGE_ATTACHMENTS

logger = logging.getLogger(__name__)

#: 暂存多久。端侧的 attachments 事件和文字是同一次点击的两个动作，正常情况下差的是
#: 毫秒级；给到 60 秒是留够网络抖动，同时不至于让一批早就作废的图片在几十分钟后
#: 突然出现在另一条消息里。
PENDING_TTL_SEC = 60

#: 判定「文字先到了」的宽限：上一回合取走了一个空槽之后，这段时间内落地的 attachments
#: 基本只可能是那条消息的迟到件（而不是新一次点击）。取小是因为这是**启发式**——
#: 用户连发两条（第一条纯文本、第二条带图）时，第二条确实会落在宽限里，
#: 代价是多一行 warn 日志；反过来漏判的代价是「图跑到下一条消息里」却查不到线索。
LATE_ARRIVAL_GRACE_SEC = 3.0


@dataclass(slots=True)
class _Staged:
    """槽里的一批附件。``staged_at`` 用的是槽的时钟，不是墙上时间。"""

    staged_at: float
    client_msg_id: str | None
    upload_ids: tuple[str, ...]


class PendingAttachmentSlot:
    """一个房间的「下一回合附件」暂存位：``put`` 存、``consume`` 取并清。

    只做四件事，且都不抛：校验（上限、类型）、覆盖（新一批替换未消费的旧一批）、
    幂等（同 ``client_msg_id`` 重发不翻倍）、过期（超过 TTL 直接给空）。
    """

    def __init__(self, *, clock: Callable[[], float] = time.monotonic,
                 ttl_sec: float = PENDING_TTL_SEC) -> None:
        """``clock`` 是测试注入点：TTL 的用例要手动推进时间，而不是 sleep 60 秒。
        默认 ``time.monotonic``——它不受系统时钟回拨影响，量的是「过了多久」这个时长。"""
        self._clock = clock
        self._ttl = float(ttl_sec)
        self._staged: _Staged | None = None
        # 最近一次「取到空槽」的时刻。put 用它判断这批是不是迟到的（见
        # LATE_ARRIVAL_GRACE_SEC）。None 表示这个 worker 还没提交过回合。
        self._last_empty_consume_at: float | None = None
        # 最近一次被消费掉的那批的 client_msg_id。重传可能晚到消费之后，
        # 那时槽已经空了，只看槽分不出「重发」和「新消息」。
        #
        # **这个记忆没有过期时间，这是刻意的**（别按 TTL 给它加一个）：槽空了以后只能靠
        # id 认重发，一旦让它过期，同一条消息的迟到重传就会被当成**新消息**的附件，
        # 贴到用户下一条消息上——那比「认出来然后丢掉」糟得多。
        #
        # 代价要说清：只记**最近一次**那批。上上次那批的迟到重传认不出来，会被当成
        # 新附件收进槽。（id 是端侧每次点击现造的、房间又是 per-worker，撞上概率极低；
        # 由 ``tests/test_input_attachments.py`` 把这个边界钉成测试，不让它读起来像已防住。）
        self._consumed_client_msg_id: str | None = None
        # 计数器。放量前必须能从日志里读出「这个房间的附件事件收了多少、拒了多少」——
        # 一条带图消息变成纯文本，线上要分得开「事件根本没到」与「到了但被拒」。
        # consume 把这两个数落到一行 INFO（见 :meth:`consume`）。
        #
        # ``accepted`` 含**幂等命中**（同 ``client_msg_id`` 的重发也是「收下」，返回 True）：
        # 它统计的是「收下的事件条数」，不是「不同的消息条数」。重发单独计在
        # ``duplicates`` 里，所以一行日志能把「用户点了 3 次」和「点了 1 次重传 2 次」分开。
        self.accepted = 0
        self.duplicates = 0
        self.ignored = 0

    def put(self, upload_ids: Any, *, client_msg_id: Any) -> bool:
        """暂存一批 upload_id。收下返回 True，拒收返回 False（槽原样不动）。

        拒收只记 warn 不抛：``control.input`` 的处理器在 ``ProtocolBridge._on_input`` 里
        是被 try 包住的，抛上去也只是多一条 warning，而丢一条不该影响会话的输入
        （文档 §14.1）。槽原样不动是为了不让一条坏投递把已经收下的好附件冲掉。
        """
        ids = _clean_ids(upload_ids)
        if ids is None:
            self.ignored += 1
            self._warn_rejected(upload_ids, client_msg_id)
            return False

        key = client_msg_id.strip() if isinstance(client_msg_id, str) and client_msg_id.strip() else None
        staged = self._staged
        if key is not None and (key == self._consumed_client_msg_id
                                or (staged is not None and staged.client_msg_id == key)):
            # 重发（control.input 是 MUST 投递，重传合法）。同一条消息的同一批图
            # 只记一次——否则一次点击的两张图会变成消费时的四张。
            # 记的不只是槽里那一批：重传可能晚到**已经消费之后**，那时槽是空的，
            # 不记的话这批图会被当成新消息的附件，贴到用户下一条消息上。
            # 计数口径：重发算「收下」（与 ``CompositeInputRelay.accepted`` 一致，
            # 那边按 put 的返回值累加），另记一笔 duplicates，免得「点了 1 次重传 2 次」
            # 在日志里读成「用户发了 3 条带图消息」。
            self.accepted += 1
            self.duplicates += 1
            logger.info("duplicate attachments event client_msg_id=%s ignored", key)
            return True

        if self._last_empty_consume_at is not None:
            late = self._clock() - self._last_empty_consume_at
            if 0.0 <= late <= LATE_ARRIVAL_GRACE_SEC:
                # 上一回合刚带着「没有附件」提交掉了，现在附件才到——这基本就是那条
                # 消息的迟到件（文字走 lk.chat、附件走数据通道，谁先到没有保证）。
                # 图不会丢（覆盖语义 + TTL 之内都有效），但它会落进**下一条**消息，
                # 和用户点的那条不是同一条。这种错位从聊天界面上看不出原因，必须留痕。
                logger.warning(
                    "attachments arrived after the previous turn was already submitted without "
                    "them (late by %.1fs, client_msg_id=%s, %d ids); they will be merged into "
                    "the NEXT turn instead", late, key, len(ids))
        elif staged is not None:
            # 还没被消费就被替换。正常只发生在「用户上一条带图消息还没发出就换了图」。
            logger.info("pending attachments replaced client_msg_id=%s -> %s",
                        staged.client_msg_id, key)

        self._staged = _Staged(staged_at=self._clock(), client_msg_id=key, upload_ids=ids)
        self.accepted += 1
        return True

    def consume(self) -> list[str]:
        """取走这批附件并清空（消费即清）。空槽或过期返回 ``[]``，不抛。"""
        staged = self._staged
        ids: list[str] = []
        if staged is None:
            self._last_empty_consume_at = self._clock()
        else:
            self._staged = None
            # 这批已经「用过」了（并入过一条消息，或因过期被丢）。记下它的 id：
            # 同一条消息的重传随后到达时，槽是空的，只能靠这个认出来。
            self._consumed_client_msg_id = staged.client_msg_id
            if (self._clock() - staged.staged_at) > self._ttl:
                logger.warning("pending attachments expired after %.0fs client_msg_id=%s: %s",
                               self._ttl, staged.client_msg_id, list(staged.upload_ids))
                self._last_empty_consume_at = self._clock()
            else:
                ids = list(staged.upload_ids)
        self._log_counters(ids)
        return ids

    def _log_counters(self, ids: Sequence[str]) -> None:
        """每回合消费时把两个计数器落到一行 INFO——放量前的第四条件。

        「图片没被理解」在线上必须能分开两种成因：**事件根本没到**（这个房间连一行计数器
        都没有，说明端侧没发或数据通道没送）与**到了但被拒**（``ignored>0``，同一行里
        还有上面那条 rejected 的 warn 可以对照）。没有这行，两者在端上长得一模一样。

        一条附件事件都没收到时**不打**：纯文本回合是每个房间都有的事，为一件没发生的
        事刷日志会把这行真正的信号淹掉。「没有这行」因此也是可读的事实。
        """
        if not (self.accepted or self.ignored or self.duplicates):
            return
        logger.info("attachments consumed for this turn: %d; counters accepted=%d ignored=%d "
                    "duplicates=%d", len(ids), self.accepted, self.ignored, self.duplicates)

    def _warn_rejected(self, upload_ids: Any, client_msg_id: Any) -> None:
        kinds = {type(upload_ids).__name__}
        if isinstance(upload_ids, Sequence) and not isinstance(upload_ids, (str, bytes)):
            kinds.add("+".join(sorted({type(x).__name__ for x in upload_ids})) or "empty")
        logger.warning("rejected control.input attachments client_msg_id=%r ids=%r (%s)",
                       client_msg_id, upload_ids, ",".join(sorted(kinds)))


def _clean_ids(upload_ids: Any) -> tuple[str, ...] | None:
    """校验**并规范化**；不合法返回 ``None``。

    上限用 :data:`MAX_MESSAGE_ATTACHMENTS`（媒体限制的本家，HTTP 上传与发送校验同源）。

    strip 必须在**存进槽之前**做完，不能只用来判空：下游 ``get_owned`` 是按 ULID
    精确查的，``" 01A "`` 校验时通过、查库时查不到，表现是「图收下了、模型看不到」，
    而计数器与日志一切正常——正是最难查的那种错位。
    """
    if not isinstance(upload_ids, list) or not upload_ids:
        return None
    if len(upload_ids) > MAX_MESSAGE_ATTACHMENTS:
        return None
    cleaned: list[str] = []
    for x in upload_ids:
        if not isinstance(x, str) or not x.strip():
            return None
        cleaned.append(x.strip())
    return tuple(cleaned)


class CompositeInputRelay:
    """``ProtocolBridge.on_input`` 的唯一消费者：按 ``args["kind"]`` 分流。

    签名与 :class:`~companion.api.livekit.touch_input.TouchInputRelay` 一致（同步、
    收 args dict），所以 bridge 侧 ``bridge.on_input = …`` 那一行的契约不变。
    ``kind=touch`` 直接转给内部的 ``TouchInputRelay``，冷却语义原样保留；
    ``kind=attachments`` 进槽；其余 kind 两边都不碰，只计 :attr:`ignored`。

    这里不抛异常，理由和槽的 ``put`` 一样：输入链不该被一条坏输入拖停。
    """

    def __init__(
        self,
        session: Any,
        slot: PendingAttachmentSlot,
        *,
        cooldown_s: float = DEFAULT_COOLDOWN_S,
        touch_warmup_s: float = 0.0,
    ) -> None:
        self.touch = TouchInputRelay(session, cooldown_s=cooldown_s, warmup_s=touch_warmup_s)
        self._slot = slot
        #: 分发器自己拒掉的条数（kind 缺失或不认识）。触摸分支内部的拒收记在
        #: ``touch.ignored`` 里，两处加起来才是「这个房间丢了多少条 control.input」。
        self._unknown_kind = 0

    @property
    def accepted(self) -> int:
        """收下的附件事件条数——**读槽的那一个计数器**，不在这里再累加一遍。

        两个累加器迟早对不上，而线上那行日志（``PendingAttachmentSlot._log_counters``）
        读的是槽的数；剧本房等「这批 id 真的进槽了」也读同一个数。一处累加、多处读。
        """
        return self._slot.accepted

    @property
    def ignored(self) -> int:
        """这个房间丢了多少条 ``control.input``：附件路的拒收（在槽里）+ 没人认领的 kind。"""
        return self._unknown_kind + self._slot.ignored

    def __call__(self, args: dict[str, Any]) -> None:
        kind = args.get("kind") if isinstance(args, dict) else None
        if kind == "attachments":
            self._on_attachments(args)
        elif kind == "touch":
            self.touch(args)
        else:
            self._unknown_kind += 1
            logger.info("control.input kind=%r has no handler (ignored=%d)", kind, self.ignored)

    def _on_attachments(self, args: dict[str, Any]) -> None:
        # put 自己计数并落日志（拒收另有 warn），这里只管分流——见 accepted/ignored 两个属性。
        self._slot.put(args.get("upload_ids"), client_msg_id=args.get("client_msg_id"))
