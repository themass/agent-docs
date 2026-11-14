"""回合收尾的往返编排：哪些命令必须真的被排进同一个 pipeline。

这一段以前没有测试，而线上正是这里出的错：``finish_turn`` 里的
``self._release(client=pipe, ...)`` 少了 ``await``。``AsyncScript.__call__`` 是
``async def``，不 await 就只造出一个协程对象——pipeline 里一条释放锁的命令都没有，
会话锁从此再也没被释放过。日志里唯一线索是

    RuntimeWarning: coroutine 'AsyncScript.__call__' was never awaited

覆盖它的集成测试全在 ``test_turn_redis.py``，需要 ``COMPANION_TEST_REDIS_URL``，
没配就整体跳过，所以这条 bug 一路绿灯上到了线上。这里用一个记录型假 Redis
在**不需要真库**的前提下守住「命令真的进了 pipeline」。
"""

import pytest

from companion.service.turn import redis_control as rc


class _Script:
    """``redis.asyncio`` 下 ``register_script`` 的返回值：``__call__`` 是 async 的。

    关键是这一点与真实现一致——写成同步方法的话，测试就抓不到「忘了 await」。
    传了 ``client`` 时它把 EVALSHA 排进 pipeline 并登记到 ``client.scripts``，
    真正的执行仍只在 ``execute()``。
    """

    def __init__(self, script: str) -> None:
        self.script = script
        self.sha = f"sha:{hash(script) & 0xFFFFFF:06x}"

    async def __call__(self, *, keys=None, args=None, client=None):
        if client is None:
            return 0
        client.scripts.add(self)
        return await client.evalsha(self.sha, len(keys or []), *(list(keys or []) + list(args or [])))


class _Pipe:
    def __init__(self) -> None:
        self.commands: list[tuple] = []
        self.scripts: set = set()

    def xadd(self, key, fields, **kwargs):
        self.commands.append(("xadd", key))
        return self

    def expire(self, key, ttl):
        self.commands.append(("expire", key))
        return self

    def delete(self, key):
        self.commands.append(("delete", key))
        return self

    async def evalsha(self, sha, numkeys, *args):
        self.commands.append(("evalsha", sha, numkeys, args))
        return self

    async def execute(self):
        return [None] * len(self.commands)


class _Redis:
    def __init__(self) -> None:
        self.pipes: list[_Pipe] = []

    def register_script(self, script: str) -> _Script:
        return _Script(script)

    def pipeline(self, transaction: bool = True) -> _Pipe:
        assert transaction is False, "回合控制面的合并往返一律不用 MULTI：单节点下没必要，还会放大延迟"
        pipe = _Pipe()
        self.pipes.append(pipe)
        return pipe


def _control() -> tuple[rc.RedisTurnControl, _Redis]:
    redis = _Redis()
    return rc.RedisTurnControl(redis), redis


async def test_finish_turn_stages_the_lock_release_in_the_same_pipeline():
    """最后一条事件、删回合状态、释放锁必须一次往返发完，且释放锁真的在 batch 里。"""
    control, redis = _control()
    await control.finish_turn(session_id=5, owner="proc:turn1", turn_id="turn1",
                              event="message.done", data={"turn_id": "turn1"})
    assert len(redis.pipes) == 1, "收尾只应有一次往返"
    kinds = [c[0] for c in redis.pipes[0].commands]
    assert kinds == ["xadd", "expire", "delete", "evalsha"]
    # 释放锁必须在最后：先放锁，下一个回合就可能写好自己的 turn hash，
    # 紧接着的 DEL 会把新回合的状态删掉。
    assert kinds[-1] == "evalsha"
    assert redis.pipes[0].scripts, "释放锁的脚本必须登记到 pipeline，否则不会被执行"


async def test_finish_turn_leaves_no_unawaited_coroutine():
    """同一件事的另一种说法：收尾路径不许留下没被 await 的协程。

    这是那条 bug 的直接症状（``RuntimeWarning: coroutine ... was never awaited``）。
    把它写成断言，是因为「命令有没有排进 pipeline」和「有没有忘 await」
    虽是同一个原因，但下一次可能有人用别的方式改坏其中一边。
    """
    import gc
    import warnings

    control, _ = _control()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        await control.finish_turn(session_id=7, owner="proc:turn2", turn_id="turn2",
                                  event="message.done", data={"turn_id": "turn2"})
        gc.collect()
    unawaited = [str(w.message) for w in caught if "never awaited" in str(w.message)]
    assert unawaited == []
