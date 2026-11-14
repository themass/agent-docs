"""AgentKit — shared platform components for agent products."""

from importlib.metadata import PackageNotFoundError, version

try:
    # 从安装元数据读，而不是手写常量：`build.sh` 把日期与内容摘要写进发行版版本号，
    # 手写的 __version__ 不会跟着变，于是 "装的是哪一份" 在代码里看得见、在常量里看不见。
    # 源码树直接跑（没安装）时才回落到 "0.0.0+source"。
    __version__ = version("agentkit")
except PackageNotFoundError:  # pragma: no cover - 只有在未安装的源码树里才会走到
    __version__ = "0.0.0+source"
