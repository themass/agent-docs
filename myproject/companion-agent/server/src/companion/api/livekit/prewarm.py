"""job 进程预热：把首帧才会碰的重 import 提前到进程启动时做完。

线上事故（2026-11-18）：语音 agent 的 job 进程冷启动 10–20 秒，日志里 SDK 直接
点名——

    event loop blocked for 11844ms importing agentkit.observability.federation
    at .../botocore/docs/bcdoc/restdoc.py; import it at process warm-up
    (prewarm) instead of on first use

botocore 的文档子树是出了名的慢 import，而 `metrics.py` 里的 agentkit 指标在每
个房间的第一次调用就会把它拉进来。首帧被 import 卡住的十几秒里，客户端的 hello
早已超时、协议降级成 v1——握手竞态修好之后，这就是用户等待剩下的主要来源。

SDK 给了现成的挂载点：`WorkerOptions.prewarm_fnc`（worker.py:190），每个 job 进程
在接到任务之前跑一次（`initialize_process_fnc`），失败就放弃这个进程重来，不会
把坏进程放出去接房。

这里只做一件事：把首帧链路一定会碰的重模块先 import 掉。绝不在这做建连接、
读远端配置之类的副作用——prewarm 的产物靠 forkserver 的写时复制传给每个 job
进程，副作用会被复制同样次数，那是事故而不是优化。
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

#: 首帧必经的重 import。每一项都要能对上生产日志里点过名、或代码里每房间第一次
#: 调用就会触发的模块；只列模块名，不做任何调用。
PREWARM_IMPORTS = (
    # metrics.py:33 —— 每个房间第一次记指标就会拉 botocore（11.8s 的那条）
    "agentkit.observability",
    # service/uploads/* —— 图片/上传策略第一次用时拉 boto3 客户端构建链
    "agentkit.storage.object_store",
)


def prewarm(job_proc: Any = None) -> None:
    """`WorkerOptions.prewarm_fnc` 的实现。签名里的 job_proc SDK 传入、我们不用。

    import 失败不吞掉：让异常冒出去，SDK 会按进程失败处理并在日志里带完整
    traceback——比静默降级回"首帧再卡一次、现场无线索"好得多。
    """
    t0 = time.perf_counter()
    for name in PREWARM_IMPORTS:
        __import__(name)
    logger.info("prewarm done modules=%d cost_ms=%.0f", len(PREWARM_IMPORTS), (time.perf_counter() - t0) * 1000)
