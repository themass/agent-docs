"""语音房间并发上限：负载函数、与 SDK 的“满”判断对接、配置默认值。"""

import math
from types import SimpleNamespace

import pytest

from companion.api.livekit.capacity import FULL_AT, room_load, worker_options_kwargs


def server(n_rooms):
    return SimpleNamespace(active_jobs=[object()] * n_rooms)


def is_full(load, threshold=FULL_AT):
    """SDK 的判断：有效负载 >= 阈值 就报“已满”（worker.py 的 _update_worker_status）。"""
    return load >= threshold


@pytest.mark.parametrize("rooms,full", [(0, False), (1, False), (4, False), (5, True), (6, True), (9, True)])
def test_a_worker_reports_full_exactly_when_it_reaches_the_cap(rooms, full):
    assert is_full(room_load(5)(server(rooms))) is full


def test_the_load_is_the_share_of_the_cap():
    assert room_load(4)(server(1)) == 0.25 and room_load(4)(server(2)) == 0.5


def test_a_cap_of_one_means_one_room_per_worker():
    load = room_load(1)
    assert not is_full(load(server(0))) and is_full(load(server(1)))


def test_the_threshold_is_valid_in_production():
    # SDK 在生产环境要求阈值不超过 1，超过会告警
    assert FULL_AT <= 1.0 and not math.isinf(FULL_AT)


@pytest.mark.parametrize("bad", [0, -1])
def test_a_non_positive_cap_is_rejected_by_the_load_function(bad):
    with pytest.raises(ValueError):
        room_load(bad)


def test_zero_means_unlimited_and_passes_nothing_to_the_sdk():
    assert worker_options_kwargs(0) == {} and worker_options_kwargs(-3) == {}


def test_a_positive_cap_sets_both_the_function_and_the_threshold():
    kw = worker_options_kwargs(5)
    assert set(kw) == {"load_fnc", "load_threshold"} and kw["load_threshold"] == FULL_AT
    assert kw["load_fnc"](server(5)) == 1.0


def test_the_options_are_accepted_by_the_real_worker_options_class():
    """不靠猜：用 SDK 真实的 WorkerOptions 接一遍，参数名写错会在这里直接报。"""
    from livekit.agents import WorkerOptions

    opts = WorkerOptions(entrypoint_fnc=lambda ctx: None, **worker_options_kwargs(5))
    assert opts.load_threshold == FULL_AT and opts.load_fnc(server(3)) == 0.6
    opts.validate_config(devmode=False)        # 生产模式的校验不报错


def test_the_setting_has_a_conservative_default_and_reads_the_env(monkeypatch):
    from companion.config import Settings

    monkeypatch.delenv("COMPANION_VOICE_MAX_ROOMS", raising=False)
    assert Settings(_env_file=None).companion_voice_max_rooms == 5
    monkeypatch.setenv("COMPANION_VOICE_MAX_ROOMS", "12")
    assert Settings(_env_file=None).companion_voice_max_rooms == 12
