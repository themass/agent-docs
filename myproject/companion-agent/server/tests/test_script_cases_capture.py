"""capture / freeze：FakeBrain 跑一轮 → JSON → 写回 YAML 的 expect_reply。

不碰已提交的 cases/voice/*.yaml：全程用 tempfile 副本。
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from companion.agent.brain.fake import FakeBrain
from companion.devtools.script_room.case_schema import load_case
from tools.script_cases import capture_case, freeze_case

_MINIMAL_YAML = """\
id: greet_emotion
goal: 问候带情绪
steps:
  - user: "你好"
  - protocol:
      - speech.seg
      - speech.end
audios: synthesize
"""


async def test_freeze_writes_expect_reply_into_yaml(tmp_path: Path):
    case_path = tmp_path / "greet_emotion.yaml"
    case_path.write_text(_MINIMAL_YAML, encoding="utf-8")
    capture_path = tmp_path / "capture.json"

    brain = FakeBrain(script=["[soft]你好呀，我在这儿。"])
    payload = await capture_case(case_path=case_path, brain=brain, out_path=capture_path)

    assert capture_path.is_file()
    assert payload["reply_lines"] == ["[soft]你好呀，我在这儿。"]
    assert "speech.seg" in payload["protocol"]
    assert payload["protocol"][-1] == "speech.end"

    freeze_case(case_path=case_path, capture_path=capture_path)

    reloaded = load_case(case_path)
    reply_steps = [s for s in reloaded.steps if s.expect_reply is not None]
    assert len(reply_steps) == 1
    assert reply_steps[0].expect_reply == ("[soft]你好呀，我在这儿。",)

    raw = yaml.safe_load(case_path.read_text(encoding="utf-8"))
    assert any("expect_reply" in step for step in raw["steps"])


def test_freeze_replaces_existing_expect_reply(tmp_path: Path):
    yaml_text = """\
id: multi_seg
goal: 多句
steps:
  - user: "聊聊今天吧"
  - expect_reply:
      - "旧句一。"
  - protocol:
      - speech.seg
      - speech.end
audios: synthesize
"""
    case_path = tmp_path / "multi_seg.yaml"
    case_path.write_text(yaml_text, encoding="utf-8")
    capture_path = tmp_path / "capture.json"
    capture_path.write_text(
        json.dumps(
            {
                "case_id": "multi_seg",
                "user": "聊聊今天吧",
                "reply_lines": ["今天天气不错。", "要不要出去走走？"],
                "protocol": ["speech.seg", "speech.seg", "speech.end"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    freeze_case(case_path=case_path, capture_path=capture_path)

    reloaded = load_case(case_path)
    reply_steps = [s for s in reloaded.steps if s.expect_reply is not None]
    assert len(reply_steps) == 1
    assert reply_steps[0].expect_reply == ("今天天气不错。", "要不要出去走走？")
