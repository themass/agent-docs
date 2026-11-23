"""prewarm：job 进程启动时把首帧重 import 提前做完。

钉住三件事：
1. 列出来的模块真的会被 import 进 sys.modules（prewarm 写错了不会报错、只是没效果——
   这正是线上 11.8s 阻塞的原样，测试必须能抓到"静默失效"）；
2. 它会作为 WorkerOptions.prewarm_fnc 挂进真实 SDK（参数名写错 = 白做）；
3. 失败不吞（prewarm 抛异常 SDK 会弃用该进程，静默吞掉反而让坏环境继续接房）。
"""

import sys
import time

import pytest

from companion.api.livekit.capacity import worker_options_kwargs
from companion.api.livekit.prewarm import PREWARM_IMPORTS, prewarm


@pytest.fixture(autouse=True)
def _stub_vad(monkeypatch):
    """本文件验的是 import 清单与挂载，不是 ONNX 模型。

    prewarm 现在还会 load VAD（stage-3 生产：每房间 load 冻循环 7–23s）——
    这里 stub 掉真模型加载，并重置进程级缓存，保证每个用例看到的都是干净计数。
    """
    from companion.api.livekit import prewarm as mod

    monkeypatch.setattr(mod, "_VAD", None)
    monkeypatch.setattr(mod, "_load_vad", lambda: "stub-vad")
    yield


def test_prewarm_imports_every_listed_module():
    for name in PREWARM_IMPORTS:
        sys.modules.pop(name, None)
    prewarm()
    for name in PREWARM_IMPORTS:
        assert name in sys.modules, f"{name} 声称预热了但其实没进 sys.modules"


def test_the_botocore_chain_is_what_federation_pulls():
    """预热清单存在的理由：federation 会把生产日志点名的 botocore 拽进来。
    哪天 agentkit 解耦了 botocore，这条测试提醒我们把清单删短。"""
    prewarm()
    import agentkit.observability.federation  # noqa: F401  与生产首帧同一入口

    assert "botocore" in sys.modules


def test_prewarm_is_repeatable_and_second_call_is_free():
    prewarm()
    t0 = time.perf_counter()
    prewarm()
    # 第二次只剩 sys.modules 查表；forkserver 预热与 job 进程各调一次不能重复付费
    assert (time.perf_counter() - t0) * 1000 < 50


def test_prewarm_has_the_job_proc_signature_the_sdk_calls_it_with():
    """SDK 以 initialize_process_fnc(proc) 的形式调用（worker.py:631），多传参数不能炸。"""
    prewarm(object())  # job_proc 替身：我们不读它，但必须收得下


def test_worker_wires_it_into_the_real_worker_options():
    """worker.py 里 `prewarm_fnc=prewarm` 写错名字，这里用真实 SDK 类接一遍就会炸。"""
    from livekit.agents import WorkerOptions

    opts = WorkerOptions(entrypoint_fnc=lambda ctx: None, prewarm_fnc=prewarm,
                         **worker_options_kwargs(5, port=8091))
    assert opts.prewarm_fnc is prewarm


def test_redis_asyncio_is_on_the_list():
    """2026-11-20 生产：job 进程 `event loop blocked for 11232ms importing
    redis.asyncio`，超了 liveness 窗口被 SDK 杀掉重试。redis_control 只带 Lua
    字符串、不 import redis 客户端；真正的重 import 在 platform.build_platform
    的 `from redis import asyncio`。清单漏它 = 每个冷 job 再赌一次十几秒。"""
    assert "redis.asyncio" in PREWARM_IMPORTS
    prewarm()
    assert "redis.asyncio" in sys.modules
    assert "redis.typing" in sys.modules  # 日志点名的另一半，随 asyncio 一起进来


def test_saxw_cold_start_blockers_are_on_the_list():
    """2026-11-18 Saxw 真机对账点名的首帧阻塞：漏一项 = 用户再等十几秒。"""
    required = {
        "companion.agent.memory.hooks",   # 16.2s
        "companion.bootstrap.platform",   # sqlalchemy/schema 冷 import
        "companion.api.livekit.agent",    # 368ms
        "osc_data._core",                 # 998ms（volcengine TTS）
        "anyio.streams.stapled",          # 147ms
    }
    missing = required - set(PREWARM_IMPORTS)
    assert not missing, f"Saxw 阻塞模块没进预热清单: {sorted(missing)}"


def test_langgraph_checkpointer_is_on_the_list():
    """2026-11-22 stage-4 生产：VAD 修复上线后，新进程接房仍冻 10–13s，
    loop_monitor 点名 `importing langgraph at bootstrap/platform.py:197
    _checkpointer`（13121ms）。清单里的 companion.bootstrap.platform 只把
    模块本体拉进来——`from langgraph.checkpoint.postgres.aio import
    AsyncPostgresSaver` 藏在函数体里，每房间第一次装配平台才冷 import。
    每个新 job 进程付一次，用户听到的就是接房后十几秒的静默。"""
    required = {
        "langgraph.checkpoint.postgres.aio",  # _checkpointer:197（13.1s 的那条）
    }
    missing = required - set(PREWARM_IMPORTS)
    assert not missing, f"checkpointer 冷 import 没进预热清单: {sorted(missing)}"
    prewarm()
    for name in required:
        assert name in sys.modules, f"{name} 声称预热了但其实没进 sys.modules"


def test_brain_build_chain_is_on_the_list():
    """2026-11-23 stage-5 生产：langgraph 补上后两通真机（05:29/05:33）仍各冻
    10.2/10.4s，loop_monitor 帧落在 build_platform → _build_brain。104 生产
    venv `-X importtime` 实测：冷 build_platform 9.8–11.0s，其中
    companion.agent.brain.deerflow 一条 3.85s（langchain_anthropic 2.16s +
    deerflow.mcp 1.9s 都在它的模块级 import 上）。清单里
    companion.api.livekit.agent 只 import agent 模块本体，够不着 brain 链——
    `_build_brain` 函数体里的每一项都是每房间第一次装配才冷 import。"""
    required = {
        "companion.agent.brain.deerflow",   # importtime: 3.85s 的那条主链
        "companion.agent.llm.router",       # _build_brain 函数体
        "companion.bootstrap.models",       # 同上（brain_models/chat_model）
        "companion.agent.brain.tools",      # 同上（to_langchain_tools）
        "psycopg_pool",                     # astart 里 checkpointer 池的真身
    }
    missing = required - set(PREWARM_IMPORTS)
    assert not missing, f"大脑装配链没进预热清单: {sorted(missing)}"
    prewarm()
    for name in required:
        assert name in sys.modules, f"{name} 声称预热了但其实没进 sys.modules"
