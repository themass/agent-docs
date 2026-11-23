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

#: 进程级 VAD 模型缓存。prewarm 会被 forkserver 与 job 进程各调一次；模型只 load
#: 一次，后续调用查表（tests/test_worker_prewarm.py 钉住"第二次调用免费"）。
_VAD: object | None = None


def _load_vad() -> object:
    global _VAD  # noqa: PLW0603 —— 进程级缓存是本模块的职责
    if _VAD is None:
        from livekit.plugins import silero

        _VAD = silero.VAD.load()
    return _VAD

#: 首帧必经的重 import。每一项都要能对上生产日志里点过名、或代码里每房间第一次
#: 调用就会触发的模块；只列模块名，不做任何调用。
PREWARM_IMPORTS = (
    # metrics.py:33 —— 每个房间第一次记指标就会拉 botocore（11.8s 的那条）
    "agentkit.observability",
    # service/uploads/* —— 图片/上传策略第一次用时拉 boto3 客户端构建链
    "agentkit.storage.object_store",
    # bootstrap/platform.py —— build_platform 第一次装配拉 redis（2026-11-18
    # 预热上线后的新日志：event loop blocked for 13056ms importing
    # companion.service.turn.redis_control，冷盘 13 秒）
    "companion.service.turn.redis_control",
    # bootstrap/platform.py:209 `from redis import asyncio`——redis_control 只带
    # Lua 字符串不拉客户端，真正的重 import 是这里。2026-11-20 生产：
    # "event loop blocked for 11232ms importing redis.asyncio"，job 进程超
    # liveness 窗口被 SDK SIGUSR1 杀掉重试，握手期间用户干等。
    "redis.asyncio",
    # livekit SDK 自己点名（agent_activity 第一次解析 turn detection 时拉）
    "onnxruntime",
    # openai/httpx 第一次发请求时才拉 anyio 后端（小头，但同样白捡）
    "anyio._core._streams",
    # 2026-11-18 Saxw 真机对账：entrypoint → _platform 仍在事件循环里
    # import companion.agent.memory.hooks，冷盘 16.2s（经 bootstrap.platform）
    "companion.agent.memory.hooks",
    # 同上路径的组装入口：顺带把 sqlalchemy schema 等平台冷 import 提前做完
    "companion.bootstrap.platform",
    # 房间 agent 类本身（同通 368ms）；提前编译进 job 进程
    "companion.api.livekit.agent",
    # volcengine TTS 链：build_voice_stack 第一次拉 osc_data._core（同通 998ms）
    "osc_data._core",
    # openai/httpx 第一次发请求才拉的 anyio 流封装（同通 147ms）
    "anyio.streams.stapled",
    # 2026-11-21 真机测量：新进程接房后第一件事就在事件循环里同步吃这几笔冷 import
    # （skills.library 12.0s / yaml 9.5s / bootstrap.database 10.9s，loop_monitor 点名）。
    # 阻塞期间 context.build 里 0.8s 预算的 recall 必然超时——voice.log 里
    # facts error=timeout 只出现在新 pid、暖进程从不，就是这么来的。清单只列 import
    # 不猜名字：tests/test_prewarm.py 会在 CI 里逐项真 import 一遍，拼错当场红。
    "companion.agent.skills.library",
    "yaml",
    "yaml.scanner",
    "companion.bootstrap.database",
    # httpcore 的连接原语第一次发请求才拉（loop_monitor：anyio.abc._testing 135ms）
    "anyio._backends._asyncio",
    # 2026-11-22 stage-2 真机对账：5f1742d 上线后点名的换成了 psycopg——fork 子进程里
    # `importing psycopg_binary.version` 10.4s、`importing psycopg` 19.9s。
    # bootstrap.database 只有 to_psycopg_conninfo 这类纯字符串工具，不拉驱动本体；
    # 驱动是 SQLAlchemy 建第一条连接时才进来，正撞在建连关键路径上。psycopg.pq.misc
    # 是 loop_monitor 直接点过的子模块（psycopg_binary 实现经 pq 链进来）。
    "psycopg",
    "psycopg.pq.misc",
    # 2026-11-22 stage-4 生产：VAD 修复上线后接房仍冻 10–13s，loop_monitor 点名
    # `importing langgraph at bootstrap/platform.py:197 _checkpointer`（13121ms）。
    # 清单里 companion.bootstrap.platform 只拉模块本体——这行 import 藏在
    # _checkpointer() 函数体里，每房间装配平台才第一次冷 import，每个新进程付一次。
    "langgraph.checkpoint.postgres.aio",
    # 2026-11-23 stage-5：langgraph 补上后两通真机（05:29/05:33）仍各冻 10.2/10.4s，
    # 栈落在 build_platform → _build_brain → deerflow import 链。104 生产 venv
    # `-X importtime` 实测：冷 build_platform 9.8–11.0s，其中 companion.agent.
    # brain.deerflow 一条 3.85s——它 import graph_middleware 时函数体外就拉
    # deerflow.mcp（1.9s）与 langchain_anthropic（2.16s）；清单里的
    # companion.api.livekit.agent 只 import agent 模块本体，够不着 brain 链。
    "companion.agent.brain.deerflow",
    # 同上：_build_brain 函数体里的 LLMRouter / bootstrap.models / brain.tools，
    # 每房间第一次装配才冷 import（与 deerflow 同一条首帧路径）。
    "companion.agent.llm.router",
    "companion.bootstrap.models",
    "companion.agent.brain.tools",
    # 首帧 platform.astart() 里的 checkpointer.setup() 走 psycopg 连接池；
    # psycopg_pool 本体此前不在清单（psycopg 在，池不在）。
    "psycopg_pool",
)


def prewarm(job_proc: Any = None) -> None:
    """`WorkerOptions.prewarm_fnc` 的实现。job_proc 是 SDK 的 JobProcess：
    加载好的 VAD 放进它的 `userdata`，入口按 `ctx.proc.userdata["vad"]` 取用。

    import 失败不吞掉：让异常冒出去，SDK 会按进程失败处理并在日志里带完整
    traceback——比静默降级回"首帧再卡一次、现场无线索"好得多。

    VAD 模型必须在预热里加载（2026-11-22 stage-3 生产：`silero.VAD.load()` 留在
    每房间的 `build_voice_stack` 里，ONNX 同步读冻事件循环 7–23s）。这里只 load
    一次、每进程；SDK 文档推荐的就是这个位置。
    """
    t0 = time.perf_counter()
    for name in PREWARM_IMPORTS:
        __import__(name)
    vad = _load_vad()
    userdata = getattr(job_proc, "userdata", None)
    if isinstance(userdata, dict):
        userdata["vad"] = vad
    logger.info("prewarm done modules=%d vad=loaded cost_ms=%.0f",
                len(PREWARM_IMPORTS), (time.perf_counter() - t0) * 1000)
