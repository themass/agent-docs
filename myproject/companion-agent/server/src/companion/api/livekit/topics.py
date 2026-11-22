"""房间里的**文本流** topic。单独一个模块，理由是这个值的引用方跨了两层。

``lk.chat`` 是 LiveKit 原生的文本流 topic（不是我们 v2 信封的 ``cmp.*`` 四个之一，
所以它**不在** ``agent.protocol.catalog`` 的方向表里——把它放进那张表会让人以为它也
受 ``allowed()`` 的收发方向门禁管，其实不受）。

生产侧（``entrypoint``）与剧本房侧（``devtools.script_room.rtc``）都要这个值，
但剧本房**不能** import ``entrypoint``：那个模块在模块级 import 音频探针
（``inbound_audio_probe`` / ``outbound_audio_probe``），后者 ``from livekit import rtc``
加 ``from livekit.agents.voice.io import AudioInput``。为了一个字符串把 livekit 与
livekit.agents 整个拖进模块图，代价是「离线」测试也必须装 ``--extra livekit`` 才跑得动，
而这恰恰掩盖了剧本房本来能离线跑这件事。所以值的本尊放这里，两边各自 import 它。
"""

from __future__ import annotations

#: 用户在房间里发文字用的文本流 topic。
TEXT_TOPIC = "lk.chat"

__all__ = ["TEXT_TOPIC"]
