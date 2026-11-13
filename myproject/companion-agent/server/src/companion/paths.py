"""文件在磁盘的哪里 —— 目录布局知识的唯一出处。

布局::

    companion-agent/           PROJECT_ROOT   docs/ scripts/ run.sh
    ├── server/                SERVER_ROOT    Python 工程：src/ tests/ migrations/ .env
    │   └── src/companion/     本文件所在的包
    └── agent/                 AGENT_ROOT     不是 Python，当数据发布：角色卡、角色目录、skill、模型路由

为什么单独放一个模块：以前布局知识散在各处，用 ``parents[1]`` / ``parents[2]`` 各自数层数
（``config.py``、``tests/``、``migrations/env.py`` ……）。目录一动，每一处都要同步改，
而数错一层**不会报错**——角色卡和 skill 加载失败时会静默退化，进程照样起得来。

这里的 assert 是为了在 import 时就按**名字**确认"这是哪个目录"，而不是靠数层数猜；
``tests/test_paths.py`` 再从外面把它钉住。

纯路径计算，不 import 任何 ``companion`` 子包，所以任何层都可以用。
"""

from __future__ import annotations

from pathlib import Path

#: ``companion-agent/server`` —— Python 工程根，放 ``.env``、``pyproject.toml``、``migrations/``。
SERVER_ROOT = Path(__file__).resolve().parents[2]

#: ``companion-agent`` —— server 与 agent 的共同父目录，放 ``docs/``、``scripts/``。
PROJECT_ROOT = SERVER_ROOT.parent

#: ``companion-agent/agent`` —— 角色卡、角色目录、skill、模型路由。不是 Python。
AGENT_ROOT = PROJECT_ROOT / "agent"

# 数错一层会让每一次角色卡 / skill 查找都落空，而落空时代码是静默退化的，
# 原来的缺陷就是这样活下来的。所以在 import 时失败，不要等到第一个文件找不到。
assert SERVER_ROOT.name == "server", f"SERVER_ROOT 解析到了 {SERVER_ROOT}"
assert (SERVER_ROOT / "src" / "companion").is_dir(), f"{SERVER_ROOT} 下没有 src/companion"

#: 各类资源的位置。
CHARACTERS_DIR = AGENT_ROOT / "characters"
ROLES_CATALOG_DIR = AGENT_ROOT / "roles" / "catalog"
SKILLS_PUBLIC_DIR = AGENT_ROOT / "skills" / "public"
LLM_ROUTING_PATH = AGENT_ROOT / "llm" / "routing.yaml"
ENV_FILE = SERVER_ROOT / ".env"
