"""旁路写入器：不阻塞、满了丢并计数、失败隔离、关停时排空。"""

import asyncio

from companion.trace.writer import BackgroundWriter


def job(log, tag, delay=0.0, fail=False):
    async def run():
        if delay:
            await asyncio.sleep(delay)
        if fail:
            raise RuntimeError(tag)
        log.append(tag)
    return run


async def test_submit_returns_immediately_even_if_the_job_is_slow():
    w, log = BackgroundWriter(), []
    t0 = asyncio.get_running_loop().time()
    assert w.submit(job(log, "a", delay=0.5)) is True
    assert asyncio.get_running_loop().time() - t0 < 0.05 and log == []
    await w.close()
    assert log == ["a"]


async def test_jobs_run_in_the_background_and_all_complete_on_flush():
    w, log = BackgroundWriter(workers=2), []
    for i in range(20):
        w.submit(job(log, i))
    assert await w.flush(2.0)
    assert sorted(log) == list(range(20)) and w.stats.written == 20 and w.stats.pending == 0
    await w.close()


async def test_a_full_queue_drops_instead_of_blocking_and_counts():
    w, log = BackgroundWriter(max_queue=3, workers=1), []
    results = [w.submit(job(log, i, delay=0.2)) for i in range(10)]
    assert results.count(False) >= 5 and w.stats.dropped == results.count(False)
    assert w.stats.queued + w.stats.dropped == 10
    await w.close(timeout=5)


async def test_a_failing_job_does_not_stop_the_others():
    w, log = BackgroundWriter(workers=1), []
    w.submit(job(log, "boom", fail=True))
    w.submit(job(log, "after"))
    await w.flush(2.0)
    assert log == ["after"] and w.stats.failed == 1 and w.stats.written == 1
    await w.close()


async def test_close_drains_what_it_can_and_reports_what_it_could_not(caplog):
    import logging

    w, log = BackgroundWriter(workers=1), []
    w.submit(job(log, "fast"))
    w.submit(job(log, "never", delay=30))
    with caplog.at_level(logging.WARNING, logger="companion.trace"):
        await w.close(timeout=0.3)
    assert log == ["fast"] and "unwritten" in caplog.text


async def test_submit_after_close_starts_fresh_instead_of_raising():
    w, log = BackgroundWriter(), []
    await w.close()
    assert w.submit(job(log, "x")) is True
    await w.close()
    assert log == ["x"]


def test_submit_without_a_running_loop_drops_quietly():
    w = BackgroundWriter()
    assert w.submit(job([], "x")) is False and w.stats.dropped == 1
