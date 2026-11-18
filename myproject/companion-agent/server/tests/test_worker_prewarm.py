"""prewarm：job 进程启动时把首帧重 import 提前做完。

钉住三件事：
1. 列出来的模块真的会被 import 进 sys.modules（prewarm 写错了不会报错、只是没效果——
   这正是线上 11.8s 阻塞的原样，测试必须能抓到"静默失效"）；
2. 它会作为 WorkerOptions.prewarm_fnc 挂进真实 SDK（参数名写错 = 白做）；
3. 失败不吞（prewarm 抛异常 SDK 会弃用该进程，静默吞掉反而让坏环境继续接房）。
"""

import sys
import time

from companion.api.livekit.capacity import worker_options_kwargs
from companion.api.livekit.prewarm import PREWARM_IMPORTS, prewarm


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
